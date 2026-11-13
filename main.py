import os
from fastapi import FastAPI, Request
import requests

app = FastAPI()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Глобальная переменная для хранения рабочей модели (кэш)
CACHED_MODEL = None

def get_free_model():
    """Ищет бесплатную модель и запоминает её, чтобы не искать каждый раз."""
    global CACHED_MODEL
    if CACHED_MODEL:
        return CACHED_MODEL
        
    try:
        # Запрашиваем список моделей только если в кэше пусто
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=2.5)
        if resp.status_code == 200:
            for model in resp.json().get("data", []):
                if model.get("id", "").endswith(":free") and not model.get("archived", False):
                    CACHED_MODEL = model["id"] # Запоминаем модель
                    return CACHED_MODEL
    except Exception:
        pass
    return "openrouter/free" # Запасной вариант

@app.post("/")
async def main(request: Request):
    global CACHED_MODEL
    body = await request.json()
    user_text = body["request"]["original_utterance"]

    model_to_use = get_free_model()

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://alice.yandex.ru",
                "X-Title": "Alisa Skill"
            },
            json={
                "model": model_to_use,
                "messages": [{"role": "user", "content": user_text}]
            },
            timeout=4.0
        )

        # Если модель устарела (404) - сбрасываем кэш, чтобы в следующий раз найти новую
        if response.status_code == 404:
            CACHED_MODEL = None 
            return {
                "version": body["version"],
                "session": body["session"],
                "response": {
                    "end_session": False,
                    "text": "Модель обновилась, попробуйте задать вопрос еще раз."
                }
            }

        if response.status_code != 200:
            return {
                "version": body["version"],
                "session": body["session"],
                "response": {
                    "end_session": False,
                    "text": f"Ошибка: {response.status_code}"
                }
            }
        
        response_data = response.json()
        
        if "choices" in response_data and len(response_data["choices"]) > 0:
            answer = response_data["choices"][0]["message"]["content"]
        else:
            answer = "Пустой ответ от нейросети."

    except requests.exceptions.Timeout:
        answer = "Нейросеть думает слишком долго. Попробуйте вопрос покороче."
    except Exception:
        answer = "Ошибка подключения."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer
        }
    }
