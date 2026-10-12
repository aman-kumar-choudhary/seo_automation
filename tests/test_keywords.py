import pytest
from content.keywords import (
    KeywordClusterManager,
    RotationStrategy,
    KEYWORD_CLUSTERS,
    KeywordCluster,
)


def test_keyword_clusters_defined():
    assert len(KEYWORD_CLUSTERS) >= 5
    for cluster in KEYWORD_CLUSTERS:
        assert cluster.primary_keyword == "RFID"
        assert len(cluster.secondary_keywords) >= 2
        assert len(cluster.lsi_terms) >= 2
        assert cluster.category in ("enterprise", "technical", "general")


def test_rotation_strategy_round_robin():
    mgr = KeywordClusterManager(strategy=RotationStrategy.ROUND_ROBIN)
    cluster1 = mgr.select_cluster()
    cluster2 = mgr.select_cluster()
    assert cluster1.name != cluster2.name


def test_rotation_strategy_relevance_weighted():
    mgr = KeywordClusterManager(strategy=RotationStrategy.RELEVANCE_WEIGHTED)
    cluster = mgr.select_cluster("technical")
    assert cluster.category == "technical"

    cluster_ent = mgr.select_cluster("enterprise")
    assert cluster_ent.category == "enterprise"


def test_get_variations_for_platform():
    mgr = KeywordClusterManager(strategy=RotationStrategy.ROUND_ROBIN)
    var = mgr.get_variations_for_platform("reddit.com", "technical")
    assert var["primary"] == "RFID"
    assert "cluster_name" in var
    assert "secondary_phrase" in var
    assert len(var["lsi_terms"]) >= 1
    assert "RFID" in var["all_tags"]
