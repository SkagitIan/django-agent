import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from ..models import LLMRun

load_dotenv()

class Orchestrator:
    @staticmethod
    def _get_plan_schema():
        return {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "op": {"type": "string"},
                            "app": {"type": "string"},
                            "model": {"type": "string"},
                            "fields": {"type": "array", "items": {"type": "string"}},
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                            "pattern": {"type": "string"},
                        },
                        "required": ["op"],
                    },
                }
            },
            "required": ["operations"],
        }

    @staticmethod
    def create_run(prompt: str, user) -> LLMRun:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        system_prompt = """
        You are a Django code architect.
        Analyze the following prompt and generate a plan of safe operations.
        Return JSON with operations list only.
        Allowed ops: create_app, add_model, add_view, add_template, add_url
        """

        full_prompt = f"{system_prompt}\n\nUser prompt: {prompt}"

        response = client.responses.create(
            model="gpt-4",
            input=full_prompt,
            text={"format": Orchestrator._get_plan_schema()},
        )

        plan_str = response.output[0].content[0].text
        plan = json.loads(plan_str)

        run = LLMRun.objects.create(prompt=prompt, plan=plan, requester=user)
        return run
