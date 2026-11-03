"""Optional, staff-only Replicate integration. No provider-supplied API URLs are followed."""

import io
import json
import re
import time
from urllib.parse import urlsplit
import requests
from PIL import Image
from django.conf import settings


def bounded_response(session, method, url, limit, **kwargs):
    with session.request(
        method, url, timeout=(3, 10), allow_redirects=False, stream=True, **kwargs
    ) as response:
        if response.status_code not in (200, 201):
            raise ValueError("Provider request failed.")
        data = bytearray()
        started = time.monotonic()
        for chunk in response.iter_content(16384):
            data.extend(chunk)
            if len(data) > limit or time.monotonic() - started > 15:
                raise ValueError("Provider response exceeds time or size limits.")
        return bytes(data)


def generate_art(target, prompt):
    deadline = time.monotonic() + 60
    headers = {
        "Authorization": "Bearer " + settings.REPLICATE_API_TOKEN,
        "Cancel-After": "1m",
    }
    with requests.Session() as session:
        session.trust_env = False
        prediction = json.loads(
            bounded_response(
                session,
                "POST",
                "https://api.replicate.com/v1/predictions",
                65536,
                headers=headers,
                json={
                    "version": settings.REPLICATE_MODEL_VERSION,
                    "input": {"prompt": prompt, "qr_code_content": target},
                },
            )
        )
        prediction_id = prediction.get("id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", prediction_id):
            raise ValueError("Invalid prediction identifier.")
        while prediction.get("status") not in {"succeeded", "failed", "canceled"}:
            if time.monotonic() >= deadline:
                raise TimeoutError("Prediction did not complete in time.")
            time.sleep(1)
            prediction = json.loads(
                bounded_response(
                    session,
                    "GET",
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    65536,
                    headers=headers,
                )
            )
        if prediction.get("status") != "succeeded":
            raise ValueError("Prediction failed.")
        output = prediction.get("output")
        url = output[0] if isinstance(output, list) and output else output
        if not isinstance(url, str):
            raise ValueError("Missing image.")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "replicate.delivery"
            or parsed.port not in (None, 443)
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Unexpected image host.")
        image_bytes = bounded_response(session, "GET", url, 5 * 1024 * 1024)
    with Image.open(io.BytesIO(image_bytes)) as image:
        if image.width * image.height > 4_000_000:
            raise ValueError("Image dimensions are too large.")
        image.load()
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()
