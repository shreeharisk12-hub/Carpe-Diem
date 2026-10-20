import asyncio
import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI(title="Brahma Voice")
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brahma.voice")

@app.get("/health")
def health():
    return {"status": "healthy", "service": "voice"}

@app.websocket("/voice")
async def voice(websocket: WebSocket):
    await websocket.accept()
    logger.info("Voice client connected")

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=(
            "You are Brahma, a helpful voice AI assistant "
            "for people using basic phones in India. "
            "Speak naturally and keep answers brief. "
            "Respond in the language the caller uses. "
            "You are an AI assistant, not a deity."
        )
    )

    try:
        async with client.aio.live.connect(
            model="gemini-3.8-live",
            config=config
        ) as session:

            logger.info("Gemini Live connected")

            async def send_audio():
                while True:
                    audio = await websocket.receive_bytes()

                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=audio,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )

            async def receive_audio():
                while True:
                    async for response in session.receive():
                        content = response.server_content

                        if content and content.model_turn:
                            for part in content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    await websocket.send_bytes(
                                        part.inline_data.data
                                    )

                        if content and content.interrupted:
                            await websocket.send_text("CLEAR")

            tasks = [
                asyncio.create_task(send_audio()),
                asyncio.create_task(receive_audio())
            ]

            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            await asyncio.gather(
                *pending,
                return_exceptions=True
            )

            for task in done:
                task.result()

    except WebSocketDisconnect:
        logger.info("Voice client disconnected")
    except Exception:
        logger.exception("Voice session failed")
    finally:
        logger.info("Voice session closed")
