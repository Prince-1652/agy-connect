"""Example 7: Brutal Feature Test Chatbot"""

import os
import sys
import json
from agy_connect import Chat, Config
from agy_connect.exceptions import AgyConnectException

def test_streaming(chat: Chat):
    print("\n--- Testing Streaming ---")
    print("User: Write a 1-sentence joke about programmers.")
    print("Agy: ", end="")
    try:
        for chunk in chat.stream("Write a 1-sentence joke about programmers."):
            sys.stdout.write(chunk)
            sys.stdout.flush()
        print()
    except AgyConnectException as e:
        print(f"\n[Error during streaming]: {e}")

def test_health_and_status(chat: Chat):
    print("\n--- Testing Health & Status ---")
    status = chat.status()
    print(f"Status: {status}")
    health = chat.health()
    print("Health Metrics:")
    for k, v in health.items():
        print(f"  {k}: {v}")

def test_history(chat: Chat, test_file="temp_history.json"):
    print("\n--- Testing History Management ---")
    
    # 1. Print current history
    print(f"Current history length: {len(chat.history())}")
    
    # 2. Save history
    print(f"Saving history to {test_file}...")
    chat.save(test_file)
    assert os.path.exists(test_file), "History file was not created!"
    
    # 3. Reset history
    print("Resetting history...")
    chat.reset()
    assert len(chat.history()) == 0, "History was not reset!"
    
    # 4. Load history
    print(f"Loading history from {test_file}...")
    chat.load(test_file)
    assert len(chat.history()) > 0, "History was not loaded!"
    print(f"History loaded successfully! (length: {len(chat.history())})")
    
    # Cleanup
    os.remove(test_file)

def test_restart(chat: Chat):
    print("\n--- Testing Restart ---")
    print("Restarting adapter...")
    chat.restart()
    print(f"Status after restart: {chat.status()}")

def test_sync_send(chat: Chat):
    print("\n--- Testing Sync Send ---")
    print("User: Do you remember the joke you just told me? Answer yes or no.")
    try:
        response = chat.send("Do you remember the joke you just told me? Answer yes or no.")
        print(f"Agy: {response.strip()}")
    except AgyConnectException as e:
        print(f"[Error during send]: {e}")

def main():
    print("Initializing Chat with custom configuration (DEBUG Mode)...")
    config = Config(
        debug_mode=True,
        idle_timeout=30,
        max_sessions=3
    )
    
    chat = Chat(config)
    
    try:
        test_streaming(chat)
        test_health_and_status(chat)
        test_history(chat)
        test_restart(chat)
        test_sync_send(chat)
        
        print("\nAll brutal tests completed successfully! Closing chat...")
    finally:
        chat.close()

if __name__ == "__main__":
    main()
