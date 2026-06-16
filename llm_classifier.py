from pydantic import BaseModel, Field
from enum import Enum
from email_fetcher import *
import re
from groq import Groq
from config import GROQ_API_KEY
import json

class Categories(str, Enum):
    job_update = "job_update"
    university = "university"
    conversation = "conversation"

    informational = "informational"
    noise = "noise"

class ClassificationOutput(BaseModel):
    category: Categories
    confidence: float = Field(ge = 0, le = 1)
    rationale: str

domains = ["swe", "pinterest", "jobright", "SCALIS", "careerbrew", "scentbird", "tldr", "monster", "wellfound", "substack", "hireft", "ziprecruiter", "extern", "linktree"]

def rule_based_filter(email: dict, sent_emails: set):
    
    if email.get("sender_email") in sent_emails:
        return Categories.conversation
    if "@iu.edu" in email.get("sender_email", ""):
        return Categories.university
    if any(domain in email.get("sender_email", "") for domain in domains):
        return Categories.noise
    else:
        return None
    


SYSTEM_PROMPT = """You are an expert email classifier for a personal Gmail triage assistant. 
Your job is to categorize incoming emails into exactly one of the following categories:

- job_update: Emails from companies or recruiters about a specific job application 
  status (rejection, interview invite, offer, resume received confirmation).
- university: Emails from a university domain or academic institution 
  (course updates, admin, faculty, student services).
- conversation: Emails that are direct replies from a real person the user 
  has previously corresponded with (personal or professional back-and-forth).
- informational: Emails directed personally at the user but requiring no reply 
  (account alerts, GitHub notifications, event invites, cold recruiter outreach).
- noise: Bulk, promotional, or automated emails (newsletters, job digests, 
  marketing, unsubscribe lists, social notifications).

Return ONLY a JSON object with exactly these fields:
{
  "category": one of the five category strings above,
  "confidence": float between 0 and 1,
  "rationale": one sentence explaining your decision
}

Examples:

Email: From: LinkedIn Jobs <jobs@linkedin.com>, Subject: 13 new Data Scientist jobs for you
{"category": "noise", "confidence": 0.98, "rationale": "Bulk job digest email from LinkedIn, not directed personally at the user."}

Email: From: John Smith <john.smith@gmail.com>, Subject: Re: Meeting next week
{"category": "conversation", "confidence": 0.95, "rationale": "Direct reply from an individual continuing a prior conversation."}

Email: From: Recruiting <recruiting@google.com>, Subject: Your application for SWE Intern
{"category": "job_update", "confidence": 0.92, "rationale": "Email from a company recruiter referencing a specific job application."}"""

client = Groq(api_key=GROQ_API_KEY)

def classify_email(email:dict):
  
    
    completion = client.chat.completions.create(

        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                
                "role": "user",
                "content": f"From: {email['sender_email']}\nSubject: {email['subject']}\nBody: {email['body']}"
            }
        ],
        temperature=0.6,
        max_completion_tokens=1024,
        top_p=0.95,
        stream=False
    )

    response_string = completion.choices[0].message.content
    data = json.loads(response_string)
    return ClassificationOutput(**data)


    
def classify(email:dict, sent_emails: set):
    rule_result = rule_based_filter(email, sent_emails)
    if rule_result is not None:
        return ClassificationOutput(category=rule_result, confidence=1.0, rationale="Rule-based filter matched")
    else:
        return classify_email(email)





