# fetch the emails using google oauth service
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import os
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import base64

def get_gmail_service():
    scopes = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']
    if os.path.exists('token.json'):    
        credentials = Credentials.from_authorized_user_file("token.json", scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            with open('token.json', 'w') as f:
                f.write(credentials.to_json())

        
        
        
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json",
        scopes = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/gmail.send']
        )
        
        credentials = flow.run_local_server(port=0)
        with open('token.json', 'w') as file:
            file.write(credentials.to_json())
        

    
    return build('gmail', 'v1', credentials = credentials)



def get_unread_emails():
    email_data = []
    now = datetime.now()
    duration = timedelta(days = 7)
    past_date = now - duration
    formatted_date = past_date.strftime("%Y/%m/%d")
    service = get_gmail_service()

    results = (
            service.users().messages().list(userId="me", labelIds=["INBOX"], q=f"is:unread after:{formatted_date}").execute()
        )
    messages = results.get("messages", [])

    for message in messages:
        msg = (
        service.users().messages().get(userId="me", id=message["id"]).execute()
        )

        subject = next(s['value'] for s in msg["payload"]["headers"] if s['name'] == 'Subject')
        sender_email = next(s['value'] for s in msg["payload"]["headers"] if s['name'] == 'From')
        date_sent = next(s['value'] for s in msg["payload"]["headers"] if s['name'] == 'Date')
        if msg['payload'].get('parts'):
            try:
                body = next(p['body']['data'] for p in msg["payload"]['parts'] if p['mimeType'] == 'text/plain')
            except StopIteration:
                body = next((p['body']['data'] for p in msg["payload"]['parts'] if p['mimeType'] == 'text/html'), None)
        else:
            body = msg['payload']['body']['data']
        if body:
            decoded_bytes = base64.urlsafe_b64decode(body)
            body_text = decoded_bytes.decode('utf-8')
        else:
            body_text = ""
        email_dict = {
            "message_id": message['id'],
            "sender_email": sender_email,
            "date_sent": date_sent,
            "subject": subject,
            "body": body_text,
            "thread_id": message['threadId']

        }
        email_data.append(email_dict)
    return email_data


        

def get_sent_emails():
    sent_email_set = set()
    now = datetime.now()
    duration = timedelta(days = 30)
    past_date = now - duration
    formatted_date = past_date.strftime("%Y/%m/%d")
    service = get_gmail_service()

    results = (
            service.users().messages().list(userId="me", labelIds=["SENT"], q=f"after:{formatted_date}").execute()
        )
    messages = results.get("messages", [])

    for message in messages:
        msg = (
        service.users().messages().get(userId="me", id=message["id"]).execute()
        )

        sent_email = next(s['value'] for s in msg["payload"]["headers"] if s['name'] == 'To')
        
      
        sent_email_set.add(sent_email)
    return sent_email_set



def get_thread_messages(thread_id:str):
    thread_list = []
    service = get_gmail_service()

    results = (
            service.users().threads().get(userId="me", id=thread_id).execute()
        )
    messages = results.get("messages", [])
    for msg in messages:
        sender_email = next(s['value'] for s in msg["payload"]["headers"] if s['name'] == 'From')
        if msg['payload'].get('parts'):
            try:
                body = next(p['body']['data'] for p in msg["payload"]['parts'] if p['mimeType'] == 'text/plain')
            except StopIteration:
                body = next((p['body']['data'] for p in msg["payload"]['parts'] if p['mimeType'] == 'text/html'), None)
        else:
            body = msg['payload']['body']['data']
        if body:
            decoded_bytes = base64.urlsafe_b64decode(body)
            body_text = decoded_bytes.decode('utf-8')
        else:
            body_text = ""
        thread_list.append({
            "sender": sender_email,
            "body": body_text
        })
    return thread_list


        
        
        
      
    
