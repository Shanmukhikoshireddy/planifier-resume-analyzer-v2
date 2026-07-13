from io import BytesIO
from minio.error import S3Error
from app.config.logging import logger
from app.config.minio import minio_client
from app.config.settings import settings
from datetime import timedelta

class MinioRepository:
    def __init__(self):
        self.client = minio_client
        self.bucket = settings.MINIO_BUCKET

    # Upload File
    def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:

        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_name,
            data=BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        logger.info(
            f"Uploaded : {object_name}"
        )
        return object_name

    # Download File
    def download_file(
        self,
        object_name: str,
    ) -> bytes:
        
        response = self.client.get_object(
            self.bucket,
            object_name,
        )
        try:
            file_bytes = response.read()
            logger.info(
                f"Downloaded : {object_name}"
            )
            return file_bytes
        finally:
            response.close()
            response.release_conn()

    # Get Object Metadata
    def get_object_info(
        self,
        object_name: str,
    ):
        return self.client.stat_object(
            self.bucket,
            object_name,
        )

    # File Exists
    def file_exists(
        self,
        object_name: str,
    ) -> bool:
        try:
            self.client.stat_object(
                self.bucket,
                object_name,
            )
            return True
        except S3Error:
            return False

    # Delete File
    def delete_file(
        self,
        object_name: str,
    ):
        self.client.remove_object(
            self.bucket,
            object_name,
        )
        logger.info(
            f"Deleted : {object_name}"
        )


    # Bucket Exists
    def bucket_exists(
        self,
    ) -> bool:
        return self.client.bucket_exists(
            self.bucket
        )

    # Get File Path
    def get_file_path(
            self,
            object_name: str,
        ) -> str:
            return f"{self.bucket}/{object_name}"
        

    # Get Presigned URL
    def get_presigned_url(
        self,
        object_path: str,
        download: bool = False,
    ):

        response_headers = None

        if download:

            response_headers = {

                "response-content-disposition": "attachment"

            }

        return self.client.presigned_get_object(

            self.bucket,

            object_path,

            expires=timedelta(hours=1),

            response_headers=response_headers,

        )
    # List Objects
    def list_objects(
        self,
        prefix: str | None = None,
    ):
        return list(
            self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=True,
            )
        )