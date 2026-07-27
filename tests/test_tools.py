import asyncio
from types import SimpleNamespace

from max_mcp.tools import channels, messages


class FakeMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator


class HistoryClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    async def fetch_history(self, *, chat_id, backward, from_time):
        self.calls.append(
            {"chat_id": chat_id, "backward": backward, "from_time": from_time}
        )
        return self.pages.pop(0) if self.pages else []


def make_ctx(client):
    return SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(client=client)
        )
    )


def message(timestamp: int, text: str = ""):
    return SimpleNamespace(
        id=timestamp,
        chat_id=1,
        sender=2,
        text=text,
        time=timestamp,
        type="USER",
        prev_message_id=None,
        attaches=[],
        reaction_info=None,
        stats=None,
    )


def test_search_respects_scan_limit() -> None:
    mcp = FakeMCP()
    messages.register(mcp)
    client = HistoryClient([[message(i, "text") for i in range(10, 0, -1)]])

    result = asyncio.run(
        mcp.tools["search_messages"](
            make_ctx(client),
            query="missing",
            chat_id=1,
            limit=50,
            scan_limit=3,
        )
    )

    assert result["scanned"] == 3
    assert client.calls[0]["backward"] == 3


def test_dump_channel_continues_from_before_time() -> None:
    mcp = FakeMCP()
    channels.register(mcp)
    client = HistoryClient([[message(90), message(80)]])

    result = asyncio.run(
        mcp.tools["dump_channel"](
            make_ctx(client),
            channel_id=7,
            max_posts=2,
            before_time=100,
        )
    )

    assert client.calls[0]["from_time"] == 100
    assert result["stopped_reason"] == "max_posts"
    assert result["next_before_time"] == 79
