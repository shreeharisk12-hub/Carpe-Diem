import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="Brahma Exotel Gateway")
logger = logging.getLogger("uvicorn.error")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "exotel-gateway"
    }


@app.websocket("/exotel/media")
async def exotel_media(ws: WebSocket):
    await ws.accept()
    logger.info("Exotel WebSocket connected")

    stream_sid = None
    authorized = False

    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                logger.info("Exotel connected event")

            elif event == "start":
                start = data.get("start", {})
                stream_sid = start.get("stream_sid")
                logger.info(
                    "Call started; audio rate: %s",
                    start.get("media_format", {}).get("sample_rate")
                )

                # This gateway is diagnostic only.
                # Caller authorization will be added
                # before enabling public access.
                authorized = False

            elif event == "media":
                if not authorized:
                    continue

                # Later:
                # Decode caller audio.
                # Resample for Gemini Live.
                # Forward audio to Gemini.
                pass

            elif event == "dtmf":
                logger.info("Keypad input received")

            elif event == "stop":
                logger.info("Call ended")
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")

    except json.JSONDecodeError:
        logger.warning("Invalid JSON received")

    except Exception:
        logger.exception("Gateway error")

    finally:
        logger.info("Exotel session closed")
