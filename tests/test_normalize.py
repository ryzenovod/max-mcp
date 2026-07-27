from enum import Enum
from types import SimpleNamespace

from max_mcp.normalize import chat_to_dict, message_to_dict


class MessageType(Enum):
    REPLY = "REPLY"


def test_chat_keeps_falsy_values() -> None:
    chat = SimpleNamespace(
        id=0,
        title="",
        type="CHAT",
        last_event_time=0,
        participants_count=0,
        description="",
        owner=0,
    )

    result = chat_to_dict(chat)

    assert result["id"] == 0
    assert result["title"] == ""
    assert result["last_event_time"] == 0
    assert result["owner_id"] == 0


def test_reply_enum_is_normalized() -> None:
    message = SimpleNamespace(
        id=1,
        chat_id=2,
        sender=SimpleNamespace(id=3),
        text="ok",
        time=4,
        type=MessageType.REPLY,
        prev_message_id=5,
        attaches=[],
    )

    result = message_to_dict(message)

    assert result["type"] == "REPLY"
    assert result["reply_to_id"] == 5
    assert result["sender"] == 3
