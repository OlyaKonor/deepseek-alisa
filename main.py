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

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://alice.yandex.ru",
                "X-Title": "Alisa Skill",
                "Content-Type": "application/json"
            },
            json={
                # Самая быстрая и стабильная бесплатная модель на данный момент
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{"role": "user", "content": user_text}]
            },
            timeout=4.0 # Ждем ответа не дольше 4 секунд
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
        
        if "choices" in response_data and len(response_data["choices"]) > 0:
            answer = response_data["choices"][0]["message"]["content"]
        else:
            answer = "Нейросеть вернула пустой ответ."

    except requests.exceptions.Timeout:
        answer = "Нейросеть задумалась слишком надолго. Попробуйте спросить что-то попроще."
    except Exception:
        answer = "Произошла ошибка при подключении."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer
        }
    }
