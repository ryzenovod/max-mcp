# max-mcp

> MCP server that gives Claude Code full access to your **MAX** messenger account — read chats, dump channels, send messages and files.

MAX (max.ru) is a Russian messenger by VK with ~50 M users. This server uses a **user session** (not a bot token), so it can access your DM list, arbitrary channels, and post on your behalf — things the official Bot API cannot do.

---

## What is MCP?

[Model Context Protocol](https://modelcontextprotocol.io) is an open standard by Anthropic that lets AI assistants call external tools. This server speaks the MCP stdio transport and plugs directly into **Claude Code** (`claude` CLI / desktop app).

---

## Why user session, not Bot API

The official MAX Bot API (`platform-api.max.ru`) can only act as a bot: it receives messages directed at the bot and replies in its own chats. It cannot:

- list your personal DMs
- read channels you didn't create
- send messages as you (not as a bot)

For SMM analytics and content workflows you need a **user-level session** — the same identity as your own MAX account. This server achieves that through [`maxapi-python`](https://pypi.org/project/maxapi-python/) (PyMax), an unofficial wrapper that speaks MAX's internal WebSocket protocol.

> **Risk:** PyMax technically violates MAX Terms of Service. Use a dedicated SMM account, not your personal one.

---

## Architecture

```
~/Documents/claude-projects/max-mcp/   ← code (permanent)
  pyproject.toml
  uv.lock
  src/max_mcp/
    server.py        # FastMCP stdio entrypoint
    client.py        # WebClient/Client singleton + lifespan
    auth.py          # CLI for login-qr / login-sms
    normalize.py     # pymax models → plain JSON dicts
    tools/
      chats.py       # list_chats, get_chat
      messages.py    # read_messages, search_messages
      channels.py    # list_channel_posts, dump_channel
      send.py        # send_message, send_file

~/.max-mcp/                            ← session (permanent, secret)
  session.db        # pymax SQLite session — chmod 600
  session.kind      # "web" or "sms" — picks client type at start
  session.phone     # E.164 phone if kind=sms — chmod 600
```

Code and session live in separate locations on purpose: the code can be deleted and rebuilt without losing your MAX login.

---

## Requirements

- macOS / Linux
- Python 3.11 – 3.13
- [uv](https://github.com/astral-sh/uv) (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

---

## Setup

### 1. Install dependencies

```bash
git clone https://github.com/renosaza/max-mcp.git ~/Documents/claude-projects/max-mcp
cd ~/Documents/claude-projects/max-mcp
uv sync
```

### 2. Authenticate

Pick one method:

**QR code (requires mobile MAX app):**

```bash
uv run python -m max_mcp.auth login-qr
```

An ASCII QR appears in your terminal. In the MAX mobile app: **Settings → Devices → Link Device → scan**. On success you'll see:

```
Logged in as: Your Name (id=123456789)
```

**SMS + password (no phone app needed):**

```bash
uv run python -m max_mcp.auth login-sms --phone +79991234567
```

PyMax prompts interactively for the SMS code (arrives in MAX or as SMS) and, if 2FA is enabled, your password.

### 3. Register in Claude Code

```bash
claude mcp add max-mcp --scope user \
  -- uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.server
```

Verify it's connected:

```bash
claude mcp list
# max-mcp: uv run --directory ... — ✓ Connected
```

In an active Claude Code session: `/mcp` → reconnect, or open a new chat.

---

## Available tools (8 total)

All IDs (`chat_id`, `channel_id`) are integers. Discover them via `list_chats`.

### Reading

#### `list_chats(limit=50, marker=None)`

Returns your chat list. Cursor-paginated: pass `next_marker` from the previous response to get the next page.

```json
{
  "chats": [
    {
      "id": 123456789,
      "title": "Team chat",
      "type": "CHAT",
      "last_event_time": 1717520000000,
      "participants_count": 12,
      "description": null,
      "owner_id": 987654321
    }
  ],
  "next_marker": 1717510000000
}
```

Chat `type` values: `DIALOG`, `CHAT`, `CHANNEL`.

**API note:** `last_event_time` is a unix timestamp in **milliseconds**. The `marker` cursor is timestamp-based (not ID-based).

---

#### `get_chat(chat_id)`

Full info on a single chat or channel.

```json
{
  "id": -69531237780213,
  "title": "My Channel",
  "type": "CHANNEL",
  "last_event_time": 1717520000000,
  "participants_count": 4200,
  "description": "Channel description",
  "owner_id": 100500
}
```

---

#### `read_messages(chat_id, limit=50, before_time=None)`

Message history, newest-first. Paginate backward by passing `next_before_time` from the previous response as `before_time`.

```json
{
  "messages": [
    {
      "id": 116691985249148380,
      "chat_id": null,
      "sender": 5267903,
      "text": "Hello!",
      "time": 1717520000123,
      "type": "USER",
      "reply_to_id": null,
      "attaches": [...]
    }
  ],
  "next_before_time": 1717519000000
}
```

`next_before_time` is `null` when the history is exhausted.

**API notes:**
- `time` is unix milliseconds.
- `sender` is a numeric user ID (no name — use `get_chat` for group metadata).
- `chat_id` in messages may be `null` (DMs don't include it in pymax 2.1.2).
- `attaches` is only present when the message has attachments. Shape varies by type: `PHOTO`, `VIDEO`, `FILE`, `CALL`, `INLINE_KEYBOARD`, `SHARE`, `CONTROL`.
- `reply_to_id` is populated only when `type == "REPLY"` (uses `prev_message_id` field).

---

#### `search_messages(query, chat_id, limit=50, scan_limit=500)`

**Client-side substring search** — MAX has no native server-side search.

Walks message history backward in batches of 100, filters case-insensitively. Returns matching messages up to `limit`.

```json
{
  "messages": [...],
  "scanned": 342,
  "scan_exhausted": false
}
```

`scan_exhausted: true` means the scan hit `scan_limit` without reaching the beginning of history. Increase `scan_limit` and paginate.

**API note:** This can be slow on large chats (1 API call per 100 messages). For chats with thousands of messages, use a reasonable `scan_limit` (e.g. 2000) and expect a few seconds of latency.

---

#### `list_channel_posts(channel_id, limit=50, before_time=None)`

Channel posts with reactions and stats. Same pagination as `read_messages`.

```json
{
  "posts": [
    {
      "id": 116691985249148380,
      "sender": 5267903,
      "text": "Post text",
      "time": 1717520000123,
      "type": "USER",
      "reaction_info": {...},
      "stats": {"views": 1234}
    }
  ],
  "next_before_time": 1717519000000
}
```

**API note:** `stats` shape is opaque — pymax surfaces the raw dict from the MAX server. The `views` key is present on most posts, but not guaranteed. `reaction_info` is also raw.

---

#### `dump_channel(channel_id, since_time=None, max_posts=1000)`

Bulk dump for analytics. Hard cap of 1000 posts per call.

```json
{
  "posts": [...],
  "count": 1000,
  "stopped_reason": "max_posts"
}
```

`stopped_reason` values:
- `max_posts` — hit the `max_posts` cap (call again with smaller `before_time`)
- `since_time` — reached the requested time boundary
- `exhausted` — reached the beginning of channel history

**Full archive pattern:**

```python
# pseudocode for Claude to iterate
before_time = None
all_posts = []
while True:
    result = dump_channel(channel_id=X, max_posts=1000, before_time=before_time)
    all_posts.extend(result["posts"])
    if result["stopped_reason"] != "max_posts":
        break
    before_time = min(p["time"] for p in result["posts"]) - 1
```

---

### Writing

#### `send_message(chat_id, text, reply_to_id=None)`

Send a text message. Optionally reply to a specific message by ID.

```json
{
  "id": 116692035197621360,
  "sender": 309991366,
  "text": "Hello!",
  "time": 1717520000000,
  "type": "USER",
  "reply_to_id": null
}
```

---

#### `send_file(chat_id, file_path, caption=None)`

Send a file. Attachment type is chosen by extension:

| Extensions | MAX type |
|---|---|
| `.jpg .jpeg .png .gif .webp .bmp` | Photo |
| `.mp4 .mov .webm` | Video |
| anything else | File |

`file_path` must be an **absolute path** to a regular file (no symlinks).

**Security:** By default only paths inside `~/Downloads`, `~/Documents`, and `/tmp` are allowed. Paths under `~/.ssh`, `~/.aws`, `~/.max-mcp`, `/etc`, `/var`, and macOS Keychains are always denied. Override the allowlist:

```bash
export MAX_MCP_SEND_ROOTS=~/Desktop:/data/exports
```

---

## Output field reference

| Field | Type | Notes |
|---|---|---|
| `id` | int | Message / post ID (int64) |
| `sender` | int | Sender user ID |
| `time` | int | Unix timestamp, **milliseconds** |
| `type` | str | `"USER"`, `"REPLY"`, `"BOT"`, etc. |
| `reply_to_id` | int \| null | Populated only when `type == "REPLY"` |
| `attaches` | list | Present only if attachments exist |
| `last_event_time` | int | Chat's last activity, milliseconds |
| `participants_count` | int | Members in chat/channel |

---

## Operations

### Re-login (session expired or switching accounts)

```bash
rm ~/.max-mcp/session.db ~/.max-mcp/session.kind ~/.max-mcp/session.phone
uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.auth login-qr
# or login-sms
```

### Switch from QR to SMS auth (or vice versa)

Delete all session files (above) and re-run the desired auth flow. The session type is stored in `~/.max-mcp/session.kind` and determines whether `WebClient` (QR) or `Client` (SMS) is used at startup.

### Debug a hung or crashed server

```bash
uv run --directory ~/Documents/claude-projects/max-mcp python -m max_mcp.server
```

Errors surface to stderr — pymax exceptions are not swallowed.

Then in Claude Code: `/mcp` → reconnect.

### Increase output budget for large channel dumps

The default MCP stdio frame warns at ~10 k tokens and caps around 25 k. For `dump_channel(max_posts=1000)` on busy channels this can be exceeded. Set in your environment:

```bash
export MAX_MCP_OUTPUT_TOKENS=80000
```

---

## Known limitations

| Limitation | Workaround |
|---|---|
| No native server-side search | `search_messages` scans client-side. Increase `scan_limit` for deeper history coverage. |
| `marker` for `list_chats` is timestamp-based (assumed from pymax internals) | Works in practice; may misbehave if MAX ever changes the semantics. |
| `stats` / `reaction_info` schema is undocumented | Inspect the raw output on real channel posts. |
| `reply_to_id` requires `type == "REPLY"` (string, uppercased) | If pymax changes the enum serialization, replies will always return `null`. |
| Sessions don't auto-refresh indefinitely | Re-run `login-qr` / `login-sms` when the session expires. |
| `dump_channel` hard cap = 1000 posts/call | Call repeatedly with decreasing `before_time`. |
| `sender` is a numeric ID, not a name | MAX has no public user-lookup endpoint in the user-session API. |
| `chat_id` is `null` in DM messages | This is a pymax 2.1.2 behaviour for direct messages. |

---

## Security

- `~/.max-mcp/` is created `chmod 700`; files are `chmod 600`.
- Session files are written with `O_CREAT|O_EXCL|O_NOFOLLOW` (no TOCTOU, no symlink follow).
- `send_file` validates paths against a denylist (`~/.ssh`, `~/.aws`, etc.) and an allowlist (`~/Downloads`, `~/Documents`, `/tmp` by default). Symlinks are rejected at the leaf.
- The server runs locally over stdio — no network port is opened.

---

## Dependencies

- `mcp[cli] >= 1.0` — Anthropic MCP SDK (FastMCP, stdio transport)
- `maxapi-python >= 2.1.2` — PyMax, unofficial MAX WebSocket wrapper (MIT)
- `pydantic >= 2.6`
- Python 3.11 – 3.13

`uv.lock` pins the full transitive closure (e.g. `mcp==1.27.2`, `qrcode==8.2`).

---

## Risk and compliance

PyMax uses MAX's internal WebSocket API. Practical risks:

1. **Account suspension** — VK may detect automation patterns and suspend the account.
2. **API drift** — MAX can change its protocol without notice; PyMax may break until updated.
3. **Rate limits** — not publicly documented; pace your `dump_channel` calls.

Mitigation: use a **dedicated SMM account**, not your personal one. Don't send high-volume outgoing messages.

---

## License

MIT
