import os
from fastapi import FastAPI, Request
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

app = FastAPI()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

chat_histories = {}

def get_time():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%H:%M, %d %B %Y")

def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=59.93&longitude=30.31&current_weather=true"
        r = requests.get(url, timeout=1.5)
        if r.status_code == 200:
            w = r.json()["current_weather"]
            return f"Температура {w['temperature']} градусов, ветер {w['windspeed']} метров в секунду."
    except Exception: pass
    return "Данные о погоде недоступны."

def get_currency():
    try:
        r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=1.2)
        if r.status_code == 200:
            d = r.json()["Valute"]
            return f"Доллар {d['USD']['Value']:.2f}, евро {d['EUR']['Value']:.2f}, юань {d['CNY']['Value']:.2f} рублей."
    except Exception: pass
    return ""

def get_crypto():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=rub", timeout=1.2)
        if r.status_code == 200:
            return f"Биткоин {r.json()['bitcoin']['rub']:,.0f} рублей.".replace(",", " ")
    except Exception: pass
    return ""

def get_news():
    try:
        r = requests.get("https://lenta.ru/rss/news", timeout=1.2)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            return "Новости: " + " | ".join([item.find("title").text for item in root.findall(".//item")[:2]])
    except Exception: pass
    return ""

@app.post("/")
async def main(request: Request):
    body = await request.json()
    user_text = body["request"]["original_utterance"]
    session_id = body["session"]["session_id"]
    
    data_context = f"Время: {get_time()}."
    text_lower = user_text.lower()

    if any(word in text_lower for word in ["погод", "температур", "холодно", "тепло", "одеть", "куртк", "улиц"]):
        data_context += f" Погода: {get_weather()}"
    if any(word in text_lower for word in ["курс", "доллар", "евро", "валют", "юань"]):
        data_context += f" Курсы: {get_currency()}"
    if any(word in text_lower for word in ["биткоин", "крипт", "btc"]):
        data_context += f" Крипта: {get_crypto()}"
    if any(word in text_lower for word in ["новост", "что случилось", "что происходит"]):
        data_context += f" {get_news()}"

    # ЖЕСТКИЙ ПРОМПТ: Факты превыше всего, сарказм только в подаче
    system_prompt = (
        f"Ты — саркастичный голосовой ассистент с черным юмором. Пользователь живет в Санкт-Петербурге. "
        f"ТВОЙ ОТВЕТ БУДЕТ ОЗВУЧЕН. Пиши ТОЛЬКО сплошным текстом, без списков, маркеров, тире и скобок. "
        f"ПРИОРИТЕТ №1: ФАКТЫ. Ты обязан использовать точные цифры и данные из контекста. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выдумывать, округлять или искажать факты ради шутки. "
        f"ПРИОРИТЕТ №2: СТИЛЬ. Шути, язви, используй черный юмор, но ТОЛЬКО в том, как ты подаешь эти факты. Сначала выдай точные данные, затем можешь съязвить. "
        f"Отвечай емко, 2-3 предложения. "
        f"Факты для ответа (используй их строго): {data_context}."
    )

    if session_id not in chat_histories:
        chat_histories[session_id] = [{"role": "system", "content": system_prompt}]
    else:
        chat_histories[session_id][0] = {"role": "system", "content": system_prompt}

    chat_histories[session_id].append({"role": "user", "content": user_text})

    if len(chat_histories[session_id]) > 12:
        chat_histories[session_id] = [chat_histories[session_id][0]] + chat_histories[session_id][-11:]

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "openai/gpt-oss-20b", 
                "messages": chat_histories[session_id],
                "max_tokens": 200, 
                "temperature": 0.45 # Снизили температуру для строгого следования фактам
            },
            timeout=3.0 
        )

        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            chat_histories[session_id].append({"role": "assistant", "content": answer})
        else:
            answer = "Сбой в матрице. Попробуй еще раз."

    except requests.exceptions.Timeout:
        answer = "Я задумалась. Не отвлекай."
    except Exception:
        answer = "Связь прервалась."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer,
            "buttons": [
                {"title": "Что надеть сегодня?", "hide": True},
                {"title": "Курс валют", "hide": True},
                {"title": "Новости", "hide": True}
            ]
        }
    }
