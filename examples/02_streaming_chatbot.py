"""Example 2: Streaming Chatbot"""

import sys
from agy_connect import Chat

def main():
    chat = Chat()
    print("Sending prompt...")
    for chunk in chat.stream("Write a short python script."):
        sys.stdout.write(chunk)
        sys.stdout.flush()
    print()
    chat.close()

if __name__ == "__main__":
    main()
