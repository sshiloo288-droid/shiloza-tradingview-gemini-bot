import os
import time
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

# רשימת מודלים עדכניים בלבד
CANDIDATE_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.8-pro",
    "gemini-2.5-pro",
    "gemini-1.5-flash-latest"
]

def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if not res.ok:
            payload.pop("parse_mode", None)
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

    # ניסיון פנייה עם מנגנון Retry קצר לשגיאות עומס זמניות (503)
    for model_name in CANDIDATE_MODELS:
        for attempt in range(3):  # עד 3 ניסיונות מול אותו מודל במקרה של עומס
            try:
                print(f"Attempting model {model_name} (Attempt {attempt + 1})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.2
                    )
                )
                if response and response.text:
                    response_text = response.text
                    break
            except Exception as e:
                last_exception = e
                err_str = str(e)
                print(f"Failed with {model_name} (Attempt {attempt + 1}): {e}")
                
                # במקרה של שגיאת עומס 503, נמתין 1.5 שניות וננסה שוב
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(1.5)
                    continue
                # בשגיאות 404/אחרות נעבור מיד למודל הבא ברשימה
                break

        if response_text:
            break

    if response_text:
        send_telegram_message(f"📊 *סקירת שוק אוטומטית - {ticker}*\n\n{response_text}")
        return {"status": "success"}
    else:
        error_msg = f"❌ שגיאה ביצירת הניתוח: {last_exception}"
        send_telegram_message(error_msg)
        return {"status": "error", "message": str(last_exception)}
