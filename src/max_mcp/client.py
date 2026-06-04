import asyncio
import os
import pathlib
import stat
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP
from pymax import Client, WebClient

SESSION_DIR = pathlib.Path.home() / ".max-mcp"
SESSION_FILE = "session.db"
KIND_FILE = "session.kind"
PHONE_FILE = "session.phone"


@dataclass
class AppCtx:
    client: Any  # WebClient | Client — both share the same public method surface


def _check_session_dir() -> None:
    st = SESSION_DIR.lstat()
    if stat.S_ISLNK(st.st_mode):
        raise RuntimeError(f"{SESSION_DIR} is a symlink; refusing to use")
    if st.st_uid != os.getuid():
        raise RuntimeError(f"{SESSION_DIR} is not owned by current user")
    if st.st_mode & 0o077:
        raise RuntimeError(
            f"{SESSION_DIR} permissions too open ({oct(st.st_mode & 0o777)}); "
            "tighten to 0700"
        )


def _read_secret(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    if path.is_symlink():
        raise RuntimeError(f"{path} is a symlink; refusing to read")
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        data = os.read(fd, 4096)
    finally:
        os.close(fd)
    return data.decode("utf-8").strip()


def _read_kind() -> tuple[str, str | None]:
    kind = _read_secret(SESSION_DIR / KIND_FILE) or "web"
    phone = _read_secret(SESSION_DIR / PHONE_FILE)
    return kind, phone


def _build_client():
    kind, phone = _read_kind()
    if kind == "sms":
        if not phone:
            raise RuntimeError(
                f"SMS session marker found but phone is missing. Re-login with: "
                f"uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.auth login-sms --phone +7..."
            )
        return Client(
            phone=phone,
            work_dir=str(SESSION_DIR),
            session_name=SESSION_FILE,
        )
    return WebClient(work_dir=str(SESSION_DIR), session_name=SESSION_FILE)


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[AppCtx]:
    session_path = SESSION_DIR / SESSION_FILE
    if not session_path.exists():
        raise RuntimeError(
            "MAX session missing. Run one of:\n"
            "  uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.auth login-qr\n"
            "  uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.auth login-sms --phone +7..."
        )
    _check_session_dir()

    client = _build_client()
    ready = asyncio.Event()

    @client.on_start()
    async def _ready(_c) -> None:
        ready.set()

    task = asyncio.create_task(client.start())
    try:
        await asyncio.wait_for(ready.wait(), timeout=30)
        yield AppCtx(client=client)
    finally:
        try:
            await client.stop()
        except Exception:
            pass
        task.cancel()
