import logging

from django.conf import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024


class GeminiScannerError(Exception):
    """A safe, user-facing grocery scanner error."""


def scan_grocery_items(image_file):
    """Extract normalized grocery item names from an uploaded image."""
    from google import genai
    from google.genai import types

    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key or api_key in {"your-gemini-api-key", "your-api-key", "change-me"}:
        raise GeminiScannerError(
            "Gemini API key is not configured. Please set a valid GEMINI_API_KEY in your .env file."
        )

    mime_type = getattr(image_file, "content_type", "")
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise GeminiScannerError("Upload a JPEG, PNG, or WebP image.")

    if getattr(image_file, "size", 0) == 0:
        raise GeminiScannerError("The uploaded image is empty.")
    if image_file.size > MAX_IMAGE_SIZE:
        raise GeminiScannerError("The image must be 10 MB or smaller.")

    image_file.seek(0)
    image_bytes = image_file.read()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                (
                    "Read this handwritten or printed grocery list or grocery "
                    "product image. Extract only legible grocery product names "
                    "that a store inventory search could match. Ignore headings, "
                    "prices, totals, dates, quantities, and store branding. Do not "
                    "guess unreadable text. Return an empty items list if no grocery "
                    "products are legible."
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["items"],
                },
            ),
        )
        data = response.parsed
        if data is None:
            raise ValueError("Gemini returned no structured result")
        items = data.get("items", []) if isinstance(data, dict) else data.items
    except Exception as exc:
        logger.exception("Gemini grocery scanning failed")
        exc_str = str(exc).lower()
        status_code = getattr(exc, "status_code", None)
        if "api_key_invalid" in exc_str or "api key not valid" in exc_str or status_code in (400, 401, 403):
            if "api key" in exc_str or "api_key" in exc_str:
                raise GeminiScannerError(
                    "Invalid Gemini API key. Please check GEMINI_API_KEY in your .env file."
                ) from exc
        if status_code == 429:
            raise GeminiScannerError(
                "The scanner has reached its request limit. Please wait a minute and try again."
            ) from exc
        if status_code == 404:
            raise GeminiScannerError(
                "The configured Gemini model is unavailable. Please check GEMINI_MODEL in your .env file."
            ) from exc
        raise GeminiScannerError(
            f"Gemini grocery scanner error: {exc}"
        ) from exc

    normalized = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            continue
        name = " ".join(item.lower().split())
        if name and name not in seen:
            seen.add(name)
            normalized.append(name)
    return normalized
