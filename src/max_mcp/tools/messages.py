from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import message_to_dict
from ._common import item_time, next_before_time, positive_int


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def read_messages(
        ctx: Context[ServerSession, AppCtx],
        chat_id: int,
        limit: int = 50,
        before_time: int | None = None,
    ) -> dict[str, Any]:
        """Прочитать историю чата; before_time листает историю назад."""
        limit = positive_int("limit", limit, maximum=100)
        client = ctx.request_context.lifespan_context.client
        page = await client.fetch_history(
            chat_id=chat_id,
            backward=limit,
            from_time=before_time,
        ) or []
        messages = [message_to_dict(message) for message in page]
        cursor = next_before_time(messages, page_is_full=len(page) >= limit)
        return {"messages": messages, "next_before_time": cursor}

    @mcp.tool()
    async def search_messages(
        ctx: Context[ServerSession, AppCtx],
        query: str,
        chat_id: int,
        limit: int = 50,
        scan_limit: int = 500,
    ) -> dict[str, Any]:
        """Искать подстроку локальным проходом по истории указанного чата."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        limit = positive_int("limit", limit, maximum=100)
        scan_limit = positive_int("scan_limit", scan_limit, maximum=10_000)

        client = ctx.request_context.lifespan_context.client
        needle = query.casefold()
        hits: list[dict[str, Any]] = []
        before_time: int | None = None
        scanned = 0
        history_exhausted = False

        while scanned < scan_limit and len(hits) < limit:
            batch_size = min(100, scan_limit - scanned)
            page = await client.fetch_history(
                chat_id=chat_id,
                backward=batch_size,
                from_time=before_time,
            ) or []
            if not page:
                history_exhausted = True
                break

            for message in page:
                if scanned >= scan_limit or len(hits) >= limit:
                    break
                scanned += 1
                normalized = message_to_dict(message)
                text = (normalized.get("text") or "").casefold()
                if needle in text:
                    hits.append(normalized)

            if len(page) < batch_size:
                history_exhausted = True
                break

            last_time = item_time(page[-1])
            if last_time is None:
                break
            before_time = last_time - 1

        return {
            "messages": hits,
            "scanned": scanned,
            "scan_exhausted": scanned >= scan_limit and not history_exhausted,
            "history_exhausted": history_exhausted,
        }
