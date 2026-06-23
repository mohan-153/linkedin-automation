"""
check_replies.py
Polls your Gmail inbox (via IMAP) for replies to review emails,
parses the command (POST / REGENERATE / SKIP), and triggers the right action.

Matching strategy (in order of preference):
  1. In-Reply-To / References header matches a Message-ID we stored.
  2. Fallback: subject line contains "[req:<request_id>]" tag.

Run this frequently via cron (e.g. every 2 minutes) so replies are
actioned quickly.
"""
import email
import imaplib
import os
import re
import sys
from email.header import decode_header

sys.path.insert(0, os.path.dirname(__file__))
import state
import linkedin_post
import generate_post
import generate_image
import send_review_email
import fetch_news

IMAP_HOST = "imap.gmail.com"
REQ_TAG_RE = re.compile(r"\[req:([a-f0-9]+)\]")


def _connect_imap():
    gmail_address = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(gmail_address, app_password)
    return imap


def _decode(s):
    if s is None:
        return ""
    parts = decode_header(s)
    return "".join(
        p.decode(enc or "utf-8") if isinstance(p, bytes) else p for p, enc in parts
    )


COMMANDS = ("POST", "REGENERATE", "SKIP")


def _extract_command(body: str) -> str:
    """
    Scans non-empty, non-quoted lines (top of the reply, before any
    '> quoted original message' or 'On ... wrote:' boilerplate) and
    returns the first recognized command word found at the START of a line.
    Allows trailing text on the same line, e.g. "REGENERATE - make it punchier".
    """
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Stop scanning once we hit quoted original content or reply boilerplate
        if line.startswith(">") or (line.lower().startswith("on ") and "wrote:" in line.lower()):
            break

        first_word = line.upper().split()[0].rstrip(".,!:;-")
        if first_word in COMMANDS:
            return first_word

        # First substantive line wasn't a command -> don't keep scanning
        # further lines (avoids matching a stray word deep in a long reply).
        break
    return ""


def _get_plain_text_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="replace")
        return ""
    else:
        charset = msg.get_content_charset() or "utf-8"
        return msg.get_payload(decode=True).decode(charset, errors="replace")


def find_request_id(msg) -> str | None:
    in_reply_to = msg.get("In-Reply-To", "")
    references = msg.get("References", "")

    for message_id in [in_reply_to] + references.split():
        message_id = message_id.strip()
        if not message_id:
            continue
        draft = state.get_draft_by_message_id(message_id)
        if draft:
            return draft["request_id"]

    subject = _decode(msg.get("Subject", ""))
    match = REQ_TAG_RE.search(subject)
    if match:
        return match.group(1)

    return None


def process_unread_replies():
    imap = _connect_imap()
    imap.select("INBOX")

    status, data = imap.search(None, "UNSEEN")
    if status != "OK":
        imap.logout()
        return

    message_nums = data[0].split()
    if not message_nums:
        imap.logout()
        print("No new replies.")
        return

    for num in message_nums:
        status, msg_data = imap.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        request_id = find_request_id(msg)
        if not request_id:
            continue  # not a reply to one of our review emails

        draft = state.get_draft(request_id)
        if not draft or draft["status"] != "pending":
            continue  # already actioned or unknown

        body = _get_plain_text_body(msg)
        command = _extract_command(body)

        if command == "POST":
            handle_post(draft)
        elif command == "REGENERATE":
            handle_regenerate(draft)
        elif command == "SKIP":
            handle_skip(draft)
        else:
            print(f"Reply for {request_id} did not contain a recognized command.")

    imap.logout()


def handle_post(draft):
    print(f"Posting draft {draft['request_id']} to LinkedIn...")
    linkedin_post.publish_post(draft["post_text"], draft["image_path"])
    state.update_status(draft["request_id"], "posted")
    print("Posted and marked as 'posted'.")


def handle_skip(draft):
    state.update_status(draft["request_id"], "skipped")
    print(f"Draft {draft['request_id']} skipped.")


def handle_regenerate(draft):
    print(f"Regenerating draft {draft['request_id']}...")
    state.update_status(draft["request_id"], "regenerating")
    state.increment_regenerate(draft["request_id"])

    new_post = generate_post.generate_post(
        draft["news_summary"],
        regenerate_hint="The previous version wasn't approved. Write a noticeably different angle or tone.",
    )
    new_img_prompt = generate_post.generate_image_prompt(new_post)

    new_request_id = state.new_request_id()
    new_image_path = generate_image.generate_image(new_img_prompt, new_request_id)

    msg_id = send_review_email.send_review_email(
        new_request_id, new_post, new_image_path, draft["news_summary"]
    )

    state.create_draft(
        request_id=new_request_id,
        news_summary=draft["news_summary"],
        post_text=new_post,
        image_path=new_image_path,
        image_prompt=new_img_prompt,
        message_id=msg_id,
    )
    print(f"New draft {new_request_id} created and sent for review.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    state.init_db()
    process_unread_replies()
