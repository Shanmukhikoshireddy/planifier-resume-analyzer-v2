from pydantic import BaseModel, Field
class MinioObject(BaseModel):
    key: str = Field(..., alias="key")
    size: int | None = Field(default=0)

class MinioBucket(BaseModel):
    name: str = Field(..., alias="name")

class MinioS3(BaseModel):
    bucket: MinioBucket
    object: MinioObject

class MinioRecord(BaseModel):
    eventName: str
    s3: MinioS3

class MinioEvent(BaseModel):
    Records: list[MinioRecord]
    @property
    def record(self) -> MinioRecord:
        return self.Records[0]
    @property
    def bucket_name(self) -> str:
        return self.record.s3.bucket.name
    @property
    def object_name(self) -> str:
        return self.record.s3.object.key
    @property
    def event_name(self) -> str:
        return self.record.eventName
    @property
    def file_size(self) -> int:
        return self.record.s3.object.size