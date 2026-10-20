import asyncio
import binascii
import base64
import json
import logging
import os
import secrets
import time

import numpy as np
from scipy.signal import resample_poly

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from google import genai
from google.genai import types
from weather_tool import get_weather

load_dotenv()

app = FastAPI(title="Brahma Phone AI")
logger = logging.getLogger("uvicorn.error")

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)

ALLOWED_CALLERS = {
    "".join(c for c in number if c.isdigit())[-10:]
    for number in os.environ["ALLOWED_CALLERS"].split(",")
    if number.strip()
}
GATEWAY_TOKEN = os.environ["EXOTEL_GATEWAY_TOKEN"]

MAX_CALL_SECONDS = 180


def convert_audio(data, input_rate, output_rate):
    if input_rate == output_rate:
        return data

    samples = np.frombuffer(data, dtype="<i2")

    if len(samples) == 0:
        return b""

    from math import gcd

    divisor = gcd(input_rate, output_rate)

    converted = resample_poly(
        samples.astype(np.float32),
        output_rate // divisor,
        input_rate // divisor
    )

    converted = np.clip(
        np.rint(converted),
        -32768,
        32767
    ).astype("<i2")

    return converted.tobytes()


def normalize_number(number):
    value = str(number or "")
    digits = "".join(c for c in value if c.isdigit())

    if len(digits) == 10:
        return "+91" + digits

    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits

    if len(digits) == 11 and digits.startswith("0"):
        return "+91" + digits[1:]

    return ""


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "brahma-phone-ai"
    }


