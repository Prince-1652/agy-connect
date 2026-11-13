"""Example 3: Antigravity Interactive CLI Chatbot.

Features:
- Instant warm worker initialization (<0.02s) via WorkerPool.
- Real-time token-by-token streaming.
- Authentic Antigravity CLI progress feedback (tools, commands, thinking).
- Dynamic model switching with preserved context (/models, /model <name>).
- Slash commands: /help, /models, /model, /status, /clear.
"""

import sys
import time
from agy_connect import Chat, Config, warmup

def print_banner() -> None:
    print("=" * 60)
    print("  Antigravity CLI Interactive Chatbot (agy-connect)")
    print("  Type '/help' for commands, 'exit' to quit.")
    print("=" * 60)

def print_help() -> None:
    print("\nAvailable Commands:")
    print("  /models         - List available models")
    print("  /model <name>   - Switch model (preserves conversation context)")
    print("  /model default  - Revert to user's global CLI settings.json")
    print("  /status         - Display session health and process metrics")
    print("  /clear          - Clear conversation history")
    print("  /help           - Show this help message")
    print("  exit / quit     - Close session and exit\n")

def main() -> None:
    print_banner()

    # Pre-warm worker pool in background
    t0 = time.time()
    warmup(wait=False)

    # Initialize chat using pre-warmed pool worker
    config = Config(model="gemini-3.8-flash-low", use_pool=True)
    with Chat(config) as chat:
        init_latency = (time.time() - t0) * 1000
        active_model = chat.config.model or "CLI default (settings.json)"
        print(f"\n[Session ready in {init_latency:.1f}ms | Active model: {active_model}]\n")

        while True:
            try:
                user_input = input("You> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit"):
                    print("\nClosing session...")
                    break

                # Handle slash commands
                if user_input == "/help":
                    print_help()
                    continue

                if user_input == "/models":
                    print("\nAvailable Models:")
                    for m in chat.models():
                        is_active = (m["id"] == chat.config.model)
                        tag = " (active)" if is_active else ""
                        print(f"  - {m['id']:<26} : {m['name']}{tag}")
                    print()
                    continue

                if user_input.startswith("/model "):
                    target = user_input.split(maxsplit=1)[1].strip()
                    if target.lower() in ("default", "none"):
                        target = None

                    t_switch = time.time()
                    sys.stdout.write(f"\rSwitching model to {target or 'CLI default'}...")
                    sys.stdout.flush()
                    chat.switch_model(target)
                    elapsed = (time.time() - t_switch) * 1000
                    print(f"\rSwitched to {chat.config.model or 'CLI default'} in {elapsed:.0f}ms (context preserved).\n")
                    continue

                if user_input == "/status":
                    h = chat.health()
                    print(f"\nSession ID : {chat.session_id}")
                    print(f"Status     : {chat.status()}")
                    print(f"PID        : {h.get('pid')}")
                    print(f"Process    : {'Alive' if h.get('process_alive') else 'Stopped'}")
                    print(f"Uptime     : {h.get('uptime', 0):.1f}s\n")
                    continue

                if user_input == "/clear":
                    chat.reset()
                    print("\nConversation history cleared.\n")
                    continue

                # Stream response tokens live with native CLI states (thinking, tool execution, tokens)
                chat.stream_cli(user_input, prefix="Agy> ")

            except (KeyboardInterrupt, EOFError):
                print("\n\nSession interrupted. Exiting...")
                break

    print("Session ended cleanly.")

if __name__ == "__main__":
    main()
