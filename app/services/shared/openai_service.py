import json
import time
from openai import OpenAI
from app.config.settings import settings
from app.config.logging import logger

class OpenAIService:
    def __init__(self):
        logger.info("Initializing OpenAI...")
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
        self.model = settings.OPENAI_MODEL
        logger.info(
            f"OpenAI Model : {self.model}"
        )
    def generate(
        self,
        messages,
    ) -> str:
        try:
            for attempt in range(3):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                    )
                    content = response.choices[0].message.content
                    return content.strip()
                except Exception as e:
                    logger.warning(
                        f"OpenAI attempt {attempt + 1} failed."
                    )
                    logger.exception(e)
                    if attempt == 2:
                        raise
                    time.sleep(5)
        except Exception as e:
            logger.exception(e)
            raise
    def generate_json(
        self,
        messages,
    ) -> dict:
        response = self.generate(messages)
        response = response.strip()
        if response.startswith("```"):
            response = response.replace("```json", "")
            response = response.replace("```", "")
            response = response.strip()
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            response = response[start:end + 1]
        try:
            parsed = json.loads(response)
            return parsed
        except json.JSONDecodeError as e:
            logger.error("OpenAI returned invalid JSON.")
            logger.error(response)
            logger.exception(e)
            raise ValueError("Invalid JSON returned by OpenAI.")

    # Health Check
    def health_check(self) -> bool:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": "Reply with exactly OK."
                    }
                ],
            )

            text = response.choices[0].message.content.strip()

            logger.info(f"Health Check Response: {text}")

            return text.upper() == "OK"

        except Exception as e:
            logger.exception("OpenAI Health Check Failed")
            return False