from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import chat_to_dict
from ._common import positive_int


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_chats(
        ctx: Context[ServerSession, AppCtx],
        limit: int = 50,
        marker: int | None = None,
    ) -> dict[str, Any]:
        """Получить список чатов MAX с курсорной пагинацией через marker."""
        limit = positive_int("limit", limit, maximum=100)
        client = ctx.request_context.lifespan_context.client
        page = await client.fetch_chats(marker=marker) or []
        chats = [chat_to_dict(chat) for chat in page[:limit]]

        next_marker: int | None = None
        if len(page) >= limit:
            timestamps = [
                chat["last_event_time"]
                for chat in chats
                if isinstance(chat.get("last_event_time"), int)
            ]
            if timestamps:
                next_marker = min(timestamps) - 1
        return {"chats": chats, "next_marker": next_marker}

    @mcp.tool()
    async def get_chat(
        ctx: Context[ServerSession, AppCtx],
        chat_id: int,
    ) -> dict[str, Any]:
        """Получить сведения об одном чате или канале MAX по его id."""
        client = ctx.request_context.lifespan_context.client
        chat = await client.get_chat(chat_id)
        return chat_to_dict(chat)
