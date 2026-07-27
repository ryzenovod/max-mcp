from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import post_to_dict
from ._common import item_time, next_before_time, positive_int


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_channel_posts(
        ctx: Context[ServerSession, AppCtx],
        channel_id: int,
        limit: int = 50,
        before_time: int | None = None,
    ) -> dict[str, Any]:
        """Получить публикации канала; before_time листает историю назад."""
        limit = positive_int("limit", limit, maximum=100)
        client = ctx.request_context.lifespan_context.client
        page = await client.fetch_history(
            chat_id=channel_id,
            backward=limit,
            from_time=before_time,
        ) or []
        posts = [post_to_dict(message) for message in page]
        cursor = next_before_time(posts, page_is_full=len(page) >= limit)
        return {"posts": posts, "next_before_time": cursor}

    @mcp.tool()
    async def dump_channel(
        ctx: Context[ServerSession, AppCtx],
        channel_id: int,
        since_time: int | None = None,
        max_posts: int = 1000,
        before_time: int | None = None,
    ) -> dict[str, Any]:
        """Выгрузить до 1000 публикаций канала с поддержкой продолжения выгрузки."""
        max_posts = positive_int("max_posts", max_posts, maximum=1000)
        client = ctx.request_context.lifespan_context.client
        posts: list[dict[str, Any]] = []
        cursor = before_time
        stopped = "exhausted"

        while len(posts) < max_posts:
            batch_size = min(100, max_posts - len(posts))
            page = await client.fetch_history(
                chat_id=channel_id,
                backward=batch_size,
                from_time=cursor,
            ) or []
            if not page:
                break

            reached_since_time = False
            for message in page:
                normalized = post_to_dict(message)
                timestamp = item_time(normalized)
                if (
                    since_time is not None
                    and timestamp is not None
                    and timestamp < since_time
                ):
                    reached_since_time = True
                    stopped = "since_time"
                    break
                posts.append(normalized)
                if len(posts) >= max_posts:
                    stopped = "max_posts"
                    break

            if reached_since_time or len(posts) >= max_posts:
                break
            if len(page) < batch_size:
                break

            last_time = item_time(page[-1])
            if last_time is None:
                stopped = "invalid_cursor"
                break
            cursor = last_time - 1

        next_cursor = next_before_time(
            posts,
            page_is_full=stopped == "max_posts" and bool(posts),
        )
        return {
            "posts": posts,
            "count": len(posts),
            "stopped_reason": stopped,
            "next_before_time": next_cursor,
        }
