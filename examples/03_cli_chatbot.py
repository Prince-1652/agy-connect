"""Example 3: CLI Chatbot"""

import sys
from agy_connect import Chat

def main():
    chat = Chat()
    print("Welcome to agy-connect CLI! Type 'exit' to quit.")
    
    while True:
        try:
            user_input = input("You> ")
            if user_input.lower() in ["exit", "quit"]:
                break
                
            print("Agy> ", end="")
            for chunk in chat.stream(user_input):
                sys.stdout.write(chunk)
                sys.stdout.flush()
            print()
            
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
    chat.close()

if __name__ == "__main__":
    main()
