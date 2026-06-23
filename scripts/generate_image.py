"""
generate_image.py
Free, no-key image generation via Pollinations.ai.
Docs: https://pollinations.ai/ (simple GET request returns image bytes)
"""
import requests
import urllib.parse
from pathlib import Path

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"
IMAGE_DIR = Path(__file__).parent.parent / "data" / "images"


def generate_image(prompt: str, request_id: str, width=1024, height=1024) -> str:
    """
    Generates an image from `prompt` and saves it locally.
    Returns the local file path.
    """
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    encoded_prompt = urllib.parse.quote(prompt)
    # nologo=true removes the watermark, seed randomizes each regeneration
    url = f"{POLLINATIONS_BASE}/{encoded_prompt}?width={width}&height={height}&nologo=true"

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()

    image_path = IMAGE_DIR / f"{request_id}.jpg"
    with open(image_path, "wb") as f:
        f.write(resp.content)

    return str(image_path)


if __name__ == "__main__":
    path = generate_image("A clean modern illustration of AI and human collaboration, minimalist", "test123")
    print(f"Saved to {path}")
