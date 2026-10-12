"""Semantic SEO Keyword Clustering and LSI Keyword Engine for Innovions."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum


class RotationStrategy(StrEnum):
    ROUND_ROBIN = "ROUND_ROBIN"
    RELEVANCE_WEIGHTED = "RELEVANCE_WEIGHTED"
    RANDOM = "RANDOM"


@dataclass
class KeywordCluster:
    name: str
    primary_keyword: str
    secondary_keywords: list[str]
    lsi_terms: list[str]
    category: str


# Semantic keyword clusters centered around Innovions RFID solutions
KEYWORD_CLUSTERS: list[KeywordCluster] = [
    KeywordCluster(
        name="Asset Tracking & Inventory",
        primary_keyword="RFID",
        secondary_keywords=[
            "RFID asset tracking",
            "automated inventory tracking",
            "real-time locating systems",
            "warehouse asset management",
        ],
        lsi_terms=["inventory audit", "tag scanning", "stock accuracy", "serial tracking"],
        category="enterprise",
    ),
    KeywordCluster(
        name="Industrial IoT & Smart Sensors",
        primary_keyword="RFID",
        secondary_keywords=[
            "Industrial IoT RFID",
            "smart RFID sensors",
            "wireless telemetry modules",
            "industrial automation telemetry",
        ],
        lsi_terms=["sensor network", "low-latency telemetry", "edge computing", "data capture"],
        category="technical",
    ),
    KeywordCluster(
        name="Supply Chain & Logistics Visibility",
        primary_keyword="RFID",
        secondary_keywords=[
            "RFID supply chain visibility",
            "smart logistics tracking",
            "freight transparency",
            "automated dispatch verification",
        ],
        lsi_terms=["dock door scanning", "pallet monitoring", "chain of custody", "in-transit tracking"],
        category="enterprise",
    ),
    KeywordCluster(
        name="Hardware Architecture & Protocols",
        primary_keyword="RFID",
        secondary_keywords=[
            "passive and active RFID readers",
            "UHF RFID tag technology",
            "high-frequency antenna arrays",
            "embedded reader architectures",
        ],
        lsi_terms=["signal attenuation", "reader sensitivity", "frequency spectrum", "tag memory"],
        category="technical",
    ),
    KeywordCluster(
        name="Enterprise Software & Analytics",
        primary_keyword="RFID",
        secondary_keywords=[
            "enterprise RFID middleware",
            "cloud RFID intelligence",
            "ERP asset synchronization",
            "operational asset analytics",
        ],
        lsi_terms=["API integration", "business dashboards", "automated reconciliations", "real-time alerts"],
        category="general",
    ),
]


class KeywordClusterManager:
    """Manages keyword rotation, LSI injection, and semantic cluster matching."""

    def __init__(self, strategy: RotationStrategy = RotationStrategy.RELEVANCE_WEIGHTED):
        self.strategy = strategy
        self.clusters = KEYWORD_CLUSTERS
        self._current_index = 0

    def select_cluster(self, platform_category: str = "general") -> KeywordCluster:
        """Selects a cluster according to the configured rotation strategy."""
        if self.strategy == RotationStrategy.RELEVANCE_WEIGHTED:
            matching = [c for c in self.clusters if c.category == platform_category]
            if matching:
                return random.choice(matching)
            return self.clusters[self._current_index % len(self.clusters)]

        elif self.strategy == RotationStrategy.ROUND_ROBIN:
            cluster = self.clusters[self._current_index % len(self.clusters)]
            self._current_index += 1
            return cluster

        else:  # RANDOM
            return random.choice(self.clusters)

    def get_variations_for_platform(self, platform_name: str, category: str = "general") -> dict:
        """Generates dynamic keyword bundle with primary keyword, secondary phrases, and LSI terms."""
        cluster = self.select_cluster(category)
        secondary = random.choice(cluster.secondary_keywords)
        lsi_sample = random.sample(cluster.lsi_terms, k=min(2, len(cluster.lsi_terms)))

        return {
            "primary": "RFID",
            "cluster_name": cluster.name,
            "secondary_phrase": secondary,
            "lsi_terms": lsi_sample,
            "all_tags": f"RFID, {secondary.replace(' ', '-')}, {', '.join(lsi_sample)}",
        }
