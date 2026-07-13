from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
}

def is_supported_resume(
    file_name: str,
) -> bool:
    return (
        Path(file_name)
        .suffix
        .lower()
        in SUPPORTED_EXTENSIONS
    )

def get_extension(
    file_name: str,
) -> str:
    return (
        Path(file_name)
        .suffix
        .lower()
    )