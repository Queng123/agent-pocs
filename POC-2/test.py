import openai
import json
import urllib.parse
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import atexit

class WebSearchAgent:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.conversation_history = []
        self.driver = None
        self.wait = None

        atexit.register(self.cleanup)

    def _initialize_driver(self):
        if self.driver is None:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)

    def search_on_google(self, query: str) -> Dict[str, Any]:
        try:
            self._initialize_driver()

            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.google.com/search?q={encoded_query}"

            self.driver.get(search_url)

            self.wait.until(EC.presence_of_element_located((By.ID, "search")))

            try:
                results = self.driver.find_elements(By.CSS_SELECTOR, "h3 a, .yuRUbf a")
                result_count = len(results)
            except:
                result_count = "unknown"

            return {
                "success": True,
                "message": f"Successfully searched Google for: '{query}'. Found {result_count} results.",
                "query": query,
                "url": search_url,
                "result_count": result_count
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to search Google for '{query}': {str(e)}",
            }

    def analyze_page_and_click_link(self, 
                                   link_text: Optional[str] = None, 
                                   link_index: int = 0, 
                                   css_selector: Optional[str] = None) -> Dict[str, Any]:
        try:
            if self.driver is None:
                return {
                    "success": False,
                    "message": "No browser session found. Please search on Google first.",
                }
            current_url = self.driver.current_url
            page_title = self.driver.title

            link_element = None
            click_method = ""

            if css_selector:
                link_element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))
                click_method = f"CSS selector: {css_selector}"
            elif link_text:

                link_element = self.wait.until(EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, link_text)))
                click_method = f"link text: {link_text}"
            else:
                search_results = self.driver.find_elements(By.CSS_SELECTOR, "h3 a, .yuRUbf a")
                if search_results and len(search_results) > link_index:
                    link_element = search_results[link_index]
                    click_method = f"search result #{link_index + 1}"
                else:
                    return {
                        "success": False,
                        "message": f"No search result found at index {link_index}. Total results: {len(search_results)}",
                        "page_analysis": {
                            "title": page_title,
                            "url": current_url,
                            "total_results": len(search_results)
                        }
                    }
            
            if link_element:
                link_url = link_element.get_attribute("href")
                link_title = link_element.get_attribute("title") or link_element.text
                
                self.driver.execute_script("arguments[0].click();", link_element)
                
                WebDriverWait(self.driver, 15).until(
                    lambda driver: driver.current_url != current_url
                )
                
                new_url = self.driver.current_url
                new_title = self.driver.title
                
                return {
                    "success": True,
                    "message": f"Successfully clicked on link using {click_method} and navigated to new page",
                    "page_analysis": {
                        "previous_page": {
                            "title": page_title,
                            "url": current_url
                        },
                        "clicked_link": {
                            "title": link_title[:100] + "..." if len(link_title) > 100 else link_title,
                            "url": link_url
                        },
                        "current_page": {
                            "title": new_title,
                            "url": new_url
                        }
                    }
                }
            
        except TimeoutException:
            return {
                "success": False,
                "message": "Timeout waiting for link to be clickable or page to load",
                "page_analysis": {
                    "title": self.driver.title if self.driver else "Unknown",
                    "url": self.driver.current_url if self.driver else "Unknown"
                }
            }
        except NoSuchElementException as e:
            return {
                "success": False,
                "message": f"Could not find the specified link: {str(e)}",
                "page_analysis": {
                    "title": self.driver.title if self.driver else "Unknown",
                    "url": self.driver.current_url if self.driver else "Unknown"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to analyze page and click link: {str(e)}",
            }

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self.wait = None

    def get_function_definitions(self):
        return [
            {
                "name": "search_on_google",
                "description": "Perform a search on Google using a persistent browser session",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query to perform"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "analyze_page_and_click_link",
                "description": "Analyzes the current page and clicks on a specific link. Can click by link text, index, or CSS selector",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "link_text": {
                            "type": "string",
                            "description": "Partial text of the link to click (optional)"
                        },
                        "link_index": {
                            "type": "integer",
                            "description": "Index of the search result to click (0 = first result, default: 0)"
                        },
                        "css_selector": {
                            "type": "string",
                            "description": "CSS selector for the link to click (optional)"
                        }
                    },
                    "required": []
                }
            }
        ]

    def execute_function(self, function_name: str, arguments: Dict[str, Any]):
        if function_name == "search_on_google":
            query = arguments.get("query", "")
            return self.search_on_google(query)
        elif function_name == "analyze_page_and_click_link":
            link_text = arguments.get("link_text")
            link_index = arguments.get("link_index", 0)
            css_selector = arguments.get("css_selector")
            return self.analyze_page_and_click_link(link_text, link_index, css_selector)
        else:
            return {"error": f"Unknown function: {function_name}"}

    def chat_with_agent(self, user_message: str) -> str:
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        system_message = {
            "role": "system",
            "content": """You are a helpful web search agent with advanced browser automation capabilities. Your current capabilities include:

1. Performing searches on Google with persistent browser sessions
2. Analyzing pages and clicking on specific links (by text, index, or CSS selector)

Key features:
- You maintain a persistent browser session across operations
- You can click on search results and navigate between pages
- You can be specific about which links to click

Your main tasks:
- When a user wants to search for something, perform the search and offer to click on relevant results
- Be proactive in suggesting next steps for a complete search workflow
- Explain what you're doing and what you found
- Extract relevant information from pages when requested
- Be friendly and helpful in your interactions

Available functions:
- search_on_google: Search Google with any query
- analyze_page_and_click_link: Click on links from search results or current page

Always provide useful feedback about what you found and suggest logical next steps.
"""
        }

        messages = [system_message] + self.conversation_history
        max_iterations = 8
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
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
    print("Enhanced Web Search Agent with Browser Automation Starting...")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("OpenAI API key is required!")
        return

    try:
        agent = WebSearchAgent(api_key)

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
                
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
    finally:
        if 'agent' in locals():
            agent.cleanup()

if __name__ == "__main__":
    main()