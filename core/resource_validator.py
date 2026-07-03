"""Resource validator with hard limits and override warnings.

Validates configurations against hardware limits and provides
clear warnings when limits are exceeded.
"""
from __future__ import annotations


class ResourceValidator:
    """Validate configurations against hardware limits."""

    @staticmethod
    def max_threads(cpu_cores: int) -> int:
        """Calculate maximum recommended threads.

        Formula: (cpu_cores - 2) * 10, minimum 10
        """
        return max(10, (cpu_cores - 2) * 10)

    @staticmethod
    def max_connections(server_max_connections: int) -> int:
        """Calculate maximum safe connection count.

        Formula: 80% of server max connections
        """
        return int(server_max_connections * 0.8)

    @staticmethod
    def max_concurrent_ops(ram_gb: float) -> int:
        """Estimate maximum concurrent ops based on RAM.

        Formula: 1 GB RAM ≈ 10K ops/sec
        """
        return int(ram_gb * 10_000)

    @staticmethod
    def validate_threads(
        total_threads: int,
        cpu_cores: int,
        allow_override: bool = False,
    ) -> dict:
        """Validate total thread count.

        Args:
            total_threads: Total threads across all workloads
            cpu_cores: Client CPU cores
            allow_override: Whether override is allowed

        Returns:
            Dict with ok, limit, warnings
        """
        limit = ResourceValidator.max_threads(cpu_cores)

        if total_threads <= limit:
            return {"ok": True, "limit": limit, "warnings": []}

        warnings = [
            f"Total threads ({total_threads}) exceeds recommended limit ({limit})",
            f"Risk: CPU oversubscription may cause thread starvation",
            f"Risk: Context switching overhead will reduce throughput",
            f"Risk: System may become unresponsive",
        ]

        if allow_override:
            warnings.append("⚠️  OVERRIDE: User explicitly allowed exceeding limits")
            return {"ok": True, "limit": limit, "warnings": warnings, "overridden": True}
        else:
            return {"ok": False, "limit": limit, "warnings": warnings}

    @staticmethod
    def validate_connections(
        connection_count: int,
        server_max_connections: int,
        allow_override: bool = False,
    ) -> dict:
        """Validate connection count."""
        limit = ResourceValidator.max_connections(server_max_connections)

        if connection_count <= limit:
            return {"ok": True, "limit": limit, "warnings": []}

        warnings = [
            f"Connection count ({connection_count}) exceeds recommended limit ({limit})",
            f"Risk: May exhaust server connection pool",
            f"Risk: New connections may be rejected",
            f"Hint: Server max connections: {server_max_connections}",
        ]

        if allow_override:
            warnings.append("⚠️  OVERRIDE: User explicitly allowed exceeding limits")
            return {"ok": True, "limit": limit, "warnings": warnings, "overridden": True}
        else:
            return {"ok": False, "limit": limit, "warnings": warnings}

    @staticmethod
    def validate_memory(
        required_gb: float,
        available_gb: float,
        allow_override: bool = False,
    ) -> dict:
        """Validate memory requirements."""
        # Use 80% of available as safe limit
        safe_limit = available_gb * 0.8

        if required_gb <= safe_limit:
            return {"ok": True, "limit": safe_limit, "warnings": []}

        warnings = [
            f"Required memory ({required_gb:.1f} GB) exceeds safe limit ({safe_limit:.1f} GB)",
            f"Risk: System may swap to disk (severe performance degradation)",
            f"Risk: Out of memory errors possible",
            f"Available: {available_gb:.1f} GB",
        ]

        if allow_override:
            warnings.append("⚠️  OVERRIDE: User explicitly allowed exceeding limits")
            return {"ok": True, "limit": safe_limit, "warnings": warnings, "overridden": True}
        else:
            return {"ok": False, "limit": safe_limit, "warnings": warnings}

    @staticmethod
    def validate_configuration(
        config: dict,
        client_hardware: dict,
        server_hardware: dict,
        allow_overrides: bool = False,
    ) -> dict:
        """Validate entire configuration.

        Args:
            config: Configuration to validate
            client_hardware: Client hardware profile
            server_hardware: Server hardware profile
            allow_overrides: Whether to allow limit overrides

        Returns:
            Validation result with warnings
        """
        client_cpu = client_hardware.get("summary", {}).get("cpu_cores", 4)
        client_ram = client_hardware.get("summary", {}).get("ram_gb", 16)
        server_max_conn = server_hardware.get("max_connections", 1000)

        results = {
            "ok": True,
            "warnings": [],
            "limits": {
                "max_threads": ResourceValidator.max_threads(client_cpu),
                "max_connections": ResourceValidator.max_connections(server_max_conn),
            },
        }

        # Validate total threads
        total_threads = sum(
            params.get("threads", 0)
            for params in config.get("workloads", {}).values()
        )

        if total_threads > 0:
            thread_result = ResourceValidator.validate_threads(
                total_threads, client_cpu, allow_overrides
            )
            if not thread_result["ok"]:
                results["ok"] = False
            results["warnings"].extend(thread_result["warnings"])

        # Validate connections (if connection_storm workload)
        if "connection_storm" in config.get("workloads", {}):
            conn_count = config["workloads"]["connection_storm"].get("connection_count", 0)
            conn_result = ResourceValidator.validate_connections(
                conn_count, server_max_conn, allow_overrides
            )
            if not conn_result["ok"]:
                results["ok"] = False
            results["warnings"].extend(conn_result["warnings"])

        # Estimate memory usage
        # Rough estimate: threads * 50 MB + seeding size
        estimated_ram_mb = total_threads * 50

        seeding = config.get("seeding", {})
        large_count = seeding.get("large_count", 0)
        # Assume 1KB per doc average
        seeding_gb = (large_count * 1) / (1024 * 1024)
        estimated_ram_mb += seeding_gb * 1024

        estimated_ram_gb = estimated_ram_mb / 1024

        mem_result = ResourceValidator.validate_memory(
            estimated_ram_gb, client_ram, allow_overrides
        )
        if not mem_result["ok"]:
            results["ok"] = False
        results["warnings"].extend(mem_result["warnings"])

        results["resource_usage"] = {
            "total_threads": total_threads,
            "estimated_ram_gb": round(estimated_ram_gb, 2),
            "connection_count": config.get("workloads", {}).get("connection_storm", {}).get("connection_count", 0),
        }

        return results


