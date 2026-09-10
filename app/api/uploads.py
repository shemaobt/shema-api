from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.upload import ImageUploadResponse
from app.services.storage import upload_image

router = APIRouter()


@router.post("/image", response_model=ImageUploadResponse)
async def upload_image_endpoint(
    file: UploadFile,
    folder: str = "images",
    _: User = Depends(get_current_user),
) -> ImageUploadResponse:
    if folder not in ("app-icons", "avatars", "project-images", "images"):
        folder = "images"
    try:
        url = await upload_image(file, folder=folder)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ImageUploadResponse(url=url)
