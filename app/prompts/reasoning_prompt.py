import json

SYSTEM_PROMPT = """
You are an expert Technical Recruiter and Hiring Manager.

Your responsibility is to explain WHY a candidate matches a job requirement.

Rules:

1. Use ONLY the provided Job Requirements and Candidate Profile.
2. Never invent information.
3. Mention matching required skills.
4. Mention matching preferred skills if available.
5. Mention missing required skills.
6. Mention education only if available.
7. Mention certifications only if available.
8. Mention relevant projects if available.
9. Mention relevant professional summary if available.
10. Mention experience comparison.
11. Explain the ATS score using the supplied score information.
12. Give a concise recruiter recommendation.
13. Return plain text only.
"""

USER_PROMPT = """
Job Requirements
================
{job}

Candidate Profile
=================
{candidate}

Provide the reasoning in the following format.

1. Overall Match Summary
- Explain why this candidate matches the job.

2. Technical Skills
- Matching required skills
- Matching preferred skills
- Missing required skills

3. Experience Match
- Compare candidate experience with required experience.

4. Education
- Explain whether education satisfies the requirement.

5. Certifications
- Mention matching certifications.
- Mention if certifications are unavailable.

6. Projects & Professional Summary
- Mention relevant projects.
- Mention relevant professional summary.

7. ATS Evaluation
Include:
- Final Score
- Skill Match Percentage
- Match Level

Briefly explain why the score is high or low.

8. Recruiter Recommendation

Conclude with one of:

Strongly Recommended

Recommended

Consider with Reservations

Not Recommended

Keep the response professional and concise (8–12 bullet points).
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
                    ensure_ascii=False,
                ),
                candidate=json.dumps(
                    candidate,
                    indent=2,
                    ensure_ascii=False,
                ),
            ),
        },
    ]