from email_fetcher import *
from groq import Groq
from config import GROQ_API_KEY


client = Groq(api_key=GROQ_API_KEY)
SYSTEM_PROMPT = """
You are a professional email assistant helping Sanskar Srivastava draft replies. 
You will be given a thread of emails showing the full conversation history.
Write a reply to the most recent email in the thread.

Guidelines:
- Keep the tone formal and polite but concise
- Do not repeat information already stated in the thread
- Address the sender by name if their name is available
- Sign off as "Sanskar Srivastava"
- Write ONLY the email body — no subject line, no metadata, no explanations
- If the email is a rejection or purely informational with nothing to respond to, write "NO_REPLY_NEEDED"

"""
def draft_email(thread_id:str):
  
    thread_list = get_thread_messages(thread_id)
    completion = client.chat.completions.create(

        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                
                "role": "user",
                "content": f"\n\n".join([
                    f"sender_email:{t['sender']}\n{t['body']}"
                    for t in thread_list
                ])
            }
        ],
        temperature=0.6,
        max_completion_tokens=1024,
        top_p=0.95,
        stream=False
    )

    response_string = completion.choices[0].message.content
    return response_string


from email.mime.text import MIMEText
import base64

def save_gmail_draft(email: dict, draft_text: str) -> str:
    service = get_gmail_service()
    
    msg = MIMEText(draft_text)
    msg['To'] = email['sender_email']
    msg['Subject'] = f"Re: {email['subject']}"
    
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    
    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw, "threadId": email['thread_id']}}
    ).execute()
    
    return draft['id']