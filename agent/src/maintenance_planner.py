from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langsmith.run_helpers import tracing_context

try:
    from .table_health import (
        ALLOWED_MAINTENANCE_OPERATIONS,
        EXPIRE_SNAPSHOTS,
        NO_ACTION,
        REMOVE_ORPHAN_FILES,
        REWRITE_DATA_FILES,
        REWRITE_MANIFESTS,
        REWRITE_POSITION_DELETE_FILES,
        TableHealth,
    )
except ImportError:
    from table_health import (
        ALLOWED_MAINTENANCE_OPERATIONS,
        EXPIRE_SNAPSHOTS,
        NO_ACTION,
        REMOVE_ORPHAN_FILES,
        REWRITE_DATA_FILES,
        REWRITE_MANIFESTS,
        REWRITE_POSITION_DELETE_FILES,
        TableHealth,
    )

DEFAULT_MODEL = "openai:gpt-5.5"
LANGSMITH_PROJECT = "iceberg-ops-agent"

PLANNER_SYSTEM_PROMPT = (
    "You are an Apache Iceberg and Apache Polaris maintenance planner. "
    "Reason about collected table-health metrics and decide which tables need "
    "maintenance. Do not execute operations. Return only machine-readable JSON. "
    "Prefer conservative, explainable decisions based on file counts, small-file "
    "ratio, delete files, snapshots, and the deterministic recommendation."
)


@dataclass(frozen=True)
class MaintenanceDecision:
    catalog: str
    namespace: str
    table: str
    operation: str
    priority: str
    confidence: float
    should_execute: bool
    rationale: str
    action: str
    validation: str
    execution_order: int = 1
    estimated_cost: str = "UNKNOWN"
    estimated_benefit: str = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_planning_prompt(table_health: list[TableHealth | dict[str, Any]]) -> str:
    payload = [health.to_dict() if isinstance(health, TableHealth) else health for health in table_health]
    return (
        "Review these Polaris-managed Iceberg table-health metrics and make a "
        "maintenance decision for each table.\n\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "decisions": [\n'
        "    {\n"
        '      "catalog": "lakehouse",\n'
        '      "namespace": "demo",\n'
        '      "table": "events",\n'
        f'      "operation": "{" | ".join(sorted(ALLOWED_MAINTENANCE_OPERATIONS))}",\n'
        '      "priority": "HIGH | MEDIUM | LOW",\n'
        '      "confidence": 0.0,\n'
        '      "should_execute": false,\n'
        '      "rationale": "short reason based on metrics",\n'
        '      "action": "concrete Polaris/Iceberg maintenance action or no-op",\n'
        '      "validation": "how to verify the decision after execution",\n'
        '      "execution_order": 1,\n'
        '      "estimated_cost": "LOW | MEDIUM | HIGH | UNKNOWN",\n'
        '      "estimated_benefit": "LOW | MEDIUM | HIGH | UNKNOWN"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        f"- Keep should_execute false for {NO_ACTION}.\n"
        "- Use the deterministic recommendation unless the metrics contradict it.\n"
        f"- For {REWRITE_DATA_FILES}, mention compaction with rewrite_data_files.\n"
        f"- For {REWRITE_MANIFESTS}, mention rewrite_manifests.\n"
        f"- For {EXPIRE_SNAPSHOTS}, mention snapshot expiration.\n"
        f"- For {REMOVE_ORPHAN_FILES}, mention remove_orphan_files and dry-run-first validation.\n"
        f"- For {REWRITE_POSITION_DELETE_FILES}, mention rewrite_position_delete_files.\n"
        "- Use execution_order when more than one operation is needed.\n"
        "- Estimate cost and benefit conservatively from the provided metrics.\n"
        "- Keep rationale and action concise.\n\n"
        f"Table health metrics:\n{json.dumps(payload, indent=2)}"
    )


def create_maintenance_planning_agent(model: Any | None = None):
    load_dotenv()
    return create_agent(
        model=_resolve_model(model),
        tools=[],
        system_prompt=PLANNER_SYSTEM_PROMPT,
    )


def _resolve_model(model: Any | None = None) -> Any:
    if model is not None:
        if isinstance(model, str) and not model.strip():
            return DEFAULT_MODEL
        return model

    env_model = os.getenv("OPENAI_MODEL")
    if env_model and env_model.strip():
        return env_model
    return DEFAULT_MODEL


def plan_maintenance(
    table_health: list[TableHealth | dict[str, Any]],
    *,
    model: Any | None = None,
) -> list[MaintenanceDecision]:
    agent = create_maintenance_planning_agent(model=model)
    with tracing_context(
        project_name=os.getenv("LANGSMITH_PROJECT", LANGSMITH_PROJECT),
        tags=["maintenance-planner", "iceberg", "polaris"],
        metadata={"table_count": len(table_health)},
    ):
        result = agent.invoke(
            {"messages": [{"role": "user", "content": build_planning_prompt(table_health)}]},
            config={"run_name": "plan_iceberg_table_maintenance"},
        )
    content = _message_content_to_text(result["messages"][-1].content)
    return parse_maintenance_decisions(content)


def parse_maintenance_decisions(content: str) -> list[MaintenanceDecision]:
    payload = json.loads(_extract_json_payload(content))
    decisions = payload["decisions"] if isinstance(payload, dict) else payload
    return [MaintenanceDecision(**decision) for decision in decisions]


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return str(content)


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_payload(content: str) -> str:
    stripped = _strip_json_fence(content)
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped

    object_start = stripped.find("{")
    array_start = stripped.find("[")
    starts = [index for index in (object_start, array_start) if index >= 0]
    if not starts:
        return stripped

    start = min(starts)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if end < start:
        return stripped
    return stripped[start : end + 1]
