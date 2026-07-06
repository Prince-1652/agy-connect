"""Example 6: Async Usage"""

import asyncio
from agy_connect import SessionManager, Config

async def main():
    config = Config(max_sessions=5)
    manager = SessionManager(config)
    
    # Get a session
    session = await manager.get("async_demo_session")
    
    print("Sending prompt asynchronously...")
    response = await session.send("Explain asyncio in one sentence.")
    print(f"Response: {response}")
    
    # Cleanup
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