@app.websocket("/exotel/media")
async def phone_call(ws: WebSocket):
    authorization = ws.headers.get("authorization", "")
    username = ""
    password = ""

    if authorization.lower().startswith("basic "):
        try:
            encoded = authorization.split(" ", 1)[1]
            decoded = base64.b64decode(
                encoded, validate=True
            ).decode("utf-8")
            username, password = decoded.split(":", 1)
        except (
            ValueError,
            UnicodeDecodeError,
            binascii.Error
        ):
            pass

    valid_user = secrets.compare_digest(
        username, "brahma"
    )
    valid_password = secrets.compare_digest(
        password, GATEWAY_TOKEN
    )

    if not (valid_user and valid_password):
        await ws.close(code=1008)
        return

    await ws.accept()

    stream_sid = None
    call_started = time.monotonic()

    try:
        first = await asyncio.wait_for(
            ws.receive_text(), timeout=15
        )

        event = json.loads(first)

        if event.get("event") == "connected":
            event = json.loads(
                await asyncio.wait_for(
                    ws.receive_text(), timeout=15
                )
            )

        if event.get("event") != "start":
            await ws.close(code=1008)
            return

        start = event.get("start", {})

        stream_sid = (
            start.get("stream_sid")
            or event.get("stream_sid")
        )

        caller = normalize_number(start.get("from"))

        if not (
            stream_sid
            and caller
            and caller[-10:] in ALLOWED_CALLERS
        ):
            logger.warning("Unauthorized call rejected")
            await ws.close(code=1008)
            return

        rate = int(
            start.get("media_format", {}).get(
                "sample_rate", 8000
            )
        )

        if rate not in (8000, 16000, 24000):
            await ws.close(code=1003)
            return

        logger.info("Authorized Brahma call started")

        weather_declaration = types.FunctionDeclaration(
            name="get_weather",
            description=(
                "Get real weather forecasts for a named city, "
                "town or village. Use this when the caller asks "
                "about current weather, temperature or rain today "
                "or tomorrow. Ask for the location if missing."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "location": types.Schema(
                        type=types.Type.STRING,
                        description="Place name, preferably with district."
                    ),
                    "day": types.Schema(
                        type=types.Type.STRING,
                        description="Either today or tomorrow."
                    )
                },
                required=["location"]
            )
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            tools=[types.Tool(
                function_declarations=[weather_declaration]
            )],
            system_instruction=(
                "You are Brahma, a friendly AI voice "
                "assistant for basic-phone users in India. "
                "Keep responses short and natural. "
                "Answer in the caller's language. "
                "You are an AI assistant, not a deity."
            )
        )

        async with client.aio.live.connect(
            model="gemini-3.8-live",
            config=config
        ) as session:

            output_queue = asyncio.Queue(maxsize=50)

            async def receive_phone():
                while True:
                    if time.monotonic() - call_started > MAX_CALL_SECONDS:
                        break

                    raw = await ws.receive_text()
                    message = json.loads(raw)
                    kind = message.get("event")

                    if kind == "stop":
                        break

                    if kind != "media":
                        continue

                    payload = message.get(
                        "media", {}
                    ).get("payload")

                    if not payload:
                        continue

                    audio = base64.b64decode(payload)

                    pcm = convert_audio(
                        audio, rate, 16000
                    )

                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=pcm,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )

            async def receive_gemini():
                while True:
                    async for response in session.receive():

                        if response.tool_call:
                            function_responses = []

                            for call in response.tool_call.function_calls:
                                if call.name != "get_weather":
                                    continue

                                args = dict(call.args or {})
                                location = str(
                                    args.get("location", "")
                                )
                                day = str(
                                    args.get("day", "today")
                                )

                                logger.info(
                                    "Weather requested; period=%s",
                                    day
                                )

                                try:
                                    result = await asyncio.wait_for(
                                        asyncio.to_thread(
                                            get_weather,
                                            location,
                                            day
                                        ),
                                        timeout=20
                                    )
                                except asyncio.TimeoutError:
                                    result = {
                                        "error": "Weather lookup timed out."
                                    }
                                except Exception:
                                    logger.exception(
                                        "Weather lookup failed"
                                    )
                                    result = {
                                        "error": "Weather lookup failed."
                                    }

                                function_responses.append(
                                    types.FunctionResponse(
                                        id=call.id,
                                        name=call.name,
                                        response={"result": result}
                                    )
                                )

                            if function_responses:
                                await session.send_tool_response(
                                    function_responses=function_responses
                                )

                        if not response.server_content:
                            continue

                        content = response.server_content

                        if not content:
                            continue

                        if content.interrupted:
                            while not output_queue.empty():
                                try:
                                    output_queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break

                            await ws.send_json({
                                "event": "clear",
                                "stream_sid": stream_sid
                            })

                        if content.model_turn:
                            for part in content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    audio = convert_audio(
                                        part.inline_data.data,
                                        24000,
                                        rate
                                    )

                                    logger.info(
                                        "Gemini generated %d bytes",
                                        len(audio)
                                    )

                                    await output_queue.put(audio)

                        if content.turn_complete:
                            logger.info(
                                "Gemini response turn completed"
                            )

                    logger.info(
                        "Gemini receive iteration finished; "
                        "continuing to listen"
                    )

            async def send_phone_audio():
                chunk_bytes = max(3200, int(rate * 2 * 0.2))
                buffer = b""

                while True:
                    data = await output_queue.get()
                    buffer += data

                    while len(buffer) >= chunk_bytes:
                        chunk = buffer[:chunk_bytes]
                        buffer = buffer[chunk_bytes:]

                        await ws.send_json({
                            "event": "media",
                            "stream_sid": stream_sid,
                            "media": {
                                "payload": base64.b64encode(
                                    chunk
                                ).decode("ascii")
                            }
                        })

                        await asyncio.sleep(chunk_bytes / (rate * 2))

            tasks = [
                asyncio.create_task(receive_phone()),
                asyncio.create_task(receive_gemini()),
                asyncio.create_task(send_phone_audio())
            ]

            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                if task.cancelled():
                    logger.warning("A bridge task was cancelled")
                elif task.exception():
                    logger.error(
                        "Bridge task failed: %r",
                        task.exception()
                    )
                else:
                    logger.warning(
                        "A bridge task finished normally: %s",
                        task.get_coro().__name__
                    )

            for task in pending:
                task.cancel()

            await asyncio.gather(
                *pending,
                return_exceptions=True
            )

            for task in done:
                task.result()

    except Exception:
        logger.exception("Phone session failed")

    finally:
        logger.info("Brahma phone session closed")
        try:
            await ws.close()
        except Exception:
            pass
