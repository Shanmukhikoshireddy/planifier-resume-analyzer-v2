SYSTEM_PROMPT = """
You are an experienced Technical Recruiter.

Your task is to analyze a Job Description and extract structured hiring requirements.

Rules

1. Return ONLY valid JSON.
2. Never invent information.
3. If a field is unavailable:
   - use "" for strings
   - use [] for arrays
4. Extract the required experience exactly as a number or range.
5. Split comma-separated skills into individual items.
6. Remove duplicate skills.
"""


USER_PROMPT = """
Analyze the following Job Description.

Return ONLY valid JSON.

Schema

{{
    "title": "",

    "experience": "",

    "education": "",

    "skills": [],

    "certifications": [],

    "responsibilities": [],

    "qualifications": [],

    "nice_to_have": []
}}

Rules

experience examples

"0"

"2"

"5"

"2-4"

"5+"

education example

"B.Tech Computer Science"

skills

Return only technologies and technical skills.

certifications

Return only certification names.

Job Description

{job_description}
"""


def build_job_prompt(
    job_description: str,
):

    return [

        {

            "role": "system",

            "content": SYSTEM_PROMPT,

        },

        {

            "role": "user",

            "content": USER_PROMPT.format(

                job_description=job_description,

            ),

        },

    ]