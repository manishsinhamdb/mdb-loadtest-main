"""Connection profile management with URI encryption.

Handles CRUD operations for stored MongoDB connection profiles.
Uses Fernet (symmetric encryption) for securing connection URIs and API keys.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from db.models import ConnectionProfile


class ConnectionManager:
    """Manages encrypted connection profiles."""

    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize connection manager with encryption key.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from
                           LOADGEN_ENCRYPTION_KEY env var or generates new one.
        """
        if encryption_key is None:
            encryption_key = os.environ.get("LOADGEN_ENCRYPTION_KEY")
            if not encryption_key:
                # Generate new key and warn user to save it
                new_key = Fernet.generate_key().decode()
                print(
                    f"\n⚠️  WARNING: No encryption key found!\n"
                    f"   Generated new key: {new_key}\n"
                    f"   Set environment variable to persist:\n"
                    f"   export LOADGEN_ENCRYPTION_KEY='{new_key}'\n"
                )
                encryption_key = new_key

        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def encrypt_string(self, plaintext: str) -> bytes:
        """Encrypt a string."""
        return self.cipher.encrypt(plaintext.encode())

    def decrypt_string(self, encrypted: bytes) -> str:
        """Decrypt bytes to string."""
        return self.cipher.decrypt(encrypted).decode()

    def create_profile(
        self,
        session: Session,
        name: str,
        uri: str,
        database_name: str,
        auth_source: Optional[str] = None,
    ) -> ConnectionProfile:
        """Create a new connection profile.

        Args:
            session: SQLAlchemy session
            name: Friendly profile name (must be unique)
            uri: MongoDB connection URI (will be encrypted)
            database_name: Default database name
            auth_source: Optional auth source override

        Returns:
            Created ConnectionProfile instance

        Raises:
            ValueError: If profile name already exists
        """
        # Check if name exists
        existing = session.query(ConnectionProfile).filter_by(name=name).first()
        if existing:
            raise ValueError(f"Profile with name '{name}' already exists")

        # Encrypt URI
        uri_encrypted = self.encrypt_string(uri)

        # Create profile
        profile = ConnectionProfile(
            name=name,
            uri_encrypted=uri_encrypted,
            database_name=database_name,
            auth_source=auth_source,
            created_at=datetime.utcnow(),
        )

        session.add(profile)
        session.commit()
        session.refresh(profile)

        return profile

    def get_profile(self, session: Session, profile_id: int) -> Optional[ConnectionProfile]:
        """Get profile by ID."""
        return session.query(ConnectionProfile).filter_by(id=profile_id).first()

    def get_profile_by_name(self, session: Session, name: str) -> Optional[ConnectionProfile]:
        """Get profile by name."""
        return session.query(ConnectionProfile).filter_by(name=name).first()

    def list_profiles(self, session: Session) -> list[ConnectionProfile]:
        """List all profiles (most recently used first)."""
        return (
            session.query(ConnectionProfile)
            .order_by(ConnectionProfile.last_used.desc().nullslast(), ConnectionProfile.created_at.desc())
            .all()
        )

    def update_profile(
        self,
        session: Session,
        profile_id: int,
        name: Optional[str] = None,
        uri: Optional[str] = None,
        database_name: Optional[str] = None,
        auth_source: Optional[str] = None,
    ) -> ConnectionProfile:
        """Update an existing profile.

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID to update
            name: New name (optional)
            uri: New URI (optional, will be encrypted)
            database_name: New database name (optional)
            auth_source: New auth source (optional)

        Returns:
            Updated ConnectionProfile

        Raises:
            ValueError: If profile not found or new name conflicts
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            raise ValueError(f"Profile with ID {profile_id} not found")

        # Check name conflict if changing name
        if name and name != profile.name:
            existing = session.query(ConnectionProfile).filter_by(name=name).first()
            if existing:
                raise ValueError(f"Profile with name '{name}' already exists")
            profile.name = name

        if uri:
            profile.uri_encrypted = self.encrypt_string(uri)

        if database_name:
            profile.database_name = database_name

        if auth_source is not None:  # Allow setting to None
            profile.auth_source = auth_source

        session.commit()
        session.refresh(profile)

        return profile

    def delete_profile(self, session: Session, profile_id: int) -> bool:
        """Delete a profile.

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID to delete

        Returns:
            True if deleted, False if not found
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            return False

        session.delete(profile)
        session.commit()
        return True

    def get_decrypted_uri(self, profile: ConnectionProfile) -> str:
        """Decrypt and return the connection URI.

        Args:
            profile: ConnectionProfile instance

        Returns:
            Decrypted connection URI
        """
        return self.decrypt_string(profile.uri_encrypted)

    def update_discovery_data(
        self,
        session: Session,
        profile_id: int,
        client_data: Optional[dict] = None,
        server_data: Optional[dict] = None,
    ) -> ConnectionProfile:
        """Update cached discovery data for a profile.

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID
            client_data: Dict with cpu_cores, ram_gb, storage_gb
            server_data: Dict with version, topology, cluster_tier, ram_gb, vcpus, max_connections

        Returns:
            Updated ConnectionProfile
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            raise ValueError(f"Profile with ID {profile_id} not found")

        if client_data:
            profile.client_cpu_cores = client_data.get("cpu_cores")
            profile.client_ram_gb = client_data.get("ram_gb")
            profile.client_storage_gb = client_data.get("storage_gb")

        if server_data:
            profile.server_version = server_data.get("version")
            profile.server_topology = server_data.get("topology")
            profile.server_cluster_tier = server_data.get("cluster_tier")
            profile.server_ram_gb = server_data.get("ram_gb")
            profile.server_vcpus = server_data.get("vcpus")
            profile.server_max_connections = server_data.get("max_connections")

        session.commit()
        session.refresh(profile)

        return profile

    def update_test_result(
        self,
        session: Session,
        profile_id: int,
        success: bool,
    ) -> ConnectionProfile:
        """Update test connection result.

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID
            success: Whether test succeeded

        Returns:
            Updated ConnectionProfile
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            raise ValueError(f"Profile with ID {profile_id} not found")

        profile.last_test_success = success
        profile.last_test_at = datetime.utcnow()

        session.commit()
        session.refresh(profile)

        return profile

    def mark_used(self, session: Session, profile_id: int) -> ConnectionProfile:
        """Mark profile as used (updates last_used timestamp).

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID

        Returns:
            Updated ConnectionProfile
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            raise ValueError(f"Profile with ID {profile_id} not found")

        profile.last_used = datetime.utcnow()

        session.commit()
        session.refresh(profile)

        return profile

    def set_atlas_credentials(
        self,
        session: Session,
        profile_id: int,
        public_key: str,
        private_key: str,
        group_id: str,
    ) -> ConnectionProfile:
        """Set Atlas API credentials for a profile (encrypted).

        Args:
            session: SQLAlchemy session
            profile_id: Profile ID
            public_key: Atlas public API key
            private_key: Atlas private API key
            group_id: Atlas project/group ID

        Returns:
            Updated ConnectionProfile
        """
        profile = self.get_profile(session, profile_id)
        if not profile:
            raise ValueError(f"Profile with ID {profile_id} not found")

        profile.atlas_public_key_encrypted = self.encrypt_string(public_key)
        profile.atlas_private_key_encrypted = self.encrypt_string(private_key)
        profile.atlas_group_id = group_id

        session.commit()
        session.refresh(profile)

        return profile

    def get_atlas_credentials(self, profile: ConnectionProfile) -> Optional[dict]:
        """Get decrypted Atlas API credentials.

        Args:
            profile: ConnectionProfile instance

        Returns:
            Dict with public_key, private_key, group_id or None if not set
        """
        if not profile.atlas_public_key_encrypted:
            return None

        return {
            "public_key": self.decrypt_string(profile.atlas_public_key_encrypted),
            "private_key": self.decrypt_string(profile.atlas_private_key_encrypted),
            "group_id": profile.atlas_group_id,
        }


# Global instance (lazy-initialized)
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get global ConnectionManager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