if __name__ == "__main__":
    # Test validator
    print("✅ Resource Validator Test\n")

    config = {
        "intensity": "extreme",
        "workloads": {
            "indexed_reads": {"threads": 80},
            "unindexed_scans": {"threads": 40},
        },
        "seeding": {"large_count": 1000000},
    }

    client_hw = {
        "summary": {"cpu_cores": 12, "ram_gb": 24.0}
    }

    server_hw = {
        "max_connections": 3200
    }

    print("Validating configuration...")
    print(f"  Total threads: 120")
    print(f"  Client: 12 cores, 24 GB RAM")
    print(f"  Limit: {ResourceValidator.max_threads(12)} threads\n")

    result = ResourceValidator.validate_configuration(config, client_hw, server_hw)

    print(f"Result: {'✅ PASS' if result['ok'] else '❌ FAIL'}")
    print(f"Warnings: {len(result['warnings'])}")
    for warning in result['warnings']:
        print(f"  - {warning}")

    print(f"\nResource usage:")
    print(f"  Threads: {result['resource_usage']['total_threads']}")
    print(f"  Est. RAM: {result['resource_usage']['estimated_ram_gb']} GB")

    # Test with override
    print("\n" + "="*60)
    print("Testing with override allowed...")
    result2 = ResourceValidator.validate_configuration(config, client_hw, server_hw, allow_overrides=True)
    print(f"Result: {'✅ PASS (override)' if result2['ok'] else '❌ FAIL'}")

    print("\n✅ Validator test passed!")
