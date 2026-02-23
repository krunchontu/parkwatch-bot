"""Config repository.

Handles runtime configuration overrides stored in the database.
"""

from datetime import datetime
from typing import cast

from ..models import ConfigOverrideRow
from .base import BaseRepository


class ConfigRepository(BaseRepository):
    """Runtime configuration override operations."""

    async def get_config_override(self, key: str) -> ConfigOverrideRow | None:
        """Get a single runtime config override by key."""
        row = await self._fetchone(
            f"SELECT key, value, updated_by, updated_at FROM config_overrides WHERE key = {self._ph(1)}",
            (key,),
        )
        return cast(ConfigOverrideRow, row) if row else None

    async def get_all_config_overrides(self) -> list[ConfigOverrideRow]:
        """Get all runtime config overrides."""
        rows = await self._fetchall("SELECT key, value, updated_by, updated_at FROM config_overrides ORDER BY key")
        return cast(list[ConfigOverrideRow], rows)

    async def upsert_config_override(self, key: str, value: str, updated_by: int, updated_at: datetime) -> None:
        """Insert or update a runtime config override."""
        if self.driver == "sqlite":
            await self._execute(
                "INSERT OR REPLACE INTO config_overrides (key, value, updated_by, updated_at) VALUES (?, ?, ?, ?)",
                (key, value, updated_by, updated_at),
            )
        else:
            await self._execute(
                "INSERT INTO config_overrides (key, value, updated_by, updated_at) VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, "
                "updated_by = EXCLUDED.updated_by, updated_at = EXCLUDED.updated_at",
                (key, value, updated_by, updated_at),
            )

    async def delete_config_override(self, key: str) -> None:
        """Delete a runtime config override."""
        await self._execute(f"DELETE FROM config_overrides WHERE key = {self._ph(1)}", (key,))
