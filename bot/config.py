import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")  # Verrà riempito dopo /start
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
DATABASE_URL       = os.getenv("DATABASE_URL")

# Soglia in giorni per gli alert scadenze
ALERT_DAYS_AHEAD = 7
