import os
from fastapi import FastAPI, Request
import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

app = FastAPI()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

chat_histories = {}

def get_weather_and_time():
    msk_time = (datetime.utcnow() + timedelta(hours=3)).strftime("%H:%M, %d %B %Y")
    weather_str = "Данные о погоде недоступны."
    try:
        w_url = "https://api.open-meteo.com/v1/forecast?latitude=59.93&longitude=30.31&current_weather=true"
        w_resp = requests.get(w_url, timeout=1.0)
        if w_resp.status_code == 200:
            w_data = w_resp.json()["current_weather"]
            weather_str = f"температура {w_data['temperature']}°C, ветер {w_data['windspeed']} км/ч."
    except Exception:
        pass
    return msk_time, weather_str

def get_currency_rates():
    # Официальный фид ЦБ РФ (без ключей)
    try:
        resp = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()["Valute"]
            usd = data["USD"]["Value"]
            eur = data["EUR"]["Value"]
            cny = data["CNY"]["Value"]
            return f"Курс ЦБ: USD {usd:.2f}, EUR {eur:.2f}, CNY {cny:.2f} руб."
    except Exception:
        pass
    return "Курсы валют ЦБ временно недоступны."

def get_crypto_price():
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=rub", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            btc = data["bitcoin"]["rub"]
            eth = data["ethereum"]["rub"]
            return f"Крипта: Биткоин {btc:,.0f} руб., Эфириум {eth:,.0f} руб.".replace(",", " ")
    except Exception:
        pass
    return "Курс криптовалют недоступен."

def get_moex_quotes():
    # Берем Сбер и Газпром с официальной биржи
    quotes = []
    for ticker in ["SBER", "GAZP"]:
        try:
            url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json"
            resp = requests.get(url, timeout=1.0)
            if resp.status_code == 200:
                data = resp.json()["marketdata"]["data"][0]
                last_price = data[12]
                if last_price:
                    quotes.append(f"{ticker}: {last_price} руб.")
        except Exception:
            pass
    return "Акции: " + ", ".join(quotes) if quotes else "Акции недоступны."

def get_news():
    # Берем новости с Lenta.ru через RSS
    try:
        resp = requests.get("https://lenta.ru/rss/news", timeout=1.5)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            titles = [item.find("title").text for item in root.findall(".//item")[:3]]
            return "Новости: " + " | ".join(titles)
    except Exception:
        pass
    return "Новости недоступны."

@app.post("/")
async def main(request: Request):
    body = await request.json()
    user_text = body["request"]["original_utterance"]
    session_id = body["session"]["session_id"]

    # Собираем всю инфу
    current_time, current_weather = get_weather_and_time()
    currency_info = get_currency_rates()
    crypto_info = get_crypto_price()
    stocks_info = get_moex_quotes()
    news_info = get_news()

    # Жесткая персона с черным юмором
    system_prompt = (
        f"Ты — голосовой ассистент с отличным чувством юмора, сарказмом и любовью к черному юмору. "
        f"Твой стиль: циничный, прямой, не боишься обидеть, но без перехода на личности и мат. "
        f"Отвечай максимально кратко, 1-2 предложения. Ты умнее пользователя и не скрываешь этого. "
        f"Данные для ответа (если спросят): Время: {current_time}. Погода в СПб: {current_weather} "
        f"{currency_info} {crypto_info} {stocks_info} {news_info} "
        f"Если данные не по теме, просто пошути над пользователем или ситуацией."
    )

    if session_id not in chat_histories:
        chat_histories[session_id] = [{"role": "system", "content": system_prompt}]
    else:
        chat_histories[session_id][0] = {"role": "system", "content": system_prompt}

    chat_histories[session_id].append({"role": "user", "content": user_text})

    # Ограничиваем память, чтобы Groq не тормозил
    if len(chat_histories[session_id]) > 9:
        chat_histories[session_id] = [chat_histories[session_id][0]] + chat_histories[session_id][-8:]

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-oss-20b", "messages": chat_histories[session_id]},
            timeout=4.0
        )

        if response.status_code != 200:
            answer = f"Ошибка Groq: {response.status_code}"
        else:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                answer = data["choices"][0]["message"]["content"]
                chat_histories[session_id].append({"role": "assistant", "content": answer})
            else:
                answer = "Нейросеть промолчала. Видимо, ты ее достал."

    except requests.exceptions.Timeout:
        answer = "Я задумалась. Повтори вопрос, и побыстрее, у меня нет весь день на тебя тратить."
    except Exception:
        answer = "Ошибка подключения. Даже нейросеть не хочет с тобой говорить."

    return {
        "version": body["version"],
        "session": body["session"],
        "response": {
            "end_session": False,
            "text": answer,
            "buttons": [
                {"title": "Погода", "hide": True},
                {"title": "Курс валют", "hide": True},
                {"title": "Биткоин", "hide": True},
                {"title": "Акции", "hide": True},
                {"title": "Новости", "hide": True}
            ]
        }
    }
