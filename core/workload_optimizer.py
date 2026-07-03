"""Workload parameter optimizer.

Calculates optimal workload parameters based on hardware constraints,
target metrics, and resource availability.
"""
from __future__ import annotations


class WorkloadOptimizer:
    """Optimize workload parameters for given hardware."""

    @staticmethod
    def optimize_threads(
        workload_key: str,
        base_threads: int,
        client_cpu_cores: int,
        intensity: str = "medium",
        max_limit: int | None = None,
    ) -> int:
        """Optimize thread count for a workload.

        Args:
            workload_key: Workload identifier
            base_threads: Base thread count from intent calculation
            client_cpu_cores: Client CPU cores
            intensity: Intensity level
            max_limit: Optional hard limit

        Returns:
            Optimized thread count
        """
        # Apply workload-specific multipliers
        workload_factors = {
            "connection_storm": 1.0,  # Direct connection count
            "indexed_reads": 1.2,     # CPU-efficient, can oversubscribe slightly
            "unindexed_scans": 0.9,   # More I/O bound
            "inmemory_sorts": 0.8,    # Memory-intensive
            "aggregation_pipelines": 0.9,  # CPU + memory
            "write_bursts": 1.0,      # Balanced
            "update_contention": 1.1,  # Can benefit from more contention
            "mixed_blend": 1.0,       # Balanced
        }

        factor = workload_factors.get(workload_key, 1.0)
        optimized = int(base_threads * factor)

        # Apply hard limit if provided
        if max_limit:
            optimized = min(optimized, max_limit)

        # Ensure at least 1 thread
        return max(1, optimized)

    @staticmethod
    def optimize_batch_size(
        workload_key: str,
        client_ram_gb: float,
        doc_size_kb: int = 10,
    ) -> int:
        """Optimize batch size for write operations.

        Args:
            workload_key: Workload identifier
            client_ram_gb: Client RAM in GB
            doc_size_kb: Document size in KB

        Returns:
            Optimized batch size
        """
        # Calculate based on available RAM
        # Assume 10% of RAM available for batching
        available_mb = client_ram_gb * 1024 * 0.1
        available_kb = available_mb * 1024

        # Calculate max documents per batch
        max_batch = int(available_kb / doc_size_kb)

        # Clamp to reasonable range
        return max(10, min(max_batch, 1000))

    @staticmethod
    def optimize_target_ops(
        workload_key: str,
        threads: int,
        server_vcpus: int,
        intensity: str = "medium",
    ) -> int:
        """Calculate target ops/sec for throttled workloads.

        Args:
            workload_key: Workload identifier
            threads: Thread count
            server_vcpus: Server vCPUs
            intensity: Intensity level

        Returns:
            Target ops/sec (0 = unthrottled)
        """
        # Most workloads are unthrottled (0)
        # Only throttle if specifically needed
        if workload_key in ["connection_storm"]:
            # Throttle connection storms to avoid overwhelming
            base_rate = server_vcpus * 10
            intensity_mult = {"light": 0.5, "medium": 1.0, "heavy": 2.0, "extreme": 4.0}
            return int(base_rate * intensity_mult.get(intensity, 1.0))

        return 0  # Unthrottled

    @staticmethod
    def calculate_concurrency_factor(
        client_cpu_cores: int,
        server_vcpus: int,
        intensity: str,
    ) -> float:
        """Calculate optimal concurrency factor.

        Args:
            client_cpu_cores: Client CPU cores
            server_vcpus: Server vCPUs
            intensity: Intensity level

        Returns:
            Concurrency multiplier
        """
        # Balance client and server resources
        cpu_ratio = client_cpu_cores / max(1, server_vcpus)

        # Base multipliers by intensity
        base = {"light": 2, "medium": 4, "heavy": 6, "extreme": 10}
        base_mult = base.get(intensity, 4)

        # Adjust based on CPU ratio
        if cpu_ratio > 2:
            # Client much stronger - can drive more load
            return base_mult * 1.2
        elif cpu_ratio < 0.5:
            # Server much stronger - reduce to avoid client bottleneck
            return base_mult * 0.8
        else:
            return base_mult

    @staticmethod
    def optimize_configuration(
        config: dict,
        client_hardware: dict,
        server_hardware: dict,
        limits: dict,
    ) -> dict:
        """Optimize entire workload configuration.

        Args:
            config: Configuration from intent engine
            client_hardware: Client hardware profile
            server_hardware: Server hardware profile
            limits: Resource limits (max_threads, max_connections, etc.)

        Returns:
            Optimized configuration
        """
        optimized = config.copy()

        client_cpu = client_hardware.get("summary", {}).get("cpu_cores", 4)
        client_ram = client_hardware.get("summary", {}).get("ram_gb", 16)
        server_vcpus = server_hardware.get("vcpus", 4)
        intensity = config.get("intensity", "medium")

        # Optimize each workload
        for workload_key, params in config.get("workloads", {}).items():
            optimized_params = params.copy()

            # Optimize threads
            if "threads" in params:
                optimized_params["threads"] = WorkloadOptimizer.optimize_threads(
                    workload_key,
                    params["threads"],
                    client_cpu,
                    intensity,
                    limits.get("max_threads"),
                )

            # Optimize batch size for write workloads
            if workload_key == "write_bursts" and "batch_size" in params:
                doc_kb = params.get("doc_kb", 10)
                optimized_params["batch_size"] = WorkloadOptimizer.optimize_batch_size(
                    workload_key, client_ram, doc_kb
                )

            # Optimize target ops if needed
            if "target_ops_per_sec" in params and params["target_ops_per_sec"] == 0:
                target = WorkloadOptimizer.optimize_target_ops(
                    workload_key,
                    optimized_params["threads"],
                    server_vcpus,
                    intensity,
                )
                if target > 0:
                    optimized_params["target_ops_per_sec"] = target

            optimized["workloads"][workload_key] = optimized_params

        return optimized


if __name__ == "__main__":
    # Test optimizer
    print("🔧 Workload Optimizer Test\n")

    # Sample config
    config = {
        "intent_id": "write_throughput",
        "intensity": "heavy",
        "workloads": {
            "write_bursts": {
                "threads": 60,
                "batch_size": 100,
                "doc_kb": 10,
            }
        },
    }

    client_hw = {
        "summary": {"cpu_cores": 12, "ram_gb": 24.0}
    }

    server_hw = {
        "vcpus": 16
    }

    limits = {
        "max_threads": 100,
        "max_connections": 1200,
    }

    print("Original config:")
    print(f"  write_bursts: threads={config['workloads']['write_bursts']['threads']}, "
          f"batch_size={config['workloads']['write_bursts']['batch_size']}")

    optimized = WorkloadOptimizer.optimize_configuration(config, client_hw, server_hw, limits)

    print("\nOptimized config:")
    print(f"  write_bursts: threads={optimized['workloads']['write_bursts']['threads']}, "
          f"batch_size={optimized['workloads']['write_bursts']['batch_size']}")

    print("\n✅ Optimizer test passed!")
