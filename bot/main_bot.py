"""
main_bot.py — Entry-point del Bot Telegram RATIO.
Gestisce comandi e messaggi in arrivo, e lancia il job scheduler giornaliero.
"""

import logging
from datetime import time as dtime
import pytz

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from bot.ai_sql import answer_question
from bot.scheduler import build_alert_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ITALY_TZ = pytz.timezone("Europe/Rome")


# ─────────────────────────────── HANDLERS ──────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start — rivela il Chat ID in modo che possa essere copiato in .env"""
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"👋 Ciao! Sono *RATIO Alert Bot*.\n\n"
        f"Il tuo *Chat ID* è: `{chat_id}`\n\n"
        f"Copialo nel file `.env` come `TELEGRAM_CHAT_ID` e anche su Render "
        f"tra le variabili d'ambiente. Poi sono pronto!",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help — mostra i comandi disponibili."""
    await update.message.reply_text(
        "🤖 *RATIO Alert Bot — Comandi:*\n\n"
        "📦 /scadenze — Mostra le scadenze dei prossimi 7 giorni\n"
        "❓ /help — Mostra questo messaggio\n\n"
        "💬 *Oppure scrivimi direttamente una domanda tipo:*\n"
        "• _Quanto abbiamo fatturato a febbraio?_\n"
        "• _Quali cantieri sono confermati questa settimana?_\n"
        "• _Mostrami i preventivi in bozza_",
        parse_mode="Markdown"
    )


async def scadenze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /scadenze — invia l'alert scadenze manualmente."""
    await update.message.reply_text("⏳ Sto controllando le scadenze...")
    msg = build_alert_message()
    if msg:
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("✅ Nessuna scadenza nei prossimi 7 giorni!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i messaggi in testo libero → Chat-to-SQL con Groq."""
    user_text = update.message.text
    await update.message.reply_text("🤔 Sto elaborando la tua domanda...")
    response = answer_question(user_text)
    # Niente parse_mode per evitare crash con asterischi/underscore non bilanciati dall'AI
    try:
        await update.message.reply_text(response)
    except Exception:
        await update.message.reply_text(response.replace("*", "").replace("_", "").replace("`", ""))


# ─────────────────────────────── JOB GIORNALIERO ───────────────────────────

async def daily_alert_job(context: ContextTypes.DEFAULT_TYPE):
    """Job che gira ogni mattina alle 08:00 e invia l'alert al chat configurato."""
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID non configurato. Alert non inviato.")
        return
    msg = build_alert_message()
    if msg:
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=msg,
            parse_mode="Markdown"
        )
        logger.info("Alert scadenze inviato con successo.")
    else:
        logger.info("Nessuna scadenza imminente oggi. Alert non inviato.")



async def main_async():
    """Versione async del main, compatibile con Render e qualsiasi ambiente cloud."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Registra i comandi
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scadenze", scadenze_command))

    # Gestisce i messaggi di testo libero
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler: alert alle 08:00 ogni giorno (ora italiana)
    job_queue = app.job_queue
    job_queue.run_daily(
        daily_alert_job,
        time=dtime(hour=8, minute=0, tzinfo=ITALY_TZ),
        name="daily_scadenze_alert"
    )

    logger.info("🤖 RATIO Bot avviato. In ascolto...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Entry point: usa asyncio.run() per garantire l'event loop su qualsiasi OS."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
