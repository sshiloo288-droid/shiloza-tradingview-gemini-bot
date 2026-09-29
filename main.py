import os
import requests
from fastapi import FastAPI, Request
from google import genai
from google.genai import types

app = FastAPI()

# טעינת משתני סביבה מאובטחים
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

@app.get("/")
def home():
    return {"status": "Server is running"}

@app.post("/webhook")
async def tradingview_webhook(request: Request):
    data = await request.json()
    
    ticker = data.get("ticker", "NQ / ES")
    price = data.get("price", "N/A")
    chart_url = data.get("chart_url", None)
    custom_msg = data.get("message", "ניתוח מתוזמן לפתיחת סשן")
    
    system_instruction = """
    אתה אנליסט מסחר מומחה הפועל לפי מתודולוגיית SMC / ICT.
    בצע ניתוח של הנתונים והגרף והחזר סקירה ממוקדת הכוללת:
    1. כיוון מרכזי (Bias) ומיקום המחיר ביחס ל-TDO / TWO / Discount / Premium.
    2. זיהוי אזורי עניין (POI / FVG / Liquidity Sweep).
    3. תרחיש עבודה מומלץ לפתיחת הסשן (Judas Swing, יעד BSL/SSL).
    """
    
    prompt = f"נכס: {ticker}\nמחיר נוכחי: {price}\nהודעת התראה: {custom_msg}"
    
    contents = [prompt]
    if chart_url:
        try:
            img_data = requests.get(chart_url).content
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))
        except Exception as e:
            print(f"Error fetching image: {e}")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2
        )
    )
    
    send_telegram_message(f"📊 **סקירת שוק אוטומטית - {ticker}**\n\n{response.text}")
    return {"status": "success"}
