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

from agent.src.table_health import TableHealthCollector, TableIdentifier
from scripts.polaris_spark import create_spark_session, env, parse_table_specs


def main() -> None:
    catalog = env("CATALOG", "lakehouse")
    table_specs = parse_table_specs([])
    spark = create_spark_session("collect-polaris-table-health")

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

        print(json.dumps([health.to_dict() for health in health_results], indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
