"""
linkedin_post.py
Publishes a text+image post to LinkedIn using the current (2026) Posts API.

Flow:
  1. (If needed) refresh the access token using the refresh token.
  2. Register an image upload via POST /rest/images?action=initializeUpload
  3. PUT the raw image bytes to the returned uploadUrl
  4. POST /rest/posts with the image URN referenced in `content.media.id`

Notes:
- Uses urn:li:person:{id} as author since this is a personal profile, not a company page.
- LinkedIn access tokens expire after 60 days; refresh tokens after 365 days.
  This module attempts a refresh automatically if a request returns 401.
- Required scope: w_member_social (already covered by your existing app setup).
"""
import os
import requests

LINKEDIN_VERSION = "202506"  # YYYYMM format, update periodically
API_BASE = "https://api.linkedin.com/rest"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


def _headers(access_token: str, content_type="application/json") -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_VERSION,
        "Content-Type": content_type,
    }


def refresh_access_token() -> str:
    """
    Uses the stored refresh token to get a new access token.
    Returns the new access token. Does NOT persist it automatically —
    caller should update .env or a secrets store if you want this to stick
    long-term (refresh tokens are valid ~365 days, access tokens ~60 days).
    """
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    refresh_token = os.getenv("LINKEDIN_REFRESH_TOKEN")

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    new_access_token = data["access_token"]
    os.environ["LINKEDIN_ACCESS_TOKEN"] = new_access_token  # update for this process
    print("LinkedIn access token refreshed. Consider updating your .env with the new value:")
    print(f"  LINKEDIN_ACCESS_TOKEN={new_access_token}")
    return new_access_token


def _upload_image(access_token: str, person_urn: str, image_path: str) -> str:
    """Registers + uploads an image, returns its image URN (urn:li:image:...)."""
    init_resp = requests.post(
        f"{API_BASE}/images?action=initializeUpload",
        headers=_headers(access_token),
        json={"initializeUploadRequest": {"owner": person_urn}},
        timeout=20,
    )
    init_resp.raise_for_status()
    value = init_resp.json()["value"]
    upload_url = value["uploadUrl"]
    image_urn = value["image"]

    with open(image_path, "rb") as f:
        put_resp = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {access_token}"},
            data=f.read(),
            timeout=60,
        )
    put_resp.raise_for_status()

    return image_urn


def _create_post(access_token: str, person_urn: str, post_text: str, image_urn: str | None) -> str:
    """Creates the post. Returns the post URN (from x-restli-id header)."""
    payload = {
        "author": person_urn,
        "commentary": post_text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if image_urn:
        payload["content"] = {"media": {"id": image_urn, "altText": "Post image"}}

    resp = requests.post(
        f"{API_BASE}/posts",
        headers=_headers(access_token),
        json=payload,
        timeout=20,
    )

    if resp.status_code == 401:
        # token expired mid-flow — refresh and retry once
        new_token = refresh_access_token()
        resp = requests.post(
            f"{API_BASE}/posts",
            headers=_headers(new_token),
            json=payload,
            timeout=20,
        )

    resp.raise_for_status()
    return resp.headers.get("x-restli-id", "")


def publish_post(post_text: str, image_path: str | None = None) -> str:
    """
    Main entry point. Publishes post_text (with optional image) to LinkedIn.
    Returns the resulting post URN.
    """
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    person_urn = os.getenv("LINKEDIN_PERSON_URN")
    if not access_token or not person_urn:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN / LINKEDIN_PERSON_URN not set in environment")

    image_urn = None
    if image_path and os.path.exists(image_path):
        try:
            image_urn = _upload_image(access_token, person_urn, image_path)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                access_token = refresh_access_token()
                image_urn = _upload_image(access_token, person_urn, image_path)
            else:
                raise

    post_urn = _create_post(access_token, person_urn, post_text, image_urn)
    print(f"Published. Post URN: {post_urn}")
    return post_urn


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    publish_post("This is a test post from my automation script.", image_path=None)
