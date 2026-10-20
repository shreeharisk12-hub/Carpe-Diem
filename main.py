import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = FastAPI(title="Brahma AI")
logger = logging.getLogger("uvicorn.error")

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

class Question(BaseModel):
    text: str

@app.get("/")
def home():
    return {
        "name": "Brahma",
        "status": "online",
        "message": "AI accessible to every phone"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/ask")
def ask(question: Question):
    try:
        response = client.interactions.create(
            model="gemini-3.8-flash",
            input=question.text,
            generation_config={
                "thinking_level": "low",
                "max_output_tokens": 150
            }
        )

        return {
            "response": response.output_text
        }

    except Exception as e:
        logger.error(
            "Gemini error: %s: %s",
            type(e).__name__,
            e
        )
        raise HTTPException(
            status_code=502,
            detail="AI provider request failed"
        )
