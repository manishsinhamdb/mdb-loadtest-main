"""Integration tests for V2 features.

Tests the full flow: hardware discovery → intent calculation → validation.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hardware_discovery import HardwareDiscovery
from core.intent_engine import IntentEngine
from core.workload_optimizer import WorkloadOptimizer
from core.resource_validator import ResourceValidator


def test_hardware_discovery():
    """Test hardware discovery on current machine."""
    print("🧪 Test: Hardware Discovery")

    hw = HardwareDiscovery.get_full_profile()

    assert hw is not None, "Hardware profile should not be None"
    assert "summary" in hw, "Should have summary"
    assert "cpu_cores" in hw["summary"], "Should have CPU cores"
    assert hw["summary"]["cpu_cores"] > 0, "CPU cores should be positive"

    print(f"  ✅ Detected: {hw['summary']['cpu_cores']} cores, {hw['summary']['ram_gb']:.1f} GB RAM")
    return hw


def test_intent_calculation(client_hw):
    """Test intent engine calculation."""
    print("\n🧪 Test: Intent Calculation")

    engine = IntentEngine()

    # Test read_performance intent
    config = engine.calculate_configuration(
        intent_id="read_performance",
        intensity="medium",
        duration_seconds=600,
        data_size=None,
        concurrency_level=10,
        client_hardware=client_hw,
        server_hardware={"vcpus": 16, "ram_gb": 40, "max_connections": 3200}
    )

    assert config is not None, "Config should not be None"
    assert "workloads" in config, "Should have workloads"
    assert "indexed_reads" in config["workloads"], "Should have indexed_reads workload"

    print(f"  ✅ Calculated config:")
    print(f"     - Intent: {config['intent_id']} @ {config['intensity']}")
    print(f"     - Workloads: {list(config['workloads'].keys())}")

    return config


def test_workload_optimization(config, client_hw):
    """Test workload optimizer."""
    print("\n🧪 Test: Workload Optimization")

    limits = {
        "max_threads": ResourceValidator.max_threads(client_hw["summary"]["cpu_cores"]),
        "max_connections": 2560,
    }

    optimized = WorkloadOptimizer.optimize_configuration(
        config,
        client_hw,
        {"vcpus": 16, "ram_gb": 40},
        limits
    )

    assert optimized is not None, "Optimized config should not be None"

    total_threads = sum(w.get("threads", 0) for w in optimized["workloads"].values())
    print(f"  ✅ Optimized: {total_threads} total threads (limit: {limits['max_threads']})")

    return optimized


def test_resource_validation(config, client_hw):
    """Test resource validator."""
    print("\n🧪 Test: Resource Validation")

    validation = ResourceValidator.validate_configuration(
        config,
        client_hw,
        {"vcpus": 16, "ram_gb": 40, "max_connections": 3200},
        allow_overrides=False
    )

    assert validation is not None, "Validation result should not be None"
    assert "ok" in validation, "Should have ok field"
    assert "warnings" in validation, "Should have warnings field"

    print(f"  ✅ Validation: {'PASS' if validation['ok'] else 'FAIL'}")
    print(f"     - Warnings: {len(validation['warnings'])}")
    if validation['warnings']:
        for warning in validation['warnings'][:3]:
            print(f"       • {warning}")

    return validation


def test_all_intents():
    """Test all 8 intents."""
    print("\n🧪 Test: All Intents")

    engine = IntentEngine()
    intents = engine.list_intents()

    assert len(intents) >= 8, f"Should have at least 8 intents, got {len(intents)}"

    print(f"  ✅ Found {len(intents)} intents:")
    for intent in intents[:8]:
        print(f"     - {intent}")

    # Test each intent can be calculated
    client_hw = {"summary": {"cpu_cores": 12, "ram_gb": 24.0}}
    server_hw = {"vcpus": 16, "ram_gb": 40, "max_connections": 3200}

    for intent_id in ["connection_stress", "read_performance", "write_throughput"]:
        try:
            config = engine.calculate_configuration(
                intent_id, "medium", 600, None, 10, client_hw, server_hw
            )
            assert config is not None
            print(f"  ✅ {intent_id}: OK")
        except Exception as e:
            print(f"  ❌ {intent_id}: {e}")
            raise


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n🧪 Test: Edge Cases")

    engine = IntentEngine()

    # Test with minimal hardware
    minimal_hw = {"summary": {"cpu_cores": 2, "ram_gb": 4.0}}
    server_hw = {"vcpus": 4, "ram_gb": 8, "max_connections": 500}

    config = engine.calculate_configuration(
        "read_performance", "light", 60, None, 1, minimal_hw, server_hw
    )

    assert config is not None
    total_threads = sum(w.get("threads", 0) for w in config["workloads"].values())
    assert total_threads > 0, "Should have at least some threads"

    print(f"  ✅ Minimal hardware: {total_threads} threads calculated")

    # Test extreme intensity
    heavy_config = engine.calculate_configuration(
        "read_performance", "extreme", 600, None, 10,
        {"summary": {"cpu_cores": 12, "ram_gb": 24.0}},
        {"vcpus": 16, "ram_gb": 40, "max_connections": 3200}
    )

    heavy_threads = sum(w.get("threads", 0) for w in heavy_config["workloads"].values())
    assert heavy_threads > total_threads, "Extreme should use more threads than light"

    print(f"  ✅ Extreme intensity: {heavy_threads} threads (> {total_threads} light)")


def test_validation_warnings():
    """Test that validator generates warnings for excessive configs."""
    print("\n🧪 Test: Validation Warnings")

    client_hw = {"summary": {"cpu_cores": 4, "ram_gb": 8.0}}
    server_hw = {"vcpus": 4, "ram_gb": 8, "max_connections": 500}

    # Create config with excessive threads
    excessive_config = {
        "workloads": {
            "indexed_reads": {"threads": 200},  # Way over limit
        },
        "seeding": {"large_count": 10_000_000}  # Large seeding
    }

    validation = ResourceValidator.validate_configuration(
        excessive_config, client_hw, server_hw, allow_overrides=False
    )

    assert not validation["ok"], "Should fail validation"
    assert len(validation["warnings"]) > 0, "Should have warnings"

    print(f"  ✅ Generated {len(validation['warnings'])} warnings for excessive config")

    # Test with override
    validation_override = ResourceValidator.validate_configuration(
        excessive_config, client_hw, server_hw, allow_overrides=True
    )

    assert validation_override["ok"], "Should pass with override"
    assert len(validation_override["warnings"]) > 0, "Should still have warnings"

    print(f"  ✅ Override allowed excessive config with warnings")


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("V2 INTEGRATION TESTS")
    print("=" * 60)

    try:
        # Test 1: Hardware Discovery
        client_hw = test_hardware_discovery()

        # Test 2: Intent Calculation
        config = test_intent_calculation(client_hw)

        # Test 3: Workload Optimization
        optimized = test_workload_optimization(config, client_hw)

        # Test 4: Resource Validation
        validation = test_resource_validation(optimized, client_hw)

        # Test 5: All Intents
        test_all_intents()

        # Test 6: Edge Cases
        test_edge_cases()

        # Test 7: Validation Warnings
        test_validation_warnings()

        print("\n" + "=" * 60)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
