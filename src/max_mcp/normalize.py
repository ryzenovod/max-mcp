from typing import Any


def _dump(obj: Any) -> Any:
    if obj is None:
        return None
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump(mode="json", exclude_none=True)
    return obj


def chat_to_dict(chat: Any) -> dict[str, Any]:
    d = _dump(chat) or {}
    chat_type = d.get("type") or getattr(chat, "type", None)
    return {
        "id": d.get("id") or getattr(chat, "id", None),
        "title": d.get("title") or getattr(chat, "title", None),
        "type": str(chat_type) if chat_type is not None else None,
        "last_event_time": d.get("last_event_time"),
        "participants_count": d.get("participants_count"),
        "description": d.get("description"),
        "owner_id": d.get("owner"),
    }


def attach_to_dict(att: Any) -> dict[str, Any]:
    d = _dump(att) or {}
    kind = type(att).__name__
    d["_kind"] = kind
    return d


def _reply_to_id(msg: Any, d: dict[str, Any]) -> int | None:
    msg_type = d.get("type") or getattr(msg, "type", None)
    if str(msg_type).upper() == "REPLY":
        return d.get("prev_message_id") or getattr(msg, "prev_message_id", None)
    return None


def message_to_dict(msg: Any) -> dict[str, Any]:
    d = _dump(msg) or {}
    out = {
        "id": d.get("id"),
        "chat_id": d.get("chat_id"),
        "sender": d.get("sender"),
        "text": d.get("text"),
        "time": d.get("time"),
        "type": str(d.get("type")) if d.get("type") is not None else None,
        "reply_to_id": _reply_to_id(msg, d),
    }
    attaches = d.get("attaches") or getattr(msg, "attaches", None) or []
    if attaches:
        out["attaches"] = [
            attach_to_dict(a) if not isinstance(a, dict) else a for a in attaches
        ]
    return out


def post_to_dict(msg: Any) -> dict[str, Any]:
    base = message_to_dict(msg)
    d = _dump(msg) or {}
    if d.get("reaction_info") is not None:
        base["reaction_info"] = d["reaction_info"]
    if d.get("stats") is not None:
        base["stats"] = d["stats"]
    return base
