import json

SYSTEM_PROMPT = """
You are an experienced Technical Recruiter.

Your task is to analyze how well a candidate matches a job description.

Rules

1. Use ONLY the provided Job Requirements and Candidate Profile.
2. Never invent information.
3. If a required skill is missing, mention it.
4. If experience is insufficient, mention it.
5. Keep the explanation concise and professional.
6. Return plain text only.
"""
USER_PROMPT = """
Job Requirements
{job}
Candidate Profile
{candidate}
Provide the following analysis:
1. Overall Match Summary
2. Candidate Strengths
3. Matching Skills
4. Missing Skills
5. Experience Match
6. Education Match
7. Certifications
8. Final Recommendation
Keep the explanation within 8-10 short bullet points.
"""

def build_reasoning_prompt(
    job: dict,
    candidate: dict,
):
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": USER_PROMPT.format(
                job=json.dumps(
                    job,
                    indent=2,
                ),
                candidate=json.dumps(
                    candidate,
                    indent=2,
                ),
            ),
        },
    ]