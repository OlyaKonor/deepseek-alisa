import os
from fastapi import FastAPI, Request
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

app = FastAPI()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Память для сессий
chat_histories = {}

def get_time():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%H:%M, %d %B %Y")

def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=59.93&longitude=30.31&current_weather=true"
        r = requests.get(url, timeout=0.8)
        if r.status_code == 200:
            w = r.json()["current_weather"]
            return f"Погода в СПб: {w['temperature']}°C, ветер {w['windspeed']} км/ч."
    except Exception: pass
    return ""

def get_currency():
    try:
        r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=0.8)
        if r.status_code == 200:
            d = r.json()["Valute"]
            return f"Курсы: USD {d['USD']['Value']:.2f}, EUR {d['EUR']['Value']:.2f}, CNY {d['CNY']['Value']:.2f}."
    except Exception: pass
    return ""

def get_crypto():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=rub", timeout=0.8)
        if r.status_code == 200:
            return f"Биткоин: {r.json()['bitcoin']['rub']:,.0f} руб.".replace(",", " ")
    except Exception: pass
    return ""

def get_news():
    try:
        r = requests.get("https://lenta.ru/rss/news", timeout=0.8)
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

    # Умная загрузка данных (только по запросу)
    if any(word in text_lower for word in ["погод", "температур", "холодно", "тепло", "одеть", "куртк"]):
        data_context += f" {get_weather()}"
    if any(word in text_lower for word in ["курс", "доллар", "евро", "валют", "юань"]):
        data_context += f" {get_currency()}"
    if any(word in text_lower for word in ["биткоин", "крипт", "btc"]):
        data_context += f" {get_crypto()}"
    if any(word in text_lower for word in ["новост", "что случилось", "что происходит"]):
        data_context += f" {get_news()}"

    # ИСПРАВЛЕННЫЙ ПРОМПТ
    system_prompt = (
        f"Ты — голосовой ассистент с сарказмом и черным юмором. Ты умный, язвительный, но ПОЛЕЗНЫЙ. "
        f"ВАЖНО: Пользователь живет в Санкт-Петербурге, Россия. "
        f"Ты ОБЯЗАН давать четкие рекомендации и советы, когда тебя просят (например, что надеть по погоде, стоит ли брать зонт, как поступить в ситуации). Не отказывай в помощи. "
        f"ГЛАВНОЕ ПРАВИЛО: Отвечай емко, по делу, без воды. Сразу переходи к сути! Если нужен список — используй короткие пункты. "
        f"Факты для ответа (используй их, если они есть): {data_context}."
    )

    # Инициализация памяти
    if session_id not in chat_histories:
        chat_histories[session_id] = [{"role": "system", "content": system_prompt}]
    else:
        chat_histories[session_id][0] = {"role": "system", "content": system_prompt}

    chat_histories[session_id].append({"role": "user", "content": user_text})

    # РАСШИРЕННАЯ ПАМЯТЬ: Оставляем 12 последних сообщений
    if len(chat_histories[session_id]) > 12:
        chat_histories[session_id] = [chat_histories[session_id][0]] + chat_histories[session_id][-11:]

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "openai/gpt-oss-20b", 
                "messages": chat_histories[session_id],
                "max_tokens": 250, 
                "temperature": 0.7 
            },
            timeout=3.2 
        )

        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            chat_histories[session_id].append({"role": "assistant", "content": answer})
        else:
            answer = f"Сбой в матрице. Код: {response.status_code}."

    except requests.exceptions.Timeout:
        answer = "Я задумалась. Не отвлекай."
    except Exception:
        answer = "Связь с космосом прервалась. Попробуй еще раз."

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
