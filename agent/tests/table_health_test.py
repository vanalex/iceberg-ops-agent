from agent.src.table_health import TableHealthCollector


def test_recommends_data_file_rewrite_for_many_small_files() -> None:
    collector = TableHealthCollector(spark=None, catalog="lakehouse")

    recommendation = collector.recommend(
        snapshot_count=1,
        data_file_count=20,
        delete_file_count=0,
        small_file_ratio=0.80,
    )

    assert recommendation.operation == "REWRITE_DATA_FILES"
    assert recommendation.priority == "HIGH"


def test_recommends_no_action_when_thresholds_are_not_exceeded() -> None:
    collector = TableHealthCollector(spark=None, catalog="lakehouse")

    recommendation = collector.recommend(
        snapshot_count=1,
        data_file_count=1,
        delete_file_count=0,
        small_file_ratio=0.0,
    )

    assert recommendation.operation == "NO_ACTION"
    assert recommendation.priority == "LOW"


def test_recommends_position_delete_file_rewrite_for_many_delete_files() -> None:
    collector = TableHealthCollector(spark=None, catalog="lakehouse")

    recommendation = collector.recommend(
        snapshot_count=1,
        data_file_count=1,
        delete_file_count=20,
        small_file_ratio=0.0,
    )

    assert recommendation.operation == "REWRITE_POSITION_DELETE_FILES"
    assert recommendation.priority == "MEDIUM"


def test_recommends_manifest_rewrite_for_many_manifests() -> None:
    collector = TableHealthCollector(spark=None, catalog="lakehouse")

    recommendation = collector.recommend(
        snapshot_count=1,
        data_file_count=1,
        delete_file_count=0,
        small_file_ratio=0.0,
        manifest_count=200,
    )

    assert recommendation.operation == "REWRITE_MANIFESTS"
    assert recommendation.priority == "MEDIUM"


def test_recommends_orphan_file_cleanup_for_detected_orphans() -> None:
    collector = TableHealthCollector(spark=None, catalog="lakehouse")

    recommendation = collector.recommend(
        snapshot_count=1,
        data_file_count=1,
        delete_file_count=0,
        small_file_ratio=0.0,
        orphan_file_count=3,
    )

    assert recommendation.operation == "REMOVE_ORPHAN_FILES"
    assert recommendation.priority == "LOW"
