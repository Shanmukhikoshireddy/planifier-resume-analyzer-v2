import re

def extract_years(
    experience: str,
) -> float:
    if not experience:
        return 0
    match = re.search(
        r"\d+(\.\d+)?",
        experience,
    )
    if match:
        return float(
            match.group()
        )
    return 0