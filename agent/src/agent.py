import json
import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent

DEFAULT_MODEL = "openai:gpt-5.5"

SYSTEM_PROMPT = (
    "You are an expert Apache Iceberg and Apache Polaris operations assistant. "
    "Analyze table maintenance recommendations and return concrete, safe, "
    "operator-ready actions for Polaris-managed Iceberg tables. Prefer actions "
    "that include the maintenance operation, execution timing, validation steps, "
    "and any operational caution needed to avoid disrupting writers."
)


def build_maintenance_prompt(analysis_result: dict[str, Any]) -> str:
    return (
        "Analyze this Apache Iceberg table maintenance recommendation and give "
        "one concrete action to operate on Polaris and maintain tables correctly.\n\n"
        f"Recommendation:\n{json.dumps(analysis_result, indent=2)}"
    )


def create_iceberg_ops_agent(model: str | None = None):
    load_dotenv()
    return create_agent(
        model=model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )


def analyze_maintenance_recommendation(
    analysis_result: dict[str, Any],
    *,
    model: str | None = None,
) -> str:
    agent = create_iceberg_ops_agent(model=model)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": build_maintenance_prompt(analysis_result)}]}
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    recommendation = {
        "operation": "REWRITE_DATA_FILES",
        "reason": "The table contains a very high percentage of small files.",
        "priority": "HIGH",
        "confidence": 0.94,
    }
    print(analyze_maintenance_recommendation(recommendation))
