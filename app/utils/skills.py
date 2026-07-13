def normalize_skills(
    skills: list,
) -> list:

    normalized = []
    for skill in skills:
        skill = (
            skill
            .strip()
            .lower()
        )

        if skill not in normalized:
            normalized.append(
                skill
            )
    return normalized