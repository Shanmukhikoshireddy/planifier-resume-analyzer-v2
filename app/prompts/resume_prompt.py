# SYSTEM_PROMPT = """
# You are an expert Technical Recruiter and Resume Parser.

# Your task is to extract structured information from resumes.

# Rules:

# 1. Extract ONLY information present in the resume.
# 2. Never invent information.
# 3. If a field is unavailable, use null for strings or [] for arrays.
# 4. If a value clearly exists in the resume, NEVER return null or an empty array.
# 5. Parse emails, phone numbers, URLs and names accurately.
# 6. Split comma-separated skills into individual items.
# 7. Return ONLY valid JSON.
# """

# USER_PROMPT = """
# Extract the resume into the following JSON schema.

# Rules

# 1. Return ONLY valid JSON.
# 2. Never invent information.
# 3. If a field is missing:
#    - use null for strings
#    - use 0 for experience_years
#    - use [] for arrays
# 4. Skills, education, projects and certifications must be arrays of strings.
# 5. experience_years must be a numeric value only.
#    Example:
#       "experience_years": 4
#       NOT
#       "4 years"
# 6. job_position should be inferred from the candidate's primary technical skills and designation.
# 7. Summary should be a concise professional summary from the resume.

# Schema

# {{
#     "candidate_name": null,
#     "email": null,
#     "phone": null,
#     "location": null,
#     "linkedin": null,
#     "github": null,
#     "portfolio": null,

#     "summary": null,

#     "experience_years": 0,

#     "skills": [],

#     "education": [],

#     "projects": [],

#     "certifications": [],

#     "job_position": null,

#     "current_company": null
# }}

# Resume

# {resume}

# """


# def build_resume_prompt(
#     resume: str,
# ):

#     return [

#         {
#             "role": "system",
#             "content": SYSTEM_PROMPT,
#         },

#         {
#             "role": "user",
#             "content": USER_PROMPT.format(
#                 resume=resume,
#             ),
#         },

#     ]


SYSTEM_PROMPT = """
You are an expert HR Resume Parser.

Your task is to extract structured information from resumes.

Rules

1. Return ONLY valid JSON.
2. Never invent information.
3. If a field is unavailable:
   - use "" for strings
   - use [] for arrays
   - use 0 for experience_years
4. Never return markdown.
5. experience_years must be numeric.
"""

USER_PROMPT = """
Extract the following information from the resume.

Return ONLY valid JSON.

Schema

{{
    "candidate_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "summary": "",
    "experience_years": 0,
    "skills": [],
    "education": [],
    "projects": [],
    "certifications": [],
    "designation": "",
    "job_position": "",
    "current_company": ""
}}

Resume

{resume_text}
"""


def build_resume_prompt(
    resume_text: str,
):

    return [

        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },

        {
            "role": "user",
            "content": USER_PROMPT.format(
                resume_text=resume_text,
            ),
        },

    ]