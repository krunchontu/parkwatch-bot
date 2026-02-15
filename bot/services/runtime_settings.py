"""Runtime settings service backed by config_overrides table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config import (
    DUPLICATE_RADIUS_METERS,
    DUPLICATE_WINDOW_MINUTES,
    FEEDBACK_WINDOW_HOURS,
    MAINTENANCE_MESSAGE,
    MAINTENANCE_MODE,
    MAX_REPORTS_PER_HOUR,
    MAX_WARNINGS,
    SIGHTING_EXPIRY_MINUTES,
    SIGHTING_RETENTION_DAYS,
)

from ..database import get_db


@dataclass(frozen=True)
class SettingSpec:
    key: str
    value_type: type
    default: Any


MUTABLE_SPECS: dict[str, SettingSpec] = {
    "MAX_REPORTS_PER_HOUR": SettingSpec("MAX_REPORTS_PER_HOUR", int, MAX_REPORTS_PER_HOUR),
    "DUPLICATE_WINDOW_MINUTES": SettingSpec("DUPLICATE_WINDOW_MINUTES", int, DUPLICATE_WINDOW_MINUTES),
    "DUPLICATE_RADIUS_METERS": SettingSpec("DUPLICATE_RADIUS_METERS", float, float(DUPLICATE_RADIUS_METERS)),
    "SIGHTING_EXPIRY_MINUTES": SettingSpec("SIGHTING_EXPIRY_MINUTES", int, SIGHTING_EXPIRY_MINUTES),
    "SIGHTING_RETENTION_DAYS": SettingSpec("SIGHTING_RETENTION_DAYS", int, SIGHTING_RETENTION_DAYS),
    "FEEDBACK_WINDOW_HOURS": SettingSpec("FEEDBACK_WINDOW_HOURS", int, FEEDBACK_WINDOW_HOURS),
    "MAX_WARNINGS": SettingSpec("MAX_WARNINGS", int, MAX_WARNINGS),
    "MAINTENANCE_MODE": SettingSpec("MAINTENANCE_MODE", bool, MAINTENANCE_MODE),
    "MAINTENANCE_MESSAGE": SettingSpec("MAINTENANCE_MESSAGE", str, MAINTENANCE_MESSAGE),
}


class RuntimeSettingsError(ValueError):
    """Raised when runtime setting key/value is invalid."""


class RuntimeSettings:
    """Typed runtime setting accessor and mutator."""

    def _get_spec(self, key: str) -> SettingSpec:
        spec = MUTABLE_SPECS.get(key)
        if not spec:
            raise RuntimeSettingsError(f"Setting '{key}' cannot be changed at runtime.")
        return spec

    def _cast(self, spec: SettingSpec, raw_value: str) -> Any:
        if spec.value_type is int:
            try:
                return int(raw_value)
            except ValueError as exc:
                raise RuntimeSettingsError(f"{spec.key} requires an integer value.") from exc

        if spec.value_type is float:
            try:
                return float(raw_value)
            except ValueError as exc:
                raise RuntimeSettingsError(f"{spec.key} requires a numeric value.") from exc

        if spec.value_type is bool:
            normalized = raw_value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
            raise RuntimeSettingsError(f"{spec.key} requires a boolean value (true/false).")

        if spec.value_type is str:
            value = raw_value.strip()
            if not value:
                raise RuntimeSettingsError(f"{spec.key} cannot be empty.")
            return value

        raise RuntimeSettingsError(f"Unsupported type for setting {spec.key}.")

    async def get(self, key: str) -> Any:
        spec = self._get_spec(key)
        row = await get_db().get_config_override(key)
        if not row:
            return spec.default
        return self._cast(spec, row["value"])

    async def list_effective(self) -> list[dict[str, Any]]:
        overrides = {r["key"]: r for r in await get_db().get_all_config_overrides()}
        items: list[dict[str, Any]] = []
        for key, spec in MUTABLE_SPECS.items():
            if key in overrides:
                value = self._cast(spec, overrides[key]["value"])
                source = "override"
            else:
                value = spec.default
                source = "default"
            items.append({"key": key, "value": value, "source": source, "type": spec.value_type.__name__})
        return items

    async def set_override(self, key: str, raw_value: str, actor_id: int) -> tuple[Any, Any]:
        spec = self._get_spec(key)
        new_value = self._cast(spec, raw_value)
        old_value = await self.get(key)

        await get_db().upsert_config_override(
            key=key,
            value=str(new_value),
            updated_by=actor_id,
            updated_at=datetime.now(timezone.utc),
        )
        return old_value, new_value

    async def reset_override(self, key: str) -> Any:
        spec = self._get_spec(key)
        await get_db().delete_config_override(key)
        return spec.default


_runtime_settings = RuntimeSettings()


def get_runtime_settings() -> RuntimeSettings:
    return _runtime_settings
