"""Hardware discovery using psutil for client machine specs.

Auto-detects:
- CPU cores (physical and logical)
- RAM (total and available)
- Storage (disk space)
- Network interfaces
"""
from __future__ import annotations

import os
import platform
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None


class HardwareDiscovery:
    """Detect client machine hardware specifications."""

    @staticmethod
    def get_cpu_info() -> dict:
        """Get CPU information.

        Returns:
            Dict with physical_cores, logical_cores, cpu_percent
        """
        if not psutil:
            return {"error": "psutil not installed"}

        return {
            "physical_cores": psutil.cpu_count(logical=False) or 0,
            "logical_cores": psutil.cpu_count(logical=True) or 0,
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "cpu_freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
        }

    @staticmethod
    def get_memory_info() -> dict:
        """Get RAM information.

        Returns:
            Dict with total_gb, available_gb, used_gb, percent
        """
        if not psutil:
            return {"error": "psutil not installed"}

        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "used_gb": mem.used / (1024**3),
            "percent": mem.percent,
        }

    @staticmethod
    def get_disk_info(path: str = "/") -> dict:
        """Get disk information for given path.

        Args:
            path: Path to check disk space for (default: root)

        Returns:
            Dict with total_gb, used_gb, free_gb, percent
        """
        if not psutil:
            return {"error": "psutil not installed"}

        try:
            # On macOS, check the user's home directory mount point
            if platform.system() == "Darwin":
                path = os.path.expanduser("~")

            disk = psutil.disk_usage(path)
            return {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk.percent,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e), "path": path}

    @staticmethod
    def get_network_info() -> dict:
        """Get network interface information.

        Returns:
            Dict with interface details and estimated bandwidth
        """
        if not psutil:
            return {"error": "psutil not installed"}

        interfaces = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        active_interfaces = []
        for name, stats in interfaces.items():
            if stats.isup and name not in ["lo", "lo0"]:  # Skip loopback
                iface_info = {
                    "name": name,
                    "speed_mbps": stats.speed if stats.speed > 0 else None,
                    "mtu": stats.mtu,
                }

                # Get IP addresses
                if name in addrs:
                    ips = [addr.address for addr in addrs[name] if addr.family.name in ["AF_INET", "AF_INET6"]]
                    iface_info["addresses"] = ips

                active_interfaces.append(iface_info)

        # Estimate bandwidth from fastest interface
        max_speed = max(
            (iface.get("speed_mbps", 0) for iface in active_interfaces if iface.get("speed_mbps")),
            default=1000,  # Default to 1 Gbps if unknown
        )

        return {
            "interfaces": active_interfaces,
            "estimated_bandwidth_gbps": max_speed / 1000 if max_speed else 1.0,
        }

    @staticmethod
    def get_platform_info() -> dict:
        """Get platform/OS information.

        Returns:
            Dict with system, release, machine, processor
        """
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
        }

    @staticmethod
    def get_full_profile() -> dict:
        """Get complete hardware profile.

        Returns:
            Dict with all hardware information
        """
        if not psutil:
            return {
                "error": "psutil not installed",
                "install_hint": "Run: pip install psutil",
            }

        cpu = HardwareDiscovery.get_cpu_info()
        memory = HardwareDiscovery.get_memory_info()
        disk = HardwareDiscovery.get_disk_info()
        network = HardwareDiscovery.get_network_info()
        platform_info = HardwareDiscovery.get_platform_info()

        return {
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "network": network,
            "platform": platform_info,
            "summary": {
                "cpu_cores": cpu.get("physical_cores", 0),
                "cpu_threads": cpu.get("logical_cores", 0),
                "ram_gb": memory.get("total_gb", 0),
                "storage_gb": disk.get("total_gb", 0),
                "storage_free_gb": disk.get("free_gb", 0),
                "network_gbps": network.get("estimated_bandwidth_gbps", 1.0),
            },
        }

    @staticmethod
    def calculate_recommended_limits(profile: dict) -> dict:
        """Calculate recommended resource limits based on hardware.

        Args:
            profile: Hardware profile dict

        Returns:
            Dict with recommended max threads, connections, etc.
        """
        summary = profile.get("summary", {})
        cpu_cores = summary.get("cpu_cores", 1)
        ram_gb = summary.get("ram_gb", 1)

        # Formula: (cpu_cores - 2) * 10, but at least 10
        max_threads = max(10, (cpu_cores - 2) * 10)

        # Formula: cpu_cores * 100
        max_connections = cpu_cores * 100

        # Estimate max concurrent ops based on RAM (1 GB RAM = ~10K ops/s)
        max_ops_estimate = int(ram_gb * 10_000)

        return {
            "max_threads": max_threads,
            "max_connections": max_connections,
            "max_ops_per_sec_estimate": max_ops_estimate,
            "recommended_thread_ranges": {
                "light": cpu_cores * 2,
                "medium": cpu_cores * 4,
                "heavy": cpu_cores * 6,
                "extreme": max_threads,
            },
        }


def discover_client_hardware() -> dict:
    """Convenience function to discover client hardware.

    Returns:
        Dict with full hardware profile and recommended limits
    """
    profile = HardwareDiscovery.get_full_profile()
    if "error" not in profile:
        profile["recommended_limits"] = HardwareDiscovery.calculate_recommended_limits(profile)
    return profile


if __name__ == "__main__":
    # Test hardware discovery
    import json

    print("🔍 Discovering client hardware...\n")

    profile = discover_client_hardware()
    print(json.dumps(profile, indent=2))

    if "error" not in profile:
        print("\n✅ Hardware discovery successful!")
        summary = profile["summary"]
        print(f"\n📊 Summary:")
        print(f"   CPU: {summary['cpu_cores']} cores / {summary['cpu_threads']} threads")
        print(f"   RAM: {summary['ram_gb']:.2f} GB")
        print(f"   Storage: {summary['storage_free_gb']:.2f} GB free / {summary['storage_gb']:.2f} GB total")
        print(f"   Network: ~{summary['network_gbps']:.1f} Gbps")

        limits = profile["recommended_limits"]
        print(f"\n⚙️  Recommended Limits:")
        print(f"   Max threads: {limits['max_threads']}")
        print(f"   Max connections: {limits['max_connections']}")
        print(f"   Estimated max ops/s: {limits['max_ops_per_sec_estimate']:,}")
    else:
        print(f"\n❌ Error: {profile['error']}")
        if "install_hint" in profile:
            print(f"   {profile['install_hint']}")
