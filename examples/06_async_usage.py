"""Example 6: Async Usage with Quota Failover and Question Callbacks"""

import asyncio
from agy_connect import SessionManager, Config

async def handle_async_question(q: dict) -> dict:
    """Async question responder."""
    print(f"\n[Async Hook] Question received: {q.get('question')}")
    return {"response": "proceed"}

async def main():
    # Configure session manager with fallback models
    config = Config(
        max_sessions=5,
        model="gemini-3.8-flash-high",
        fallback_models=["gemini-3.8-flash-medium", "gemini-3.8-flash-low"],
    )
    manager = SessionManager(config)
    
    # Get a session
    session = await manager.get("async_demo_session")
    
    print("Sending prompt asynchronously...")
    response = await session.send(
        "Explain asyncio in one sentence.",
        on_question=handle_async_question,
    )
    print(f"Response: {response}")
    
    # Cleanup
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
