import os
from fastapi import FastAPI, Request
import requests

app = FastAPI()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.post("/")
async def main(request: Request):
    body = await request.json()
    user_text = body["request"]["original_utterance"]

    response = requests.post(
        OPENROUTER_API_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://alice.yandex.ru",
            "X-Title": "Alisa Skill"
        },
        json={
            "model": "deepseek/deepseek-chat-v3-0324:free",
            "messages": [{"role": "user", "content": user_text}]
        }
    )

    if response.status_code != 200:
        return {
            "version": body["version"],
            "session": body["session"],
            "response": {
                "end_session": False,
                "text": f"Ошибка OpenRouter: {response.status_code}"
            }
        }
    
    response_data = response.json()
    if "choices" in response_data:
        answer = response_data["choices"][0]["message"]["content"]
    else:
        answer = "Не удалось получить ответ от нейросети."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer
        }
    }
