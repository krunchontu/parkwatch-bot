"""Lightweight health check HTTP server for ParkWatch SG.

Provides a /health endpoint for deployment platform monitoring (Railway, Render,
Kubernetes, etc.). Uses Python's built-in asyncio — no extra dependencies.
"""

import asyncio
import contextlib
import json
import logging
from datetime import datetime, timezone

from config import BOT_VERSION

logger = logging.getLogger(__name__)

_server: asyncio.AbstractServer | None = None


async def start_health_server(port: int, run_mode: str = "polling") -> None:
    """Start the health check HTTP server on the given port."""
    global _server

    async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            request_line = data.decode(errors="replace").split("\r\n")[0] if data else ""

            if request_line.startswith("GET /health"):
                body = json.dumps(
                    {
                        "status": "ok",
                        "version": BOT_VERSION,
                        "mode": run_mode,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                header = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                )
            else:
                body = json.dumps({"error": "not found"})
                header = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                )

            writer.write((header + body).encode())
            await writer.drain()
        except asyncio.TimeoutError:
            pass
        except Exception:
            logger.debug("Health check request handling error", exc_info=True)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    _server = await asyncio.start_server(handle_request, "0.0.0.0", port)
    logger.info("Health check server started on port %d (GET /health)", port)


async def stop_health_server() -> None:
    """Stop the health check HTTP server."""
    global _server
    if _server is not None:
        _server.close()
        await _server.wait_closed()
        _server = None
        logger.info("Health check server stopped")
