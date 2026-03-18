"""JSON file-backed persistence for ParkWatch SG.

Replaces PicklePersistence to eliminate the arbitrary code execution risk
inherent in Python's pickle deserialization. Uses telegram.ext.DictPersistence
(JSON-based, in-memory) as the base and adds file I/O on flush.

Data stored: conversation states (report flow step per user), user_data
(pending report zone/description/GPS, pending admin operations), bot_data
(empty). All JSON-serializable.
"""

import json
import logging
import os
from pathlib import Path

from telegram.ext import DictPersistence

logger = logging.getLogger(__name__)


class JsonFilePersistence(DictPersistence):
    """DictPersistence subclass that persists state to a JSON file.

    Loads existing data on init, writes on every flush (called by the
    Application at ``update_interval`` and on shutdown).

    File permissions are set to 0600 (owner read/write only) to prevent
    other users on the system from reading conversation state.
    """

    def __init__(self, filepath: str | Path, **kwargs) -> None:  # type: ignore[override]
        self._filepath = Path(filepath)

        # Load existing data from disk if available
        user_data_json = ""
        chat_data_json = ""
        bot_data_json = ""
        conversations_json = ""
        callback_data_json = ""

        if self._filepath.exists():
            try:
                raw = self._filepath.read_text(encoding="utf-8")
                data = json.loads(raw)
                user_data_json = data.get("user_data_json", "") or ""
                chat_data_json = data.get("chat_data_json", "") or ""
                bot_data_json = data.get("bot_data_json", "") or ""
                conversations_json = data.get("conversations_json", "") or ""
                callback_data_json = data.get("callback_data_json", "") or ""
                logger.info("Loaded persistence data from %s", self._filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not load persistence file %s (%s), starting fresh",
                    self._filepath,
                    exc,
                )

        super().__init__(
            user_data_json=user_data_json,
            chat_data_json=chat_data_json,
            bot_data_json=bot_data_json,
            conversations_json=conversations_json,
            callback_data_json=callback_data_json,
            **kwargs,
        )

    async def flush(self) -> None:
        """Write all persistence data to the JSON file.

        Called by the Application at the configured update_interval
        (default 60s) and on graceful shutdown.
        """
        data = {
            "user_data_json": self.user_data_json,
            "chat_data_json": self.chat_data_json,
            "bot_data_json": self.bot_data_json,
            "conversations_json": self.conversations_json,
            "callback_data_json": self.callback_data_json,
        }

        try:
            tmp_path = self._filepath.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            # Restrict permissions before moving into place
            os.chmod(tmp_path, 0o600)
            tmp_path.replace(self._filepath)
        except OSError:
            logger.error("Failed to write persistence file %s", self._filepath, exc_info=True)
