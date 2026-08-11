from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

try:
    from .costs import estimate_operation_cost
    from .maintenance_planner import MaintenanceDecision, plan_maintenance
    from .operations import ExecutionResult, execute_decision
    from .policy import PolicyResult, validate_decision
    from .table_health import TableHealth, TableIdentifier
    from .verification import VerificationResult, verify_execution
except ImportError:
    from costs import estimate_operation_cost
    from maintenance_planner import MaintenanceDecision, plan_maintenance
    from operations import ExecutionResult, execute_decision
    from policy import PolicyResult, validate_decision
    from table_health import TableHealth, TableIdentifier
    from verification import VerificationResult, verify_execution


class MaintenanceState(TypedDict, total=False):
    table_health: list[TableHealth | dict[str, Any]]
    decisions: list[MaintenanceDecision]
    policy_results: list[PolicyResult]
    execution_results: list[ExecutionResult]
    post_health: list[TableHealth]
    verification_results: list[VerificationResult]
    cost_estimates: list[dict[str, str]]
    collector: Any
    spark: Any
    model: Any | None


def planning_node(state: MaintenanceState) -> MaintenanceState:
    decisions = plan_maintenance(
        state["table_health"],
        model=state.get("model"),
    )
    return {**state, "decisions": sorted(decisions, key=lambda decision: decision.execution_order)}


def cost_node(state: MaintenanceState) -> MaintenanceState:
    health_by_table = _health_by_table(state["table_health"])
    cost_estimates = [
        estimate_operation_cost(
            health_by_table[_table_key(decision)],
            decision.operation,
        ).to_dict()
        for decision in state.get("decisions", [])
    ]
    return {**state, "cost_estimates": cost_estimates}


def validation_node(state: MaintenanceState) -> MaintenanceState:
    health_by_table = _health_by_table(state["table_health"])
    policy_results = [
        validate_decision(decision, health_by_table[_table_key(decision)])
        for decision in state.get("decisions", [])
    ]
    return {**state, "policy_results": policy_results}


def execution_node(state: MaintenanceState) -> MaintenanceState:
    spark = state.get("spark")
    if spark is None:
        execution_results = [
            ExecutionResult(
                catalog=result.catalog,
                namespace=result.namespace,
                table=result.table,
                operation=result.operation,
                status="SKIPPED",
                sql=None,
                message="No Spark session was provided to the maintenance graph.",
            )
            for result in state.get("policy_results", [])
        ]
        return {**state, "execution_results": execution_results}

    policy_by_table = {
        _table_key(result): result for result in state.get("policy_results", [])
    }
    execution_results = [
        execute_decision(spark, decision, policy_by_table[_table_key(decision)])
        for decision in state.get("decisions", [])
    ]
    return {**state, "execution_results": execution_results}


def post_health_node(state: MaintenanceState) -> MaintenanceState:
    collector = state.get("collector")
    if collector is None:
        return {**state, "post_health": []}

    post_health = []
    for execution in state.get("execution_results", []):
        if execution.status != "SUCCEEDED":
            continue
        post_health.append(
            collector.collect_table_health(
                TableIdentifier(
                    catalog=execution.catalog,
                    namespace=execution.namespace,
                    table=execution.table,
                )
            )
        )
    return {**state, "post_health": post_health}


def verification_node(state: MaintenanceState) -> MaintenanceState:
    before_by_table = _health_by_table(state["table_health"])
    after_by_table = _health_by_table(state.get("post_health", []))
    verification_results = []
    for execution in state.get("execution_results", []):
        key = _table_key(execution)
        verification_results.append(
            verify_execution(
                before_by_table[key],
                after_by_table.get(key),
                execution,
            )
        )
    return {**state, "verification_results": verification_results}


def build_maintenance_graph():
    graph = StateGraph(MaintenanceState)
    graph.add_node("plan", planning_node)
    graph.add_node("estimate_cost", cost_node)
    graph.add_node("validate", validation_node)
    graph.add_node("execute", execution_node)
    graph.add_node("collect_post_health", post_health_node)
    graph.add_node("verify", verification_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "estimate_cost")
    graph.add_edge("estimate_cost", "validate")
    graph.add_edge("validate", "execute")
    graph.add_edge("execute", "collect_post_health")
    graph.add_edge("collect_post_health", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


def run_maintenance_graph(
    table_health: list[TableHealth | dict[str, Any]],
    *,
    model: Any | None = None,
    collector: Any | None = None,
    spark: Any | None = None,
) -> MaintenanceState:
    result = build_maintenance_graph().invoke(
        {
            "table_health": table_health,
            "model": model,
            "collector": collector,
            "spark": spark,
        }
    )
    return result


def build_planning_graph():
    return build_maintenance_graph()


def run_planning_graph(
    table_health: list[TableHealth | dict[str, Any]],
    *,
    model: Any | None = None,
) -> list[MaintenanceDecision]:
    result = run_maintenance_graph(table_health, model=model)
    return result["decisions"]


def _table_key(value: Any) -> tuple[str, str, str]:
    if isinstance(value, dict):
        return (value["catalog"], value["namespace"], value["table"])
    return (value.catalog, value.namespace, value.table)


def _health_by_table(
    health_results: list[TableHealth | dict[str, Any]],
) -> dict[tuple[str, str, str], TableHealth | dict[str, Any]]:
    return {_table_key(health): health for health in health_results}
