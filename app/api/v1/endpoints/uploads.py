from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core import security
from app.core.s3_client import s3_client
from app.models.internal_model import User
from app.schemas.upload_schemas import FileUploadResponse

router = APIRouter()


@router.post(
    "/upload-airlink-image",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(security.get_current_user),
):
    """
    Uploads an image to S3 storage and returns its public URL.
    This is a generic endpoint that can be used for various image uploads,
    such as for Airlinks.

    Requires authentication and the user to be a merchant.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )

    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only images are allowed.",
        )

    try:
        file_url = s3_client.upload_file(file, folder="airlink-images")
        return {"url": file_url, "filename": file.filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )
