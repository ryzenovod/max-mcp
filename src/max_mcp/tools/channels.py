from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..client import AppCtx
from ..normalize import post_to_dict


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_channel_posts(
        ctx: Context[ServerSession, AppCtx],
        channel_id: int,
        limit: int = 50,
        before_time: int | None = None,
    ) -> dict[str, Any]:
        """List recent posts of a MAX channel (backward pagination via `before_time`, unix int)."""
        client = ctx.request_context.lifespan_context.client
        page = await client.fetch_history(
            chat_id=channel_id, backward=limit, from_time=before_time
        )
        page = page or []
        posts = [post_to_dict(m) for m in page]
        next_before_time = posts[-1]["time"] - 1 if len(posts) >= limit else None
        return {"posts": posts, "next_before_time": next_before_time}

    @mcp.tool()
    async def dump_channel(
        ctx: Context[ServerSession, AppCtx],
        channel_id: int,
        since_time: int | None = None,
        max_posts: int = 1000,
    ) -> dict[str, Any]:
        """Dump channel posts backward until `max_posts` or `since_time` reached.

        Hard cap 1000 posts per call to fit MCP output limits. For full archives,
        call repeatedly with shrinking `before_time` (use the smallest `time` from
        previous batch).
        """
        client = ctx.request_context.lifespan_context.client
        max_posts = min(max_posts, 1000)
        posts: list[dict[str, Any]] = []
        before_time: int | None = None
        stopped = "exhausted"
        batch = 100
        while len(posts) < max_posts:
            page = await client.fetch_history(
                chat_id=channel_id, backward=batch, from_time=before_time
            )
            page = page or []
            if not page:
                break
            stop = False
            for m in page:
                d = post_to_dict(m)
                t = d.get("time")
                if since_time is not None and t is not None and t < since_time:
                    stop = True
                    stopped = "since_time"
                    break
                posts.append(d)
                if len(posts) >= max_posts:
                    stop = True
                    stopped = "max_posts"
                    break
            if stop:
                break
            if len(page) < batch:
                break
            last_time = page[-1].time if hasattr(page[-1], "time") else post_to_dict(page[-1]).get("time")
            if last_time is None:
                break
            before_time = last_time - 1
        return {"posts": posts, "count": len(posts), "stopped_reason": stopped}
