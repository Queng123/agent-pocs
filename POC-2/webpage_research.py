import openai
import webbrowser
import json
import urllib.parse
import pyautogui
import time
import base64
from io import BytesIO
from PIL import Image
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os

class WebSearchAgent:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.conversation_history = []

    def search_on_google(self, query: str) -> Dict[str, Any]:
        """Performs a search on Google with the given query"""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            webbrowser.open(search_url)
            return {
                "success": True,
                "message": f"Successfully searched Google for: '{query}'",
                "query": query,
                "url": search_url,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to search Google for '{query}': {str(e)}",
            }
    def get_function_definitions(self):
        return [
            {
                "name": "search_on_google",
                "description": "Perform a search on Google",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query to perform"}
                    },
                    "required": ["query"]
                }
            }
        ]

    def execute_function(self, function_name: str, arguments: Dict[str, Any]):
        if function_name == "search_on_google":
            query = arguments.get("query", "")
            return self.search_on_google(query)
        else:
            return {"error": f"Unknown function: {function_name}"}

    def chat_with_agent(self, user_message: str) -> str:
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })

        system_message = {
            "role": "system",
            "content": """You are a helpful web search agent. Your current capabilities include:

1. Performing searches on Google with any query
2. Understanding multi-step search processes

Your main tasks:
- When a user wants to search for something, directly perform the search
- Be proactive in suggesting next steps needed for a complete search
- Explain what you're doing and what comes next
- Be friendly and helpful in your interactions

Current capabilities:
- Performing Google searches

Remember: You can now perform actual searches! Use the search function when users ask for a website, so you can not miss the URL.
"""
        }

        messages = [system_message] + self.conversation_history
        max_iterations = 5
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=messages,
                    functions=self.get_function_definitions(),
                    function_call="auto"
                )

                message = response.choices[0].message

                if message.function_call:
                    function_name = message.function_call.name
                    function_args = json.loads(message.function_call.arguments)

                    function_result = self.execute_function(function_name, function_args)

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "function_call": {
                            "name": function_name,
                            "arguments": message.function_call.arguments
                        }
                    })

                    messages.append({
                        "role": "function",
                        "name": function_name,
                        "content": json.dumps(function_result)
                    })

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

                    continue

                else:
                    assistant_message = message.content
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": assistant_message
                    })

                    return assistant_message

            except Exception as e:
                return f"Error during autonomous execution: {str(e)}"

        return "Completed autonomous workflow (reached maximum iterations)"

def main():
    load_dotenv()
    print("🔍 Advanced Web Search Agent Starting...")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("OpenAI API key is required!")
        return

    try:
        agent = WebSearchAgent(api_key)
        
        print("I can now perform complete autonomous web searches!")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                if not user_input:
                    continue
                    
                print("Processing your request...")
                response = agent.chat_with_agent(user_input)
                print(f"Agent: {response}\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}\n")
                
    except Exception as e:
        print(f"Failed to initialize agent: {e}")

if __name__ == "__main__":
    main()