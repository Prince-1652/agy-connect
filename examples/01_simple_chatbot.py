"""Example 1: Simple Chatbot"""

from agy_connect import Chat

def main():
    chat = Chat()
    print("Sending prompt to Antigravity CLI...")
    response = chat.send("Hello, Antigravity!")
    print(f"Response: {response}")
    chat.close()

if __name__ == "__main__":
    main()
