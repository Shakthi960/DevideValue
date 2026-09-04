import os
import uuid
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    UploadFile,
    HTTPException
)

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.supabase import supabase

from app.models.inspection import Inspection
from app.models.inspection_photo import InspectionPhoto


router = APIRouter(
    prefix="/api/inspections",
    tags=["Photos"]
)


BUCKET_NAME = "device-inspections"


ALLOWED_PHOTO_TYPES = {
    "front",
    "back",
    "left",
    "right",
    "top",
    "bottom"
}


ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp"
}


@router.post(
    "/{inspection_code}/photos"
)
async def upload_inspection_photo(
    inspection_code: str,
    photo_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    # -------------------------
    # Validate photo type
    # -------------------------

    if photo_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid photo type. "
                "Use front, back, left, right, "
                "top or bottom."
            )
        )


    # -------------------------
    # Validate file type
    # -------------------------

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG and WebP images are allowed."
        )


    # -------------------------
    # Find inspection
    # -------------------------

    inspection = (
        db.query(Inspection)
        .filter(
            Inspection.inspection_code
            == inspection_code
        )
        .first()
    )


    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="Inspection not found"
        )


    # -------------------------
    # Read file
    # -------------------------

    file_bytes = await file.read()


    # 6 MB limit
    max_size = 6 * 1024 * 1024

    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=400,
            detail="Image must be smaller than 6 MB."
        )


    # -------------------------
    # Generate unique path
    # -------------------------

    extension = "jpg"

    if file.content_type == "image/png":
        extension = "png"

    elif file.content_type == "image/webp":
        extension = "webp"


    unique_name = (
        f"{photo_type}_"
        f"{uuid.uuid4().hex}."
        f"{extension}"
    )


    storage_path = (
        f"{inspection_code}/{unique_name}"
    )


    # -------------------------
    # Upload to Supabase
    # -------------------------

    try:

        supabase.storage \
            .from_(BUCKET_NAME) \
            .upload(
                storage_path,
                file_bytes,
                {
                    "content-type":
                        file.content_type,
                    "cache-control":
                        "3600",
                    "upsert":
                        "false"
                }
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Storage upload failed: {str(e)}"
        )


    # -------------------------
    # Save metadata
    # -------------------------

    photo = InspectionPhoto(
        inspection_id=inspection.id,
        photo_type=photo_type,
        storage_path=storage_path,
        content_type=file.content_type,
        created_at=datetime.now().isoformat()
    )


    db.add(photo)

    db.commit()

    db.refresh(photo)


    return {
        "message": "Photo uploaded successfully",
        "photo_id": photo.id,
        "inspection_code": inspection_code,
        "photo_type": photo_type,
        "storage_path": storage_path
    }