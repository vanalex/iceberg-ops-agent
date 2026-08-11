import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) in sys.path:
        sys.path.remove(str(script_dir))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from agent.src.maintenance_graph import run_maintenance_graph
from agent.src.persistence import MaintenanceStore
from agent.src.table_health import TableHealthCollector, TableIdentifier
from agent.src.triggers import should_invoke_agent
from scripts.polaris_spark import create_spark_session, env, parse_table_specs


def main() -> None:
    catalog = env("CATALOG", "lakehouse")
    table_specs = parse_table_specs([])
    model = env("OPENAI_MODEL", "")
    database_path = env("MAINTENANCE_DB_PATH", "data/maintenance.db")
    adaptive_trigger_only = _env_bool("ADAPTIVE_TRIGGER_ONLY", default=False)
    spark = create_spark_session("plan-polaris-table-maintenance")

    try:
        collector = TableHealthCollector(spark, catalog)
        if table_specs:
            health_results = [
                collector.collect_table_health(
                    TableIdentifier(catalog=catalog, namespace=namespace, table=table)
                )
                for namespace, table in table_specs
            ]
        else:
            health_results = collector.scan()

        store = MaintenanceStore(database_path)
        previous_health = store.latest_health_payloads()
        store.save_health_observations(health_results)

        graph_input = health_results
        if adaptive_trigger_only:
            graph_input = [
                health
                for health in health_results
                if should_invoke_agent(
                    previous_health.get((health.catalog, health.namespace, health.table)),
                    health,
                )
            ]

        if graph_input:
            result = run_maintenance_graph(
                graph_input,
                model=model or None,
                collector=collector,
                spark=spark,
            )
        else:
            result = {
                "table_health": health_results,
                "decisions": [],
                "policy_results": [],
                "execution_results": [],
                "post_health": [],
                "verification_results": [],
                "cost_estimates": [],
            }

        store.save_decisions(result.get("decisions", []))
        store.save_policy_results(result.get("policy_results", []))
        store.save_execution_results(result.get("execution_results", []))
        store.save_health_observations(result.get("post_health", []))
        store.save_verification_results(result.get("verification_results", []))

        print(
            json.dumps(
                {
                    "decisions": [decision.to_dict() for decision in result.get("decisions", [])],
                    "policy_results": [
                        policy_result.to_dict()
                        for policy_result in result.get("policy_results", [])
                    ],
                    "execution_results": [
                        execution_result.to_dict()
                        for execution_result in result.get("execution_results", [])
                    ],
                    "verification_results": [
                        verification_result.to_dict()
                        for verification_result in result.get("verification_results", [])
                    ],
                    "cost_estimates": result.get("cost_estimates", []),
                },
                indent=2,
            )
        )
    finally:
        spark.stop()


def _env_bool(name: str, *, default: bool) -> bool:
    raw_value = env(name, "true" if default else "false")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
