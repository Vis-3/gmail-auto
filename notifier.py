import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from llm_classifier import ClassificationOutput
import html
from telegram.ext import Application, CallbackQueryHandler
from models import update_state, get_email, update_draft
from email_drafter import draft_email, save_gmail_draft


async def send_notification(email: dict, classification: ClassificationOutput):
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    message = (
    f"📧 <b>New Email</b>\n"
    f"<b>From:</b> {html.escape(email['sender_email'])}\n"
    f"<b>Subject:</b> {html.escape(email['subject'])}\n"
    f"<b>Category:</b> {classification.category.value}\n"
    f"<b>Rationale:</b> {html.escape(classification.rationale)}"
)
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Reply", callback_data=f"reply:{email['message_id']}"),
            InlineKeyboardButton("No Reply", callback_data=f"no_reply:{email['message_id']}")
        ]
    ])
    
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def handle_callback(update, context):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        return

    action, message_id = query.data.split(":")
    
    try:
        if action == "no_reply":
            update_state(message_id, "read_complete")
            await query.edit_message_text(f"✅ Marked as read: {message_id}")
    
        elif action == "reply":
            row = get_email(message_id)
            thread_id = row[17]
            sender_email = row[1]
            subject = row[3]
            email_dict = {
            "sender_email":sender_email,
            "subject":subject,
            "thread_id": thread_id
            }
            response_string = draft_email(thread_id)
            draft_id = save_gmail_draft(email_dict, response_string)
            update_draft(message_id, draft_id)
            update_state(message_id, "drafted")
            await query.edit_message_text(f"✍️ Drafting reply for: {message_id}")
    except Exception as e:
        print(f"Callback error: {e}")



