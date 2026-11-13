import os
from fastapi import FastAPI, Request
import requests

app = FastAPI()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# URL для получения списка всех моделей
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models" 
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.post("/")
async def main(request: Request):
    body = await request.json()
    user_text = body["request"]["original_utterance"]

    # 1. Получаем актуальный список всех моделей
    try:
        models_response = requests.get(OPENROUTER_MODELS_URL)
        models_data = models_response.json()
        
        # 2. Ищем первую попавшуюся бесплатную модель
        free_model_id = None
        for model in models_data.get("data", []):
            # Ищем модели, у которых в ID есть ":free" и которые не архивные
            if model.get("id", "").endswith(":free") and not model.get("archived", False):
                free_model_id = model["id"]
                break
        
        if not free_model_id:
            # Если вдруг не нашли, используем роутер как запасной вариант
            free_model_id = "openrouter/free"

    except Exception:
        # Если не удалось получить список, пробуем роутер
        free_model_id = "openrouter/free"

    # 3. Отправляем запрос к выбранной модели
    response = requests.post(
        OPENROUTER_API_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://alice.yandex.ru",
            "X-Title": "Alisa Skill"
        },
        json={
            "model": free_model_id,
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
