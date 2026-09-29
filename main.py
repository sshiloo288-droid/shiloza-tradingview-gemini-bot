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

# רשימת מודלים נתמכים בסדר עדיפויות (כולל המודל העדכני ביותר)
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

def send_telegram_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

@app.get("/")
def home():
    return {"status": "Server is running"}

@app.post("/webhook")
async def tradingview_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}

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
            img_data = requests.get(chart_url, timeout=10).content
            contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))
        except Exception as e:
            print(f"Error fetching image: {e}")

    response_text = None
    last_exception = None

    # ניסיון אוטומטי מול רשימת המודלים עד להצלחה
    for model_name in CANDIDATE_MODELS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2
                )
            )
            response_text = response.text
            break
        except Exception as e:
            print(f"Failed with model {model_name}: {e}")
            last_exception = e

    if response_text:
        send_telegram_message(f"📊 **סקירת שוק אוטומטית - {ticker}**\n\n{response_text}")
        return {"status": "success"}
    else:
        error_msg = f"❌ שגיאה ביצירת הניתוח: {last_exception}"
        send_telegram_message(error_msg)
        return {"status": "error", "message": str(last_exception)}
