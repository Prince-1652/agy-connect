"""Example 3: Antigravity Interactive CLI Chatbot.

Features:
- Instant warm worker initialization (<0.02s) via WorkerPool.
- Real-time token-by-token streaming.
- Authentic Antigravity CLI progress feedback (tools, commands, thinking).
- Mid-session limit failover with automated fallback models.
- Interactive question & permission handling (ask_question callbacks).
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

def handle_cli_question(q: dict) -> dict:
    """Prompt user interactively in terminal when agent asks a question."""
    question_text = q.get("question") or q.get("prompt") or str(q)
    options = q.get("options") or []
    print(f"\n[Agent Question]: {question_text}")
    if options:
        for idx, opt in enumerate(options, 1):
            print(f"  [{idx}] {opt}")
        choice = input("Select option or type answer: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return {"selected": options[int(choice) - 1]}
        return {"response": choice}
    ans = input("Your answer: ").strip()
    return {"response": ans}

def main() -> None:
    print_banner()

    # Pre-warm worker pool in background
    t0 = time.time()
    warmup(wait=False)

    # Initialize chat using pre-warmed pool worker with quota fallback chain
    config = Config(
        model="gemini-3.8-flash-high",
        fallback_models=["gemini-3.8-flash-medium", "gemini-3.8-flash-low"],
        use_pool=True,
    )
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

                if user_input == "/model" or user_input.startswith("/model "):
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 1:
                        print(f"\nActive model: {chat.config.model or 'CLI default (settings.json)'}")
                        print("Usage: /model <name> | /model default | /models\n")
                        continue

                    target = parts[1].strip()
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
                    print(f"Uptime     : {h.get('uptime', 0):.1f}s")
                    print(f"Fallbacks  : {chat.config.fallback_models}\n")
                    continue

                if user_input == "/clear":
                    chat.reset()
                    print("\nConversation history cleared.\n")
                    continue

                # Intercept any unrecognized slash commands so they don't break stream-json
                if user_input.startswith("/"):
                    print(f"\nUnknown slash command: '{user_input}'. Type '/help' for available commands.\n")
                    continue

                # Stream response tokens live with native CLI states and question callbacks
                chat.stream_cli(user_input, prefix="Agy> ", on_question=handle_cli_question)

            except (KeyboardInterrupt, EOFError):
                print("\n\nSession interrupted. Exiting...")
                break

    print("Session ended cleanly.")

if __name__ == "__main__":
    main()
