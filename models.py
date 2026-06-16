import sqlite3
import os
from llm_classifier import ClassificationOutput
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "app.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS EMAIL_DATA(
                message_id VARCHAR PRIMARY KEY,
                sender_email VARCHAR NOT NULL,
                date_sent DATETIME NOT NULL,
                subject TEXT,
                body TEXT,
                category TEXT NOT NULL,
                confidence REAL,
                rationale TEXT,
                state VARCHAR,
                draft_id VARCHAR,
                reminder_time DATETIME,
                created_at DATETIME NOT NULL,
                classified_at DATETIME,
                notified_at DATETIME,
                drafted_at DATETIME,
                delivered_at DATETIME,
                read_completed_at DATETIME,
                thread_id VARCHAR
                   )
""")
    conn.commit()
    conn.close()





def insert_email(email: dict, classification):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO EMAIL_DATA 
        (message_id, sender_email, date_sent, subject, body, category, confidence, rationale, state, draft_id, reminder_time, created_at, classified_at, notified_at, drafted_at, delivered_at, read_completed_at, thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email['message_id'],
        email['sender_email'],
        email['date_sent'],
        email['subject'],
        email['body'],
        classification.category.value,
        classification.confidence,
        classification.rationale,
        'new',
        None,
        None,
        datetime.now(),
        datetime.now(),
        None,
        None,
        None,
        None,
        email['thread_id']
    ))
    conn.commit()
    conn.close()

def get_email(message_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM EMAIL_DATA WHERE message_id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_state(message_id:str, new_state:str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE EMAIL_DATA SET state = ? WHERE message_id = ?", (new_state, message_id))
    conn.commit()
    conn.close()

def update_draft(message_id:str, draft_id:str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE EMAIL_DATA SET draft_id = ? WHERE message_id = ?", (draft_id, message_id))
    conn.commit()
    conn.close()
