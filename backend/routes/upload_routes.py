"""
routes/upload_routes.py
-----------------------
File upload endpoint: ingest a CSV/XLSX into the Client table.
"""

import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import Config
from database import get_db
from services.upload_service import process_upload
from utils.helpers import allowed_file, secure_filename
from utils.logger import get_logger


logger = get_logger("upload_routes")

router = APIRouter()


@router.post("/upload-clients")
async def upload_clients(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accept a multipart 'file' field and ingest it.

    Request:
        multipart/form-data
            file: <CSV or XLSX>

    Response (200):
        {
            "success": true,
            "report": { ... },
            "filename": "uploaded_file.csv"
        }
    """
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not allowed_file(file.filename, Config.ALLOWED_UPLOAD_EXTENSIONS):
        # Return a JSON body matching the old Flask shape so the React UI
        # keeps working unchanged.
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Only .csv and .xlsx files are supported.",
            },
        )

    # Save the file to disk with a unique name so the original is preserved.
    upload_dir: Path = Config.UPLOAD_FOLDER
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(file.filename)
    stamped_name = f"{int(time.time())}_{safe_name}"
    save_path = upload_dir / stamped_name

    try:
        contents = await file.read()
        save_path.write_bytes(contents)
    except Exception as exc:
        logger.exception("Failed to save uploaded file: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Could not save file."},
        )

    report = process_upload(db, save_path)

    return {
        "success": True,
        "report": report,
        "filename": stamped_name,
    }
