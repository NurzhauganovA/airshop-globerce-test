from pydantic import BaseModel, HttpUrl


class FileUploadResponse(BaseModel):
    url: HttpUrl
    filename: str
