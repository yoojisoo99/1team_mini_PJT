import os
import smtplib
from email.message import EmailMessage

def send_gmail(to_email: str, subject: str, body: str) -> None:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pw = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pw:
        raise RuntimeError("환경변수 GMAIL_USER / GMAIL_APP_PASSWORD가 필요합니다.")

    msg = EmailMessage()
    msg["From"] = f"LUMINA CAPITAL <{gmail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
        s.starttls()
        s.login(gmail_user, gmail_pw)
        s.send_message(msg)