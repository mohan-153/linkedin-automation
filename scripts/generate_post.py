"""
generate_post.py
Uses Gemini to turn a Hacker News summary into a LinkedIn post,
and to produce a short image-generation prompt that visually matches the post.
"""
import os
from google import genai

MODEL = "gemini-2.0-flash"

POST_SYSTEM_PROMPT = """You are a tech thought-leader ghostwriter for LinkedIn.
Write ONE LinkedIn post based on the news items below.

Rules:
- Pick the single most interesting story (don't try to cover all of them).
- Hook in the first line (no "Exciting news!" cliches).
- 3-6 short paragraphs, easy to skim, can use 1-2 emojis max.
- End with a question or a light call-to-action to drive comments.
- Add 3-5 relevant hashtags at the end.
- Do NOT use markdown formatting (no asterisks, no headers).
- Output ONLY the post text, nothing else.
"""

IMAGE_PROMPT_SYSTEM = """Based on the LinkedIn post below, write ONE short image
generation prompt (max 30 words) describing a clean, professional, modern
illustration or concept visual that matches the post's theme. Avoid text in the image.
Output ONLY the prompt, nothing else.
"""


def _client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


def generate_post(news_summary: str, regenerate_hint: str = "") -> str:
    client = _client()
    prompt = f"{POST_SYSTEM_PROMPT}\n\nNEWS ITEMS:\n{news_summary}"
    if regenerate_hint:
        prompt += f"\n\nIMPORTANT: This is a regeneration. {regenerate_hint}"

    resp = client.models.generate_content(model=MODEL, contents=prompt)
    return resp.text.strip()


def generate_image_prompt(post_text: str) -> str:
    client = _client()
    prompt = f"{IMAGE_PROMPT_SYSTEM}\n\nPOST:\n{post_text}"
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    return resp.text.strip()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from fetch_news import get_top_stories, format_news_summary

    stories = get_top_stories()
    summary = format_news_summary(stories)
    post = generate_post(summary)
    print("--- POST ---")
    print(post)
    img_prompt = generate_image_prompt(post)
    print("\n--- IMAGE PROMPT ---")
    print(img_prompt)
