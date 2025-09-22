import uuid

import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import UploadFile

from app.core.config import settings


class S3Client:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    def upload_file(self, file: UploadFile, folder: str = "images") -> str:
        """
        Uploads a file to an S3 bucket and returns the public URL.

        :param file: The file to upload (FastAPI UploadFile).
        :param folder: The folder within the bucket to upload to.
        :return: The URL of the uploaded file.
        """
        try:
            # Generate a unique filename to prevent overwrites
            file_extension = (
                file.filename.split(".")[-1] if "." in file.filename else ""
            )
            object_name = f"{folder}/{uuid.uuid4()}.{file_extension}"

            self.client.upload_fileobj(
                file.file,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": file.content_type, "ACL": "public-read"},
            )

            if settings.S3_ENDPOINT_URL:
                return f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{object_name}"

            region = self.client.meta.region_name or "us-east-1"
            return f"https://{self.bucket_name}.s3.{region}.amazonaws.com/{object_name}"

        except NoCredentialsError as e:
            raise Exception("S3 credentials not available") from e
        except Exception as e:
            raise Exception(f"Error uploading to S3: {e}") from e


s3_client = S3Client()
