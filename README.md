# agy-connect

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**agy-connect** is a production-grade Python runtime and SDK that bridges your Python applications seamlessly with the Antigravity CLI (`agy`).

It completely abstracts away all subprocess management, inter-process communication, and session state tracking, providing a clean, robust, and strongly-typed API for interacting with the `agy` AI coding assistant natively in Python.

---

## 🚀 Key Features

* **Zero API Key Requirement:** `agy-connect` securely piggybacks off your local Antigravity CLI's existing credentials and setup.
* **Native Context Memory:** Takes full advantage of `agy`'s native memory management by isolating chats into physical directory structures. Conversations maintain perfect memory across multiple requests!
* **Real-time Streaming:** Fetch tokens as they arrive instantly using the async generators (`chat.stream()`).
* **Session Management:** Built-in `SessionManager` utilizes LRU (Least Recently Used) caching with configurable auto-expiration to manage hundreds of simultaneous chats efficiently.
* **Robust Process Management:** Handles batch processing intelligently. If `agy` hangs or crashes, the SDK detects it and optionally performs auto-recovery.
* **Dual API Support:** Complete support for both highly scalable `asyncio` applications (via `SessionManager`) and simple synchronous scripts (via `Chat`).
* **Health Metrics:** Check CPU/process uptime and state machine transitions in real time (`chat.health()`).

---

## 📦 Installation

```bash
pip install agy-connect
```

**Prerequisites:** You must have the [Antigravity CLI](https://github.com/google/antigravity) installed on your system.
*If `agy` is missing from your system PATH, the library will gracefully raise an `AgyNotInstalled` exception guiding the user on how to install it.*

---

## 💻 Usage & Quick Start

### 1. Synchronous Chatbot (Simple Scripts)
The `Chat` class provides an easy-to-use, blocking interface perfect for automation scripts.

```python
from agy_connect import Chat

def main():
    chat = Chat()
    print("User: Hello!")
    
    # Send a prompt and wait for the complete response
    response = chat.send("Hello!")
    print(f"Agy: {response}")
    
    # Context memory is naturally maintained!
    response2 = chat.send("What did I just say?")
    print(f"Agy: {response2}")
    
if __name__ == "__main__":
    main()
```

### 2. Streaming Responses
If you want to render text back to a user in real-time (like ChatGPT):

```python
import sys
from agy_connect import Chat

chat = Chat()

print("Agy: ", end="")
for chunk in chat.stream("Write a short poem about code."):
    sys.stdout.write(chunk)
    sys.stdout.flush()
print()
```

### 3. Asynchronous APIs (FastAPI / Web Servers)
For high-performance non-blocking code, use the `SessionManager`.

```python
import asyncio
from agy_connect import SessionManager, Config

async def run_server():
    # Configure session limits and timeouts
    config = Config(max_sessions=10, idle_timeout=300)
    manager = SessionManager(config)
    
    # Request a specific session (Memory is tied to "user_123")
    session = await manager.get("user_123")
    
    # Stream asynchronously
    async for chunk in session.stream("Explain asyncio."):
        print(chunk, end="", flush=True)
        
    # Cleanup memory
    await manager.shutdown()

asyncio.run(run_server())
```

---

## 🏗 Architecture & Design

`agy-connect` uses an event-driven, state-machine architecture under the hood to ensure predictable process execution.

### The Problem it Solves
The Antigravity CLI intentionally disables its interactive REPL mode when standard streams are piped (waiting for an `EOF` before processing anything). This makes a long-running persistent subprocess impossible.

### The Solution (Batch-Mode Strategy)
`agy-connect` embraces batch-mode processing using isolated workspaces.
1. When a new session is requested, a unique session folder is dynamically created (`/sessions/<session_id>`).
2. When a prompt is sent, `agy-connect` explicitly prepends the entire Python-side tracked history to ensure context isn't lost.
3. It spawns a fresh, ephemeral `agy` process in that directory, immediately flushes `stdin`, and sends an `EOF`.
4. It attaches an async reader to `stdout` to yield the tokens back to your application as `agy` generates them, then terminates the ephemeral process cleanly.

### State Machine
Every adapter tracks its state strictly using `agy_connect.constants`:
`STOPPED -> STARTING -> READY -> STREAMING -> READY`

---

## 🛠 Configuration

You can customize the library's behavior entirely by injecting a `Config` object:

```python
from agy_connect import Chat, Config

config = Config(
    executable_path="/custom/path/to/agy", # Override auto-discovery
    idle_timeout=60,                       # Clean up session memory after 60s
    stream_chunk_size=512,                 # Byte sizes yielded during streams
    debug_mode=True                        # Enable verbose logger traces
)

chat = Chat(config)
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check the [issues page](https://github.com/Prince-1652/agy-connect/issues).

## 📝 License

This project is [MIT](https://github.com/Prince-1652/agy-connect/blob/main/LICENSE) licensed.
