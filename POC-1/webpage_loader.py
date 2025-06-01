import openai
import webbrowser
import json
from typing import Dict, Any
from dotenv import load_dotenv
import os

class BrowserAgent:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.conversation_history = []

    def start_browser(self, url: str) -> Dict[str, Any]:
        try:

            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            webbrowser.open(url)
            return {
                "success": True,
                "message": f"Successfully opened {url} in browser",
                "url": url
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to open browser: {str(e)}",
                "url": url
            }

    def get_function_definitions(self):
        return [
            {
                "name": "start_browser",
                "description": "Start the browser and load a given URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to load in the browser"
                        }
                    },
                    "required": ["url"]
                }
            }
        ]

    def execute_function(self, function_name: str, arguments: Dict[str, Any]):
        if function_name == "start_browser":
            return self.start_browser(arguments.get("url", ""))
        else:
            return {"error": f"Unknown function: {function_name}"}

    def chat_with_agent(self, user_message: str) -> str:
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })

        system_message = {
            "role": "system",
            "content": """You are a helpful browser agent. Your main task is to:
1. Ask the user for a URL if they haven't provided one
2. Use the right function to open the URL when provided
3. Be friendly and helpful in your interactions
4. Validate that URLs are properly formatted before opening them"""
        }

        messages = [system_message] + self.conversation_history

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                functions=self.get_function_definitions(),
                function_call="auto"
            )

            message = response.choices[0].message

            if message.function_call:
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)

                function_result = self.execute_function(function_name, function_args)

                self.conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": function_name,
                        "arguments": message.function_call.arguments
                    }
                })

                self.conversation_history.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_result)
                })

                final_response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[system_message] + self.conversation_history
                )

                assistant_message = final_response.choices[0].message.content
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })

                return assistant_message

            else:
                assistant_message = message.content
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_message
                })

                return assistant_message
        except Exception as e:
            return f"Error: {str(e)}"

def main():
    load_dotenv()
    print("Browser Agent Starting...")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("API key is required!")
        return

    agent = BrowserAgent(api_key)

    print("I can help you open URLs in your browser. Just tell me what you'd like to do!")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ['quit', 'exit', 'bye']:
                break
            if not user_input:
                continue
            response = agent.chat_with_agent(user_input)
            print(f"Agent: {response}\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()