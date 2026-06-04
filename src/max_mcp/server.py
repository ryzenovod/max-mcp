from mcp.server.fastmcp import FastMCP

from .client import lifespan
from .tools import channels, chats, messages, send

INSTRUCTIONS = (
    "MAX messenger user-session tools. Use list_chats/get_chat to discover chats. "
    "read_messages/list_channel_posts to fetch history. search_messages does "
    "client-side scan (slow). dump_channel for full archive (cap 1000 posts per "
    "call). send_message/send_file for writes."
)

mcp = FastMCP("max-mcp", instructions=INSTRUCTIONS, lifespan=lifespan)
chats.register(mcp)
messages.register(mcp)
channels.register(mcp)
send.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
