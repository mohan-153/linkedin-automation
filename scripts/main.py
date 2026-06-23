"""
main.py
Entry point run by cron at 9 AM and 7 PM.

Pipeline:
  1. Fetch top HN tech stories
  2. Generate LinkedIn post text via Gemini
  3. Generate a matching image prompt, then the image via Pollinations.ai
  4. Email the draft to you for review
  5. Save draft state (status='pending') so check_replies.py can act on your reply later
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()

import state
import fetch_news
import generate_post
import generate_image
import send_review_email


def run():
    state.init_db()

    print("Fetching top tech stories from Hacker News...")
    stories = fetch_news.get_top_stories()
    if not stories:
        print("No stories fetched, aborting this run.")
        return
    news_summary = fetch_news.format_news_summary(stories)
    print(news_summary)

    print("\nGenerating LinkedIn post with Gemini...")
    post_text = generate_post.generate_post(news_summary)
    print(post_text)

    print("\nGenerating image prompt...")
    image_prompt = generate_post.generate_image_prompt(post_text)
    print(image_prompt)

    request_id = state.new_request_id()

    print("\nGenerating image via Pollinations.ai...")
    image_path = generate_image.generate_image(image_prompt, request_id)
    print(f"Image saved to {image_path}")

    print("\nSending review email...")
    message_id = send_review_email.send_review_email(request_id, post_text, image_path, news_summary)
    print(f"Sent. Message-ID: {message_id}")

    state.create_draft(
        request_id=request_id,
        news_summary=news_summary,
        post_text=post_text,
        image_path=image_path,
        image_prompt=image_prompt,
        message_id=message_id,
    )
    print(f"\nDraft {request_id} saved with status 'pending'. Waiting for your email reply.")


if __name__ == "__main__":
    run()
