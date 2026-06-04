from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import chat_to_dict


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_chats(
        ctx: Context[ServerSession, AppCtx],
        limit: int = 50,
        marker: int | None = None,
    ) -> dict[str, Any]:
        """List user's MAX chats (cursor-paginated via `marker`)."""
        client = ctx.request_context.lifespan_context.client
        page = await client.fetch_chats(marker=marker)
        chats = [chat_to_dict(c) for c in page[:limit]]
        next_marker: int | None = None
        if len(page) >= limit:
            timestamps = [c["last_event_time"] for c in chats if c.get("last_event_time")]
            if timestamps:
                next_marker = min(timestamps) - 1
        return {"chats": chats, "next_marker": next_marker}

    @mcp.tool()
    async def get_chat(
        ctx: Context[ServerSession, AppCtx],
        chat_id: int,
    ) -> dict[str, Any]:
        """Get info about a single MAX chat/channel by id."""
        client = ctx.request_context.lifespan_context.client
        chat = await client.get_chat(chat_id)
        return chat_to_dict(chat)
