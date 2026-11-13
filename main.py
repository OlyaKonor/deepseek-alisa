import os
from fastapi import FastAPI, Request
import requests

app = FastAPI()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.post("/")
async def main(request: Request):
    body = await request.json()
    user_text = body["request"]["original_utterance"]

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": user_text}]
            },
            timeout=4.0
        )

        if response.status_code != 200:
            return {
                "version": body["version"],
                "session": body["session"],
                "response": {
                    "end_session": False,
                    "text": f"Ошибка Groq: {response.status_code}"
                }
            }
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            answer = data["choices"][0]["message"]["content"]
        else:
            answer = "Нейросеть вернула пустой ответ."

    except requests.exceptions.Timeout:
        answer = "Нейросеть думает слишком долго. Попробуйте спросить короче."
    except Exception:
        answer = "Ошибка подключения к нейросети."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer
        }
    }
