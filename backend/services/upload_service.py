"""
services/upload_service.py
--------------------------
CSV / XLSX parsing and client ingestion.

Pandas does the heavy lifting; we just normalize column names,
validate phone numbers, and write Client rows to the database.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd
from sqlalchemy.orm import Session

from models import Client
from utils.helpers import normalize_phone_number, safe_str
from utils.logger import get_logger


logger = get_logger("upload_service")


# Map "messy" header variants to our canonical column names.
_COLUMN_ALIASES = {
    "name": {"name", "full_name", "client_name", "customer_name", "contact"},
    "phone_number": {
        "phone_number", "phone", "phonenumber", "mobile", "mobile_number",
        "number", "contact_number", "cell",
    },
    "company": {"company", "organization", "org", "business", "company_name"},
    "email": {"email", "email_address", "mail"},
}


def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to our canonical names regardless of input casing/spelling."""
    rename_map = {}
    for col in df.columns:
        key = str(col).strip().lower().replace(" ", "_")
        for canonical, aliases in _COLUMN_ALIASES.items():
            if key in aliases:
                rename_map[col] = canonical
                break
    return df.rename(columns=rename_map)


def process_upload(db: Session, file_path: Path) -> Dict:
    """
    Read a CSV/XLSX file from disk, parse rows, and insert Client records.

    Returns a small report dict:
        {
            "total_rows": int,
            "inserted": int,
            "skipped_invalid_phone": int,
            "skipped_duplicate": int,
            "errors": [str, ...],
        }
    """
    report = {
        "total_rows": 0,
        "inserted": 0,
        "skipped_invalid_phone": 0,
        "skipped_duplicate": 0,
        "errors": [],
    }

    # --- Read file via pandas ---
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        elif suffix == ".xlsx":
            df = pd.read_excel(file_path, dtype=str, engine="openpyxl")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    except Exception as exc:
        logger.exception("Failed to read uploaded file: %s", exc)
        report["errors"].append(f"Could not read file: {exc}")
        return report

    df = _normalize_headers(df)
    report["total_rows"] = len(df)

    if "phone_number" not in df.columns:
        report["errors"].append(
            "File must contain a 'phone_number' column (or alias like 'phone'/'mobile')."
        )
        return report

    # --- Pre-load existing phone numbers to detect duplicates quickly ---
    existing_phones = {row[0] for row in db.query(Client.phone_number).all()}

    new_clients: List[Client] = []

    for _, row in df.iterrows():
        raw_phone = row.get("phone_number")
        phone = normalize_phone_number(raw_phone)

        if not phone:
            report["skipped_invalid_phone"] += 1
            continue

        if phone in existing_phones:
            report["skipped_duplicate"] += 1
            continue

        client = Client(
            name=safe_str(row.get("name")),
            phone_number=phone,
            company=safe_str(row.get("company")),
            email=safe_str(row.get("email")),
        )
        new_clients.append(client)
        existing_phones.add(phone)

    if new_clients:
        try:
            db.add_all(new_clients)
            db.commit()
            report["inserted"] = len(new_clients)
        except Exception as exc:
            db.rollback()
            logger.exception("Failed to insert clients: %s", exc)
            report["errors"].append(f"Database error: {exc}")

    logger.info("Upload processed: %s", report)
    return report
