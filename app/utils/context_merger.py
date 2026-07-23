from copy import deepcopy


class ContextMerger:

    """
    Merges the previous parsed Job Description
    with the newly parsed Job Description.

    Existing values are preserved unless
    the new prompt explicitly updates them.
    """

    def merge(
        self,
        previous: dict,
        current: dict,
    ) -> dict:

        if not previous:
            return deepcopy(current)

        merged = deepcopy(previous)

        ####################################################
        # Simple Fields
        ####################################################

        for field in [
            "title",
            "education",
            "location",
        ]:

            value = current.get(field)

            if value not in [
                None,
                "",
                [],
                {},
            ]:
                merged[field] = value

        ####################################################
        # Experience
        ####################################################

        current_exp = current.get("experience") or {}
        merged_exp = deepcopy(merged.get("experience") or {})

        if current_exp.get("min") is not None:
            merged_exp["min"] = current_exp["min"]

        if current_exp.get("max") is not None:
            merged_exp["max"] = current_exp["max"]

        merged["experience"] = merged_exp
        
        ####################################################
        # Required Skills
        ####################################################

        merged["required_skills"] = self.merge_skill_objects(
            merged.get(
                "required_skills",
                [],
            ),
            current.get(
                "required_skills",
                [],
            ),
        )

        ####################################################
        # Preferred Skills
        ####################################################

        merged["preferred_skills"] = self.merge_skill_objects(
            merged.get(
                "preferred_skills",
                [],
            ),
            current.get(
                "preferred_skills",
                [],
            ),
        )

        ####################################################
        # Excluded Skills
        ####################################################

        merged["excluded_skills"] = self.merge_skill_objects(
            merged.get(
                "excluded_skills",
                [],
            ),
            current.get(
                "excluded_skills",
                [],
            ),
        )

        ####################################################
        # Certifications
        ####################################################

        merged["certifications"] = self.merge_strings(
            merged.get(
                "certifications",
                [],
            ),
            current.get(
                "certifications",
                [],
            ),
        )

        ####################################################
        # Responsibilities
        ####################################################

        merged["responsibilities"] = self.merge_strings(
            merged.get(
                "responsibilities",
                [],
            ),
            current.get(
                "responsibilities",
                [],
            ),
        )

        ####################################################
        # Qualifications
        ####################################################

        merged["qualifications"] = self.merge_strings(
            merged.get(
                "qualifications",
                [],
            ),
            current.get(
                "qualifications",
                [],
            ),
        )

        ####################################################
        # Nice To Have
        ####################################################

        merged["nice_to_have"] = self.merge_strings(
            merged.get(
                "nice_to_have",
                [],
            ),
            current.get(
                "nice_to_have",
                [],
            ),
        )

        ####################################################
        # Keywords
        ####################################################

        merged["keywords"] = self.merge_strings(
            merged.get(
                "keywords",
                [],
            ),
            current.get(
                "keywords",
                [],
            ),
        )

        return merged

    ####################################################
    # Merge Skill Objects
    ####################################################

    def merge_skill_objects(
        self,
        old: list,
        new: list,
    ):

        if not new:
            return old

        skill_map = {}

        for skill in old:

            key = skill.get(
                "skill",
                "",
            ).lower()

            skill_map[key] = skill

        for skill in new:

            key = skill.get(
                "skill",
                "",
            ).lower()

            skill_map[key] = skill

        return list(skill_map.values())

    ####################################################
    # Merge String Lists
    ####################################################

    def merge_strings(
        self,
        old: list,
        new: list,
    ):

        values = []

        seen = set()

        for item in old + new:

            if not item:
                continue

            key = str(item).lower()

            if key in seen:
                continue

            seen.add(key)

            values.append(item)

        return values