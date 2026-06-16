import os
import base64

# Decode credentials from env vars if running on Railway (no filesystem secrets)
_creds_b64 = os.getenv("CREDENTIALS_JSON_B64")
if _creds_b64 and not os.path.exists("credentials.json"):
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(_creds_b64).decode())

_token_b64 = os.getenv("TOKEN_JSON_B64")
if _token_b64 and not os.path.exists("token.json"):
    with open("token.json", "w") as f:
        f.write(base64.b64decode(_token_b64).decode())

from email_fetcher import *
from email_fetcher import get_unread_emails
from llm_classifier import classify
from notifier import send_notification
import asyncio
from models import init_db, insert_email

init_db()


async def email_poller():
    while True:
        emails = get_unread_emails()
        sent_emails = get_sent_emails()
        for email in emails:
            result = classify(email, sent_emails)
            try:
                insert_email(email, result)
                
            except Exception:
                continue
            await send_notification(email, result)
        await asyncio.sleep(3600)

async def telegram_bot():
    from telegram.ext import Application, CallbackQueryHandler
    from notifier import handle_callback
    from config import TELEGRAM_BOT_TOKEN
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(handle_callback))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.sleep(float('inf'))

async def main():
    await asyncio.gather(email_poller(), telegram_bot())

asyncio.run(main())
        
