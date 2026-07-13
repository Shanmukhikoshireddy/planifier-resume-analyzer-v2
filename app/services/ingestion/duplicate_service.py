from app.repository.profile_repository import ProfileRepository

class DuplicateService:
    """
    Responsible for duplicate resume detection.
    """
    def __init__(self):
        self.profile_repository = ProfileRepository()

    # Check Duplicate Resume
    def is_duplicate(
        self,
        file_hash: str,
    ) -> bool:
        return self.profile_repository.resume_exists(
            file_hash
        )

    # Validate Before Processing
    def validate(
        self,
        file_hash: str,
    ):
        if self.is_duplicate(
            file_hash
        ):
            raise ValueError(
                "Duplicate resume found."
            )