"""
send_review_email.py
Sends the generated draft (text + image) to your Gmail for review via SMTP.
Uses a Gmail App Password (NOT your normal password).

Subject line includes the request_id in a parseable tag, e.g.:
  "LinkedIn Draft Review [req:ab12cd34ef56]"
This same tag is used by check_replies.py to match your reply back to the draft,
as a fallback/double-check alongside the Message-ID/In-Reply-To matching.
"""
import os
import smtplib
import uuid
from email.message import EmailMessage
from email.utils import make_msgid

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_review_email(request_id: str, post_text: str, image_path: str, news_summary: str) -> str:
    """
    Sends the review email. Returns the Message-ID we generated (string),
    so it can be stored and matched against IMAP replies later.
    """
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("REVIEW_RECIPIENT", gmail_address)

    if not gmail_address or not app_password:
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in environment")

    msg = EmailMessage()
    domain = gmail_address.split("@")[-1]
    msg_id = make_msgid(domain=domain)
    msg["Message-ID"] = msg_id
    msg["Subject"] = f"LinkedIn Draft Review [req:{request_id}]"
    msg["From"] = gmail_address
    msg["To"] = recipient

    body = f"""Here's today's draft LinkedIn post.

-----------------------------------
{post_text}
-----------------------------------

Source news used:
{news_summary}

HOW TO RESPOND:
Reply to this email with ONE word as the first line of your reply:

  POST        -> publishes this exact draft to LinkedIn
  REGENERATE  -> discards this draft and generates a new one
  SKIP        -> does nothing, draft is discarded

(Reply text is case-insensitive. Just make sure the keyword is the first line.)
"""
    msg.set_content(body)

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as f:
            img_data = f.read()
        msg.add_attachment(img_data, maintype="image", subtype="jpeg", filename="draft_image.jpg")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(gmail_address, app_password)
        smtp.send_message(msg)

    return msg_id


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    mid = send_review_email("test123", "This is a test post.", "", "No news, this is a test.")
    print(f"Sent. Message-ID: {mid}")
