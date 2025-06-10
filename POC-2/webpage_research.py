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

    def open_google_search(self) -> Dict[str, Any]:
        """Opens Google homepage in the browser"""      
        try:
            url = "https://www.google.com"
            webbrowser.open(url)
            time.sleep(3)
            return {
                "success": True,
                "message": f"Successfully opened Google homepage at {url}",
                "url": url,
                "action": "opened_google_search"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to open Google search: {str(e)}",
                "url": url,
                "action": "failed_to_open_google_search"
            }

    def search_on_google(self, query: str) -> Dict[str, Any]:
        """Performs a search on Google with the given query"""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"
            
            webbrowser.open(search_url)
            time.sleep(4)
            return {
                "success": True,
                "message": f"Successfully searched Google for: '{query}'",
                "query": query,
                "url": search_url,
                "action": "performed_google_search"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to search Google for '{query}': {str(e)}",
                "query": query,
                "action": "failed_google_search"
            }

    def take_screenshot(self) -> Optional[str]:
        """Takes a screenshot and returns it as base64 encoded string"""
        try:
            screenshot = pyautogui.screenshot()
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return img_str
        except Exception as e:
            print(f"Failed to take screenshot: {e}")
            return None

    def analyze_page_and_click_link(self, user_instruction: str) -> Dict[str, Any]:
        """Takes a screenshot, analyzes it with GPT-4 Vision, and clicks on the most relevant link"""
        try:
            screenshot_b64 = self.take_screenshot()
            if not screenshot_b64:
                return {
                    "success": False,
                    "message": "Failed to take screenshot",
                    "action": "failed_screenshot"
                }

            analysis_response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""Analyze this screenshot of a Google search results page. 

User instruction: "{user_instruction}"

Please:
1. Identify all clickable links/results visible on the page
2. Choose the BEST link that matches the user's instruction
3. Provide the approximate coordinates (x, y) where I should click
4. Explain why you chose this particular link

Return your response in this JSON format:
{{
    "best_link": {{
        "title": "title of the chosen link",
        "description": "brief description of what this link is about",
        "coordinates": [x, y],
        "confidence": "high/medium/low",
        "reasoning": "why you chose this link"
    }},
    "other_options": [
        {{"title": "other option 1", "coordinates": [x, y]}},
        {{"title": "other option 2", "coordinates": [x, y]}}
    ]
}}

