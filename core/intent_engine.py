"""Intent Engine - Maps user intents to workload configurations.

Converts high-level testing intents (e.g., "read_performance") into
detailed workload configurations with optimized parameters based on
client and server hardware.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
INTENT_TEMPLATES_PATH = PROJECT_ROOT / "data" / "intent_templates.json"


class IntentEngine:
    """Calculate workload configurations from user intents."""

    def __init__(self):
        """Initialize intent engine with templates."""
        with open(INTENT_TEMPLATES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.intents = data["intents"]
            self.global_settings = data["global_settings"]

    def list_intents(self) -> list[dict]:
        """List all available intents.

        Returns:
            List of intent metadata (id, name, description, icon, category)
        """
        return [
            {
                "id": intent_id,
                "name": intent["name"],
                "description": intent["description"],
                "icon": intent["icon"],
                "category": intent["category"],
                "primary_metrics": intent["primary_metrics"],
                "recommended_duration": intent["recommended_duration_seconds"],
            }
            for intent_id, intent in self.intents.items()
        ]

    def get_intent(self, intent_id: str) -> Optional[dict]:
        """Get intent template by ID."""
        return self.intents.get(intent_id)

    def calculate_configuration(
        self,
        intent_id: str,
        intensity: str = "medium",
        duration_seconds: int = 600,
        data_size: Optional[str] = None,
        concurrency_level: int = 10,
        client_hardware: Optional[dict] = None,
        server_hardware: Optional[dict] = None,
    ) -> dict:
        """Calculate full workload configuration from intent.

        Args:
            intent_id: Intent identifier (e.g., "read_performance")
            intensity: Intensity level (light, medium, heavy, extreme)
            duration_seconds: Test duration
            data_size: Data size option (10k, 100k, 1m, 10m) - intent-specific
            concurrency_level: Concurrency multiplier (1-100)
            client_hardware: Client hardware profile (from hardware_discovery)
            server_hardware: Server hardware profile (from connection test)

        Returns:
            Complete configuration dict ready for runner
        """
        intent = self.get_intent(intent_id)
        if not intent:
            raise ValueError(f"Unknown intent: {intent_id}")

        # Get hardware specs (with defaults)
        client_cpu = client_hardware.get("summary", {}).get("cpu_cores", 4) if client_hardware else 4
        client_ram = client_hardware.get("summary", {}).get("ram_gb", 16) if client_hardware else 16
        server_vcpus = server_hardware.get("vcpus", 4) if server_hardware else 4
        server_ram = server_hardware.get("ram_gb", 16) if server_hardware else 16
        server_max_conn = server_hardware.get("max_connections", 1000) if server_hardware else 1000

        # Get intensity multiplier
        intensity_mult = intent["intensity_multipliers"].get(intensity, 0.5)

        # Calculate workload parameters
        workloads = {}
        for workload_key, workload_config in intent["workloads"].items():
            if not workload_config.get("enabled", True):
                continue

            params = workload_config["params"].copy()

            # Replace {calculated} placeholders with actual values
            for param_key, param_value in params.items():
                if isinstance(param_value, str) and param_value == "{calculated}":
                    # Calculate based on formulas in intent
                    formula_key = f"{workload_key}_{param_key}"
                    if formula_key in intent.get("calculation_formulas", {}):
                        formula = intent["calculation_formulas"][formula_key]
                        params[param_key] = self._eval_formula(
                            formula,
                            client_cpu_cores=client_cpu,
                            intensity_multiplier=intensity_mult,
                            client_ram_gb=client_ram,
                            server_vcpus=server_vcpus,
                            server_ram_gb=server_ram,
                            server_max_connections=server_max_conn,
                            concurrency_level=concurrency_level,
                        )
                elif param_value == "{random}":
                    params[param_key] = random.randint(1000, 9999)

            workloads[workload_key] = params

        # Calculate seeding params
        seeding = self._calculate_seeding(
            intent, data_size, server_ram, intensity_mult
        )

        # Build resource estimates
        resource_estimates = self._build_resource_estimates(
            intent, intensity, client_hardware, server_hardware
        )

        return {
            "intent_id": intent_id,
            "intent_name": intent["name"],
            "intensity": intensity,
            "duration_seconds": duration_seconds,
            "workloads": workloads,
            "seeding": seeding,
            "primary_metrics": intent["primary_metrics"],
            "secondary_metrics": intent["secondary_metrics"],
            "resource_estimates": resource_estimates,
            "warnings": intent.get("warnings", []),
            "hardware_context": {
                "client_cpu_cores": client_cpu,
                "client_ram_gb": client_ram,
                "server_vcpus": server_vcpus,
                "server_ram_gb": server_ram,
            },
        }

    def _eval_formula(self, formula: str, **context) -> int:
        """Evaluate a formula string with given context.

        Args:
            formula: Formula string (e.g., "client_cpu_cores * intensity_multiplier * 8")
            **context: Variables to substitute

        Returns:
            Calculated integer value
        """
        # Replace variables
        expr = formula
        for key, value in context.items():
            expr = expr.replace(key, str(value))

        # Safe evaluation (basic math only)
        try:
            # Use eval with restricted builtins for safety
            result = eval(expr, {"__builtins__": {}, "min": min, "max": max, "int": int}, {})
            return int(result)
        except Exception as e:
            print(f"Warning: Failed to evaluate formula '{formula}': {e}")
            return 10  # Safe default

    def _calculate_seeding(
        self,
        intent: dict,
        data_size: Optional[str],
        server_ram_gb: float,
        intensity_mult: float,
    ) -> dict:
        """Calculate seeding parameters."""
        seeding_req = intent["seeding_requirement"]
        seeding_params = intent.get("seeding_params", {}).copy()

        if seeding_req == "minimal":
            # Use minimal defaults
            return {
                "large_count": 10000,
                "agg_count": 5000,
                "hot_docs": 100,
            }

        # Handle data_size placeholders
        if "{data_size}" in str(seeding_params):
            if data_size and "data_size_options" in intent:
                size_value = intent["data_size_options"].get(data_size, 1000000)
            else:
                size_value = 1000000  # Default 1M

            for key, value in seeding_params.items():
                if value == "{data_size}":
                    seeding_params[key] = size_value

        # Handle calculated RAM overflow sizes
        if "{calculated_for_ram_overflow}" in str(seeding_params):
            # For cache_pressure intent: size dataset to 1.5x server RAM
            overflow_size = int(server_ram_gb * 1.5 * 1000000 / 1024)
            for key, value in seeding_params.items():
                if value == "{calculated_for_ram_overflow}":
                    seeding_params[key] = overflow_size

        return {
            "large_count": seeding_params.get("large_count", 1000000),
            "agg_count": seeding_params.get("agg_count", 50000),
            "hot_docs": seeding_params.get("hot_docs", 100),
        }

    def _build_resource_estimates(
        self,
        intent: dict,
        intensity: str,
        client_hw: Optional[dict],
        server_hw: Optional[dict],
    ) -> dict:
        """Build resource usage estimates."""
        base_estimates = intent.get("resource_estimates", {})

        # Scale by intensity if possible
        intensity_scale = {"light": 0.5, "medium": 1.0, "heavy": 1.5, "extreme": 2.0}
        scale = intensity_scale.get(intensity, 1.0)

        return {
            "client_cpu_percent": int(base_estimates.get("client_cpu_percent", 50) * scale),
            "client_ram_mb": int(base_estimates.get("client_ram_mb", 2048) * scale),
            "server_cpu_percent": int(base_estimates.get("server_cpu_percent", 50) * scale),
            "server_ram_gb": base_estimates.get("server_ram_gb", 4),
            "network_mbps": int(base_estimates.get("network_mbps", 50) * scale),
        }

    def preview_impact(
        self,
        intent_id: str,
        intensity: str = "medium",
    ) -> dict:
        """Preview metric impact without full calculation.

        Args:
            intent_id: Intent identifier
            intensity: Intensity level

        Returns:
            Dict with primary/secondary metrics and impact descriptions
        """
        intent = self.get_intent(intent_id)
        if not intent:
            raise ValueError(f"Unknown intent: {intent_id}")

        return {
            "intent_name": intent["name"],
            "description": intent["description"],
            "primary_metrics": intent["primary_metrics"],
            "secondary_metrics": intent["secondary_metrics"],
            "warnings": intent.get("warnings", []),
            "resource_estimates": intent.get("resource_estimates", {}),
            "recommended_duration": intent["recommended_duration_seconds"],
        }


if __name__ == "__main__":
    # Test intent engine
    import json as json_lib

    engine = IntentEngine()

    print("🎯 Intent Engine Test\n")

    print("Available Intents:")
    for intent in engine.list_intents():
        print(f"  • {intent['icon']} {intent['name']} ({intent['id']})")
        print(f"    {intent['description']}")
        print(f"    Primary metrics: {', '.join(intent['primary_metrics'][:3])}...")
        print()

    print("\n" + "=" * 60)
    print("Calculating configuration for 'read_performance' intent...")
    print("=" * 60 + "\n")

    # Simulate hardware
    client_hw = {
        "summary": {
            "cpu_cores": 12,
            "ram_gb": 24.0,
            "storage_gb": 314.0,
        }
    }

    server_hw = {
        "vcpus": 16,
        "ram_gb": 40,
        "max_connections": 3200,
    }

    config = engine.calculate_configuration(
        intent_id="read_performance",
        intensity="medium",
        duration_seconds=600,
        data_size="1m",
        client_hardware=client_hw,
        server_hardware=server_hw,
    )

    print(json_lib.dumps(config, indent=2))
    print("\n✅ Intent engine test passed!")
