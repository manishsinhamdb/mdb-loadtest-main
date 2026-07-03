"""Unit tests for JSON data structures and validation.

Tests:
- atlas_metrics.json structure and completeness
- intent_templates.json structure and formulas
- metric_workload_map.json consistency
- hardware_profiles.json references
"""
import json
import os
from pathlib import Path

import pytest

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class TestAtlasMetrics:
    """Test atlas_metrics.json structure."""

    @pytest.fixture
    def metrics_data(self):
        with open(DATA_DIR / "atlas_metrics.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_exists(self, metrics_data):
        """Test metadata section exists with required fields."""
        assert "metadata" in metrics_data
        meta = metrics_data["metadata"]
        assert "version" in meta
        assert "total_metrics" in meta
        assert meta["version"] == "2.0.0"

    def test_categories_exist(self, metrics_data):
        """Test all 10 categories are present."""
        assert "categories" in metrics_data
        categories = metrics_data["categories"]
        assert len(categories) == 10

        expected_ids = [
            "hardware_system",
            "connections_network",
            "operations_opcounters",
            "query_performance",
            "cache_wiredtiger",
            "replication",
            "database_storage",
            "asserts_errors",
            "atlas_search",
            "process_server",
        ]

        actual_ids = [cat["id"] for cat in categories]
        for expected_id in expected_ids:
            assert expected_id in actual_ids, f"Missing category: {expected_id}"

    def test_metric_structure(self, metrics_data):
        """Test each metric has required fields."""
        required_fields = ["name", "unit", "description", "atlas_available", "ftdc_available"]

        total_metrics = 0
        for category in metrics_data["categories"]:
            for metric in category["metrics"]:
                total_metrics += 1
                for field in required_fields:
                    assert field in metric, f"Metric {metric.get('name', 'unknown')} missing field: {field}"

                # Validate types
                assert isinstance(metric["name"], str)
                assert isinstance(metric["unit"], str)
                assert isinstance(metric["atlas_available"], bool)
                assert isinstance(metric["ftdc_available"], bool)

        # Validate total count
        assert total_metrics == metrics_data["metadata"]["total_metrics"], \
            f"Metric count mismatch: {total_metrics} != {metrics_data['metadata']['total_metrics']}"

    def test_unique_metric_names(self, metrics_data):
        """Test metric names are unique across all categories."""
        names = []
        for category in metrics_data["categories"]:
            for metric in category["metrics"]:
                names.append(metric["name"])

        assert len(names) == len(set(names)), f"Duplicate metric names found: {set([n for n in names if names.count(n) > 1])}"

    def test_workload_references(self, metrics_data):
        """Test primary_workloads field contains valid workload keys."""
        valid_workloads = [
            "connection_storm",
            "indexed_reads",
            "unindexed_scans",
            "inmemory_sorts",
            "aggregation_pipelines",
            "write_bursts",
            "update_contention",
            "mixed_blend",
            "all",
            "",  # Empty list is valid
        ]

        for category in metrics_data["categories"]:
            for metric in category["metrics"]:
                if "primary_workloads" in metric:
                    for workload in metric["primary_workloads"]:
                        assert workload in valid_workloads, \
                            f"Invalid workload '{workload}' in metric {metric['name']}"


class TestIntentTemplates:
    """Test intent_templates.json structure."""

    @pytest.fixture
    def intents_data(self):
        with open(DATA_DIR / "intent_templates.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_exists(self, intents_data):
        """Test metadata section."""
        assert "metadata" in intents_data
        assert intents_data["metadata"]["version"] == "2.0.0"

    def test_all_intents_present(self, intents_data):
        """Test all 8 intents exist."""
        assert "intents" in intents_data
        intents = intents_data["intents"]

        expected_intents = [
            "connection_stress",
            "read_performance",
            "write_throughput",
            "aggregation_pipeline",
            "concurrency_contention",
            "cache_pressure",
            "mixed_production",
            "custom",
        ]

        for intent_id in expected_intents:
            assert intent_id in intents, f"Missing intent: {intent_id}"

    def test_intent_structure(self, intents_data):
        """Test each intent has required fields."""
        required_fields = [
            "id",
            "name",
            "description",
            "icon",
            "category",
            "workloads",
            "seeding_requirement",
            "primary_metrics",
            "secondary_metrics",
            "intensity_multipliers",
            "recommended_duration_seconds",
        ]

        for intent_id, intent in intents_data["intents"].items():
            for field in required_fields:
                assert field in intent, f"Intent {intent_id} missing field: {field}"

            # Test intensity multipliers
            assert "light" in intent["intensity_multipliers"]
            assert "medium" in intent["intensity_multipliers"]
            assert "heavy" in intent["intensity_multipliers"]
            assert "extreme" in intent["intensity_multipliers"]

    def test_workload_keys_valid(self, intents_data):
        """Test workload keys in intents match actual workload modules."""
        valid_workloads = [
            "connection_storm",
            "indexed_reads",
            "unindexed_scans",
            "inmemory_sorts",
            "aggregation_pipelines",
            "write_bursts",
            "update_contention",
            "mixed_blend",
        ]

        for intent_id, intent in intents_data["intents"].items():
            for workload_key in intent["workloads"].keys():
                assert workload_key in valid_workloads, \
                    f"Invalid workload key '{workload_key}' in intent {intent_id}"


class TestMetricWorkloadMap:
    """Test metric_workload_map.json consistency."""

    @pytest.fixture
    def map_data(self):
        with open(DATA_DIR / "metric_workload_map.json", "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def metrics_data(self):
        with open(DATA_DIR / "atlas_metrics.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_exists(self, map_data):
        """Test metadata section."""
        assert "metadata" in map_data
        assert map_data["metadata"]["version"] == "2.0.0"

    def test_mapping_structure(self, map_data):
        """Test mapping structure is valid."""
        assert "mappings" in map_data
        mappings = map_data["mappings"]

        for metric_name, workload_list in mappings.items():
            assert isinstance(workload_list, list), f"Mapping for {metric_name} is not a list"

            for mapping in workload_list:
                assert "workload" in mapping
                assert "impact" in mapping
                assert "confidence" in mapping

                # Validate confidence range
                assert 0.0 <= mapping["confidence"] <= 1.0, \
                    f"Invalid confidence {mapping['confidence']} for {metric_name}"

    def test_metrics_exist_in_atlas_catalog(self, map_data, metrics_data):
        """Test mapped metrics exist in atlas_metrics.json."""
        # Build list of all metric names
        all_metrics = set()
        for category in metrics_data["categories"]:
            for metric in category["metrics"]:
                all_metrics.add(metric["name"])

        # Check each mapped metric exists
        for metric_name in map_data["mappings"].keys():
            assert metric_name in all_metrics, \
                f"Metric {metric_name} in map not found in atlas_metrics.json"

    def test_workload_primary_metrics_consistency(self, map_data):
        """Test workload_primary_metrics section is consistent."""
        assert "workload_primary_metrics" in map_data

        for workload, metrics in map_data["workload_primary_metrics"].items():
            assert isinstance(metrics, list)
            assert len(metrics) > 0, f"Workload {workload} has no primary metrics"


class TestHardwareProfiles:
    """Test hardware_profiles.json structure."""

    @pytest.fixture
    def profiles_data(self):
        with open(DATA_DIR / "hardware_profiles.json", "r", encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_exists(self, profiles_data):
        """Test metadata section."""
        assert "metadata" in profiles_data
        assert profiles_data["metadata"]["version"] == "2.0.0"

    def test_client_profiles_exist(self, profiles_data):
        """Test client machine profiles."""
        assert "client_profiles" in profiles_data
        profiles = profiles_data["client_profiles"]

        required_fields = ["name", "cpu_cores", "ram_gb", "recommended_max_threads"]

        for profile_id, profile in profiles.items():
            for field in required_fields:
                assert field in profile, f"Profile {profile_id} missing field: {field}"

            # Validate types
            assert isinstance(profile["cpu_cores"], int)
            assert isinstance(profile["ram_gb"], (int, float))
            assert isinstance(profile["recommended_max_threads"], int)

    def test_atlas_tiers_exist(self, profiles_data):
        """Test MongoDB Atlas cluster tiers."""
        assert "mongodb_atlas_tiers" in profiles_data
        tiers = profiles_data["mongodb_atlas_tiers"]

        # Test known tiers exist
        known_tiers = ["M10", "M20", "M30", "M40", "M50", "M60"]
        for tier in known_tiers:
            assert tier in tiers, f"Missing Atlas tier: {tier}"

        # Test tier structure
        for tier_id, tier in tiers.items():
            assert "name" in tier
            assert "ram_gb" in tier
            assert "max_connections" in tier
            assert "suitable_for_loadtest" in tier

            # M10+ should be suitable for testing
            if tier_id.startswith("M") and tier_id != "M0" and tier_id != "M2" and tier_id != "M5":
                # Only dedicated tiers (M10+) should be suitable
                if tier["ram_gb"] != "Shared":
                    assert tier["suitable_for_loadtest"] is True, \
                        f"Tier {tier_id} should be suitable for load testing"

    def test_calculation_helpers_exist(self, profiles_data):
        """Test calculation helpers section."""
        assert "calculation_helpers" in profiles_data
        helpers = profiles_data["calculation_helpers"]

        assert "recommended_max_threads_formula" in helpers
        assert "thread_to_cpu_ratio" in helpers

        # Test thread_to_cpu_ratio has all intensities
        ratio = helpers["thread_to_cpu_ratio"]
        assert "light" in ratio
        assert "medium" in ratio
        assert "heavy" in ratio
        assert "extreme" in ratio


class TestDataConsistency:
    """Cross-file consistency tests."""

    @pytest.fixture
    def all_data(self):
        data = {}
        for filename in ["atlas_metrics.json", "intent_templates.json", "metric_workload_map.json", "hardware_profiles.json"]:
            with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
                data[filename] = json.load(f)
        return data

    def test_primary_metrics_in_intents_exist_in_catalog(self, all_data):
        """Test metrics referenced in intents exist in atlas_metrics.json."""
        # Build set of all metric names
        all_metrics = set()
        for category in all_data["atlas_metrics.json"]["categories"]:
            for metric in category["metrics"]:
                all_metrics.add(metric["name"])

        # Check each intent's primary/secondary metrics
        for intent_id, intent in all_data["intent_templates.json"]["intents"].items():
            for metric in intent["primary_metrics"]:
                assert metric in all_metrics, \
                    f"Metric {metric} in intent {intent_id} not found in atlas_metrics.json"

            for metric in intent["secondary_metrics"]:
                assert metric in all_metrics, \
                    f"Metric {metric} in intent {intent_id} not found in atlas_metrics.json"

    def test_workloads_in_map_match_intents(self, all_data):
        """Test workload keys in metric_workload_map match those in intents."""
        # Get ALL workload keys from ALL intents
        valid_workloads = set()
        for intent_id, intent in all_data["intent_templates.json"]["intents"].items():
            valid_workloads.update(intent["workloads"].keys())
        valid_workloads.add("all")  # Special case
        valid_workloads.add("none")  # Special case for errors

        # Check mappings
        for metric_name, mappings in all_data["metric_workload_map.json"]["mappings"].items():
            for mapping in mappings:
                workload = mapping["workload"]
                assert workload in valid_workloads, \
                    f"Unknown workload '{workload}' in mapping for {metric_name}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
