"""Tests for F-001: JsonFilePersistence replacing PicklePersistence.

Covers:
- Fresh start with no file creates empty persistence
- Data survives flush + reload cycle
- Corrupt file is handled gracefully (starts fresh)
- Missing file is handled gracefully (starts fresh)
- File permissions are set to 0600
- Atomic write via tmp file prevents corruption on crash
- Conversation state round-trips correctly
- user_data round-trips correctly
- main.py uses JsonFilePersistence, not PicklePersistence
"""

import asyncio
import json
import os
import stat
from pathlib import Path

import pytest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestJsonFilePersistence:
    """Tests for the JsonFilePersistence class."""

    def _make_persistence(self, tmp_path, filename="test_persist.json"):
        from bot.persistence import JsonFilePersistence

        return JsonFilePersistence(filepath=tmp_path / filename)

    def test_fresh_start_no_file(self, tmp_path):
        """Starting with no file creates empty persistence."""
        p = self._make_persistence(tmp_path)
        user_data = _run(p.get_user_data())
        assert user_data == {}
        conversations = _run(p.get_conversations("test"))
        assert conversations == {}

    def test_flush_creates_file(self, tmp_path):
        """Flushing writes a JSON file to disk."""
        filepath = tmp_path / "persist.json"
        p = self._make_persistence(tmp_path, "persist.json")
        _run(p.flush())
        assert filepath.exists()

        data = json.loads(filepath.read_text())
        assert "user_data_json" in data
        assert "conversations_json" in data

    def test_data_survives_flush_reload(self, tmp_path):
        """Data written by flush is restored on next load."""
        from bot.persistence import JsonFilePersistence

        filepath = tmp_path / "persist.json"

        # Write data
        p1 = JsonFilePersistence(filepath=filepath)
        _run(p1.update_user_data(12345, {"pending_report_zone": "Bugis"}))
        _run(p1.update_conversation("report_conversation", (12345, 12345), 3))
        _run(p1.flush())

        # Reload
        p2 = JsonFilePersistence(filepath=filepath)
        user_data = _run(p2.get_user_data())
        assert 12345 in user_data
        assert user_data[12345]["pending_report_zone"] == "Bugis"

        convs = _run(p2.get_conversations("report_conversation"))
        assert (12345, 12345) in convs
        assert convs[(12345, 12345)] == 3

    def test_corrupt_file_starts_fresh(self, tmp_path):
        """A corrupt JSON file is handled gracefully — starts with empty state."""
        filepath = tmp_path / "persist.json"
        filepath.write_text("THIS IS NOT JSON {{{", encoding="utf-8")

        p = self._make_persistence(tmp_path, "persist.json")
        user_data = _run(p.get_user_data())
        assert user_data == {}

    def test_empty_file_starts_fresh(self, tmp_path):
        """An empty file is handled gracefully."""
        filepath = tmp_path / "persist.json"
        filepath.write_text("", encoding="utf-8")

        # Empty string is not valid JSON, so it should start fresh
        p = self._make_persistence(tmp_path, "persist.json")
        user_data = _run(p.get_user_data())
        assert user_data == {}

    @pytest.mark.skipif(
        os.name == "nt", reason="File permissions not meaningful on Windows"
    )
    def test_file_permissions_0600(self, tmp_path):
        """Persistence file is created with 0600 permissions."""
        filepath = tmp_path / "persist.json"
        p = self._make_persistence(tmp_path, "persist.json")
        _run(p.flush())

        mode = stat.S_IMODE(filepath.stat().st_mode)
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"

    def test_atomic_write_no_partial_file(self, tmp_path):
        """Flush uses atomic write (tmp + rename), no .tmp file left behind."""
        filepath = tmp_path / "persist.json"
        tmp_file = tmp_path / "persist.tmp"

        p = self._make_persistence(tmp_path, "persist.json")
        _run(p.update_user_data(100, {"key": "value"}))
        _run(p.flush())

        assert filepath.exists()
        assert not tmp_file.exists()  # tmp file should be gone after rename

    def test_multiple_users_round_trip(self, tmp_path):
        """Multiple users' data round-trips correctly."""
        from bot.persistence import JsonFilePersistence

        filepath = tmp_path / "persist.json"

        p1 = JsonFilePersistence(filepath=filepath)
        _run(p1.update_user_data(100, {"zone": "Bugis", "lat": 1.3}))
        _run(p1.update_user_data(200, {"zone": "Orchard"}))
        _run(p1.flush())

        p2 = JsonFilePersistence(filepath=filepath)
        data = _run(p2.get_user_data())
        assert data[100]["zone"] == "Bugis"
        assert data[100]["lat"] == 1.3
        assert data[200]["zone"] == "Orchard"

    def test_bot_data_round_trip(self, tmp_path):
        """bot_data round-trips correctly."""
        from bot.persistence import JsonFilePersistence

        filepath = tmp_path / "persist.json"

        p1 = JsonFilePersistence(filepath=filepath)
        _run(p1.update_bot_data({"version": "1.7.0"}))
        _run(p1.flush())

        p2 = JsonFilePersistence(filepath=filepath)
        data = _run(p2.get_bot_data())
        assert data["version"] == "1.7.0"

    def test_overwrite_preserves_latest(self, tmp_path):
        """Multiple flushes overwrite the file with latest data."""
        from bot.persistence import JsonFilePersistence

        filepath = tmp_path / "persist.json"

        p = JsonFilePersistence(filepath=filepath)
        _run(p.update_user_data(100, {"step": 1}))
        _run(p.flush())

        _run(p.update_user_data(100, {"step": 5}))
        _run(p.flush())

        p2 = JsonFilePersistence(filepath=filepath)
        data = _run(p2.get_user_data())
        assert data[100]["step"] == 5


class TestMainUsesJsonPersistence:
    """Verify main.py imports and uses JsonFilePersistence."""

    def test_no_pickle_persistence_import(self):
        """main.py should not import PicklePersistence."""
        source = Path("bot/main.py").read_text()
        assert "import PicklePersistence" not in source
        assert "= PicklePersistence(" not in source

    def test_json_persistence_import(self):
        """main.py should import JsonFilePersistence."""
        source = Path("bot/main.py").read_text()
        assert "JsonFilePersistence" in source
