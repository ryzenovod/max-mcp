import os
import pathlib
import stat
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import message_to_dict

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

_HOME = pathlib.Path.home().resolve()
_DEFAULT_ROOTS = (_HOME / "Downloads", _HOME / "Documents", pathlib.Path("/tmp"))
_DENY_ROOTS = (
    _HOME / ".max-mcp",
    _HOME / ".ssh",
    _HOME / ".aws",
    _HOME / ".gnupg",
    _HOME / ".config",
    _HOME / ".kube",
    _HOME / ".docker",
    _HOME / "Library" / "Keychains",
    pathlib.Path("/etc"),
    pathlib.Path("/private/etc"),
    pathlib.Path("/var"),
    pathlib.Path("/private/var"),
)


def _allowed_roots() -> tuple[pathlib.Path, ...]:
    env = os.environ.get("MAX_MCP_SEND_ROOTS")
    if not env:
        return tuple(path.resolve() for path in _DEFAULT_ROOTS if path.exists())
    roots: list[pathlib.Path] = []
    for raw in env.split(os.pathsep):
        raw = raw.strip()
        if raw:
            roots.append(pathlib.Path(raw).expanduser().resolve())
    return tuple(roots)


def _is_within(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_path(file_path: str) -> pathlib.Path:
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("file_path must be a non-empty string")
    if "\x00" in file_path:
        raise ValueError("file_path contains NUL byte")

    path = pathlib.Path(file_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (FileNotFoundError, RuntimeError) as exc:
        raise ValueError(f"file_path does not resolve: {exc}") from exc

    if stat.S_ISLNK(path.lstat().st_mode):
        raise ValueError("symlinks are not allowed as file_path")

    st = resolved.lstat()
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("file_path must point to a regular file")
    if st.st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")

    for deny in _DENY_ROOTS:
        try:
            deny_resolved = deny.resolve()
        except OSError:
            continue
        if _is_within(resolved, deny_resolved):
            raise PermissionError(f"path is under denied root: {deny}")

    roots = _allowed_roots()
    if not roots:
        raise PermissionError(
            f"no allowed roots configured; set MAX_MCP_SEND_ROOTS=/path1{os.pathsep}/path2"
        )
    if not any(_is_within(resolved, root) for root in roots):
        raise PermissionError(
            f"path is outside allowed roots: {[str(root) for root in roots]}"
        )
    return resolved


def _attachment(path: pathlib.Path) -> Any:
    from pymax import File, Photo, Video

    ext = path.suffix.lower()
    if ext in PHOTO_EXT:
        return Photo(path=str(path))
    if ext in VIDEO_EXT:
        return Video(path=str(path))
    return File(path=str(path))


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def send_message(
        ctx: Context[ServerSession, AppCtx],
        chat_id: int,
        text: str,
        reply_to_id: int | None = None,
    ) -> dict[str, Any]:
        """Отправить текстовое сообщение или ответ на указанное сообщение MAX."""
        if not isinstance(text, str) or not text:
            raise ValueError("text must be a non-empty string")
        client = ctx.request_context.lifespan_context.client
        sent = await client.send_message(
            chat_id=chat_id,
            text=text,
            reply_to=reply_to_id,
        )
        return message_to_dict(sent)

    @mcp.tool()
    async def send_file(
        ctx: Context[ServerSession, AppCtx],
        chat_id: int,
        file_path: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Отправить файл, фото или видео из разрешённого локального каталога."""
        path = _validate_path(file_path)
        client = ctx.request_context.lifespan_context.client
        attachment = _attachment(path)
        sent = await client.send_message(
            chat_id=chat_id,
            text=caption or "",
            attachments=[attachment],
        )
        return message_to_dict(sent)