Be precise with coordinates - they should be clickable positions on links, not just text positions."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{screenshot_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )

            analysis_text = analysis_response.choices[0].message.content
            

            try:
                start_idx = analysis_text.find('{')
                end_idx = analysis_text.rfind('}') + 1
                json_str = analysis_text[start_idx:end_idx]
                analysis_data = json.loads(json_str)
            except:
                return {
                    "success": False,
                    "message": f"Failed to parse analysis response: {analysis_text}",
                    "action": "failed_analysis_parsing"
                }

            best_link = analysis_data.get("best_link", {})
            coordinates = best_link.get("coordinates", [])
            
            if not coordinates or len(coordinates) != 2:
                return {
                    "success": False,
                    "message": "No valid coordinates found in analysis",
                    "action": "failed_coordinate_extraction",
                    "analysis": analysis_data
                }

            # Click on the identified coordinates
            x, y = coordinates
            pyautogui.click(x, y)
            time.sleep(3)
            
            return {
                "success": True,
                "message": f"Successfully clicked on '{best_link.get('title', 'Unknown')}' at coordinates ({x}, {y})",
                "action": "clicked_link",
                "link_info": best_link,
                "analysis": analysis_data
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to analyze and click link: {str(e)}",
                "action": "failed_link_click"
            }

    def get_function_definitions(self):
        return [
            {
                "name": "open_google_search",
                "description": "Opens Google homepage in the browser to prepare for searching",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "search_on_google", 
                "description": "Performs a search on Google with a specific query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look for on Google"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_page_and_click_link",
                "description": "Takes a screenshot of the current page, analyzes it with computer vision, and clicks on the most relevant link based on user instructions",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_instruction": {
                            "type": "string",
                            "description": "User's instruction about what kind of link to click (e.g., 'click on the official documentation', 'find a tutorial for beginners', 'open the Wikipedia page')"
                        }
                    },
                    "required": ["user_instruction"]
                }
            }
        ]

    def execute_function(self, function_name: str, arguments: Dict[str, Any]):
        if function_name == "open_google_search":
            return self.open_google_search()
        elif function_name == "search_on_google":
            query = arguments.get("query", "")
            return self.search_on_google(query)
        elif function_name == "analyze_page_and_click_link":
            user_instruction = arguments.get("user_instruction", "")
            return self.analyze_page_and_click_link(user_instruction)
        else:
            return {"error": f"Unknown function: {function_name}"}

    def chat_with_agent(self, user_message: str) -> str:
        self.conversation_history.append({
            "role": "user", 
            "content": user_message
        })

        system_message = {
            "role": "system",
            "content": """You are an intelligent web search agent with computer vision capabilities. Your current capabilities include:

1. Opening Google homepage in the browser
2. Performing searches on Google with any query
3. Taking screenshots and analyzing web pages using computer vision
4. Intelligently clicking on the most relevant links based on user instructions

IMPORTANT: You can chain multiple function calls together in a single response to complete complex tasks autonomously. When a user gives you a request that requires multiple steps, execute them all automatically without asking for permission.

Your main tasks:
- Understand complex user requests that may require multiple steps
- Break down tasks into logical steps and execute them ALL in sequence
- Use computer vision to "see" the page and make intelligent decisions about which links to click
- Complete entire workflows autonomously in a single interaction

Autonomous Workflow Strategy:
1. When user wants to find specific information: 
   - Execute: search_on_google → analyze_page_and_click_link
   - Don't ask, just do it!

2. When user gives search + action requests:
   - Execute all necessary steps immediately
   - Explain what you're doing as you do it

3. For complex multi-step requests:
   - Plan the sequence of actions needed
   - Execute all functions in the correct order
   - Only stop if there's an error or you need clarification

Current capabilities:
✅ Opening Google homepage
✅ Performing Google searches  
✅ Computer vision analysis of web pages
✅ Intelligent link clicking based on user intent
✅ AUTONOMOUS MULTI-STEP EXECUTION

You should now complete full search workflows in ONE interaction! Think step-by-step:
- What does the user want to accomplish?
- What's the complete sequence of actions needed?
- Execute ALL the steps automatically

Be conversational and explain what you're doing at each step, but DO the work without asking for permission.
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
    print("Current capabilities:")
    print("✅ Opening Google homepage")
    print("✅ Performing Google searches")
    print("✅ Computer vision page analysis")
    print("✅ Intelligent link clicking")
    print("\nRequired packages: openai, pyautogui, pillow, python-dotenv")
    print("Note: Make sure your browser is visible for screenshot analysis!\n")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("❌ OpenAI API key is required!")
        return

    try:
        agent = WebSearchAgent(api_key)
        
        print("🤖 I can now perform complete autonomous web searches!")
        print("Just tell me what you want to find, and I'll:")
        print("  1. Search Google automatically")
        print("  2. Analyze the results with computer vision") 
        print("  3. Click on the best link for you")
        print("  4. All in one go - no need to ask for each step!")
        print("\nExamples:")
        print("- 'Find and open Python documentation'")
        print("- 'Search for machine learning tutorials and open a beginner guide'")
        print("- 'Look up the latest news about AI and open a recent article'")
        print("Type 'quit' to exit.\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                if not user_input:
                    continue
                    
                print("🔄 Processing your request...")
                response = agent.chat_with_agent(user_input)
                print(f"🤖 Agent: {response}\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}\n")
                
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print("Make sure you have all required packages installed:")
        print("pip install openai pyautogui pillow python-dotenv")

if __name__ == "__main__":
    main()