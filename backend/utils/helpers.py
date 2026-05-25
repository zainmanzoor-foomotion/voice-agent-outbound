"""
utils/helpers.py
----------------
Small reusable helper utilities used by multiple services and routes.
"""

import re
import unicodedata
from typing import Optional


# Simple E.164-ish phone validator: optional "+", 8 to 15 digits.
_PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")


def normalize_phone_number(raw: Optional[str]) -> Optional[str]:
    """
    Clean a phone number string and validate it.

    - Strips spaces, dashes, parentheses, and dots.
    - Returns a clean E.164-style string (with leading "+" if it had one).
    - Returns None if the number is invalid.

    Examples:
        "+1 (415) 555-0100"  ->  "+14155550100"
        "415-555-0100"       ->  "4155550100"   (still valid digits-only)
        "abc"                ->  None
    """
    if not raw:
        return None

    # Convert to string just in case pandas hands us a float (e.g. 1.234567e+10).
    cleaned = str(raw).strip()

    # Pandas may convert phone numbers into floats like "12345678900.0".
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]

    # Remove common separators.
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", cleaned)

    if not _PHONE_REGEX.match(cleaned):
        return None

    return cleaned


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Return True if the file extension is in the allowed list."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions


def safe_str(value, default: str = "") -> str:
    """Convert anything pandas may produce into a clean stripped string."""
    if value is None:
        return default
    try:
        text = str(value).strip()
    except Exception:
        return default
    if text.lower() in {"nan", "none", "null"}:
        return default
    return text


# Characters we allow through `secure_filename`. Everything else is dropped
# or replaced with an underscore.
_FILENAME_ASCII_STRIP_RE = re.compile(r"[^A-Za-z0-9_.-]")
_WINDOWS_DEVICE_FILES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def secure_filename(filename: str) -> str:
    """
    Return a safe version of an uploaded filename.

    Mirrors werkzeug.utils.secure_filename:
      - Strip directory components.
      - Normalize unicode to ASCII.
      - Replace spaces with underscores.
      - Allow only [A-Za-z0-9_.-]; everything else is removed.
      - Avoid reserved Windows device names.
      - Never return an empty string.
    """
    if not filename:
        return "file"

    # Normalize unicode (e.g. accented chars) to plain ASCII.
    filename = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )

    # Drop any path components — we never want directories in uploaded names.
    for sep in ("/", "\\"):
        filename = filename.replace(sep, " ")
    filename = "_".join(filename.split())

    # Strip anything not in our safe alphabet.
    filename = _FILENAME_ASCII_STRIP_RE.sub("", filename).strip("._-")

    # Avoid Windows reserved names like "CON", "PRN.txt", etc.
    if (
        filename
        and filename.split(".", 1)[0].upper() in _WINDOWS_DEVICE_FILES
    ):
        filename = f"_{filename}"

    return filename or "file"
