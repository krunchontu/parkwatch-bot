# Error Log

## 2026-02-15
- `pytest --collect-only -q` failed initially due to missing `pytest_asyncio` in the environment (dev deps not installed in runtime-only setup).
