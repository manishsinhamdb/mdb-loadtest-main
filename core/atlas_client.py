"""MongoDB Atlas API Client.

Fetches real-time metrics from Atlas Monitoring API during load tests.
Supports all 130+ metrics cataloged in atlas_metrics.json.
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta
from typing import Any

import httpx


class AtlasClient:
    """Atlas API client for fetching metrics."""

    BASE_URL = "https://cloud.mongodb.com/api/atlas/v2"

    def __init__(self, public_key: str, private_key: str, project_id: str):
        """Initialize Atlas client.

        Args:
            public_key: Atlas API public key
            private_key: Atlas API private key
            project_id: Atlas project/group ID
        """
        self.public_key = public_key
        self.private_key = private_key
        self.project_id = project_id
        self.session = httpx.Client(timeout=30.0)

        # Build digest auth header
        credentials = f"{public_key}:{private_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.session.headers["Authorization"] = f"Digest {encoded}"

    def get_process_metrics(
        self,
        cluster_name: str,
        host: str,
        port: int,
        metrics: list[str],
        granularity: str = "PT1M",
        period: str = "PT10M",
    ) -> dict[str, Any]:
        """Fetch process-level metrics.

        Args:
            cluster_name: Cluster name
            host: Host address
            port: Port number
            metrics: List of metric names (e.g., ["CONNECTIONS", "OPCOUNTER_QUERY"])
            granularity: Data point granularity (PT1M = 1 minute)
            period: Time period to fetch (PT10M = 10 minutes)

        Returns:
            Dict with measurements per metric
        """
        url = (
            f"{self.BASE_URL}/groups/{self.project_id}/processes/"
            f"{host}:{port}/measurements"
        )

        params = {
            "granularity": granularity,
            "period": period,
            "m": ",".join(metrics),
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def get_cluster_metrics(
        self,
        cluster_name: str,
        metrics: list[str],
        granularity: str = "PT1M",
        period: str = "PT10M",
    ) -> dict[str, Any]:
        """Fetch cluster-level metrics.

        Args:
            cluster_name: Cluster name
            metrics: List of metric names
            granularity: Data point granularity
            period: Time period to fetch

        Returns:
            Dict with measurements per metric
        """
        # For cluster metrics, use the processes endpoint with cluster aggregate
        # Atlas automatically aggregates across all processes in the cluster
        url = (
            f"{self.BASE_URL}/groups/{self.project_id}/processes/"
            f"{cluster_name}/measurements"
        )

        params = {
            "granularity": granularity,
            "period": period,
            "m": ",".join(metrics),
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def get_search_metrics(
        self,
        cluster_name: str,
        index_name: str,
        metrics: list[str],
        granularity: str = "PT1M",
        period: str = "PT10M",
    ) -> dict[str, Any]:
        """Fetch Atlas Search metrics.

        Args:
            cluster_name: Cluster name
            index_name: Search index name
            metrics: List of metric names
            granularity: Data point granularity
            period: Time period to fetch

        Returns:
            Dict with measurements per metric
        """
        url = (
            f"{self.BASE_URL}/groups/{self.project_id}/clusters/"
            f"{cluster_name}/fts/indexes/{index_name}/measurements"
        )

        params = {
            "granularity": granularity,
            "period": period,
            "m": ",".join(metrics),
        }

        response = self.session.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def poll_metrics_during_run(
        self,
        cluster_name: str,
        host: str,
        port: int,
        metrics: list[str],
        duration_seconds: int,
        callback: callable,
    ):
        """Poll metrics continuously during a test run.

        Args:
            cluster_name: Cluster name
            host: Host address
            port: Port number
            metrics: List of metric names to track
            duration_seconds: How long to poll
            callback: Function to call with each batch of measurements
                      Signature: callback(timestamp, measurements_dict)
        """
        start_time = time.time()
        poll_interval = 60  # Poll every 60 seconds

        while time.time() - start_time < duration_seconds:
            try:
                # Fetch last 2 minutes of data
                data = self.get_process_metrics(
                    cluster_name, host, port, metrics,
                    granularity="PT1M", period="PT2M"
                )

                # Extract latest measurements
                measurements = {}
                for measurement in data.get("measurements", []):
                    metric_name = measurement["name"]
                    datapoints = measurement["dataPoints"]
                    if datapoints:
                        latest = datapoints[-1]
                        measurements[metric_name] = latest["value"]

                # Call callback with results
                callback(datetime.utcnow(), measurements)

            except Exception as e:
                # Log error but continue polling
                print(f"Atlas API error: {e}")

            # Sleep until next poll
            time.sleep(poll_interval)

    def get_cluster_info(self, cluster_name: str) -> dict[str, Any]:
        """Get cluster configuration info.

        Args:
            cluster_name: Cluster name

        Returns:
            Cluster details including tier, version, topology
        """
        url = f"{self.BASE_URL}/groups/{self.project_id}/clusters/{cluster_name}"
        response = self.session.get(url)
        response.raise_for_status()

        return response.json()

    def close(self):
        """Close HTTP session."""
        self.session.close()


if __name__ == "__main__":
    print("🔌 Atlas Client Test\n")
    print("NOTE: Requires actual Atlas API credentials to run")
    print("Export these env vars:")
    print("  export ATLAS_PUBLIC_KEY=...")
    print("  export ATLAS_PRIVATE_KEY=...")
    print("  export ATLAS_PROJECT_ID=...")
    print("\nSkipping live test. Use in production with real credentials.")
