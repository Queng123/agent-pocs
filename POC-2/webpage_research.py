import openai
import json
import urllib.parse
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import atexit
from dataclasses import dataclass
from enum import Enum

class AgentStatus(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations"

@dataclass
class AgentState:
    objective: str = ""
    plan: List[str] = None
    current_step: int = 0
    completed_steps: List[Dict] = None
    status: AgentStatus = AgentStatus.PLANNING
    iteration_count: int = 0
    max_iterations: int = 15
    success_criteria: List[str] = None
    errors: List[str] = None
    
    def __post_init__(self):
        if self.plan is None:
            self.plan = []
        if self.completed_steps is None:
            self.completed_steps = []
        if self.success_criteria is None:
            self.success_criteria = []
        if self.errors is None:
            self.errors = []

class AutonomousWebSearchAgent:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.conversation_history = []
        self.driver = None
        self.wait = None
        self.agent_state = AgentState()
        
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

    def get_page_content(self, extract_text: bool = True) -> Dict[str, Any]:
        try:
            if self.driver is None:
                return {"success": False, "message": "No browser session active"}

            page_info = {
                "title": self.driver.title,
                "url": self.driver.current_url,
            }

            if extract_text:
                try:
                    main_content = self.driver.find_element(By.TAG_NAME, "main")
                    page_info["main_content"] = main_content.text[:1000] + "..." if len(main_content.text) > 1000 else main_content.text
                except:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    page_info["body_content"] = body_text[:1000] + "..." if len(body_text) > 1000 else body_text

            return {
                "message": f"Successfully got the content of the current page",
                "success": True,
                "page_info": page_info
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get page content: {str(e)}"
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
            },
            {
                "name": "get_page_content",
                "description": "Get content from the current page",
                "parameters": {
                    "type": "object",
                    "properties": {"extract_text": {"type": "boolean", "description": "Whether to extract text from the page"}},
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
        elif function_name == "get_page_content":
            extract_text = arguments.get("extract_text", True)
            return self.get_page_content(extract_text)
        else:
            return {"error": f"Unknown function: {function_name}"}

    def create_plan(self, user_message: str) -> Dict[str, Any]:
        planning_prompt = f"""
        Analyze this user request and create a detailed action plan:
        "{user_message}"
        Remember you can only search on google and open websites.

        You must respond ONLY with a valid JSON containing:
        {{
            "objective": "Clear description of the main objective",
            "plan": ["Step 1", "Step 2", "Step 3", ...],
            "success_criteria": ["Criterion 1", "Criterion 2", ...]
        }}

        Available functions:
        - search_on_google : to perform searches
        - analyze_page_and_click_link : to click on links and navigate
        - get_page_content : to get the content of the current page (it can be useful to validate the objective)

        Create a realistic plan with concrete and measurable steps, taking into account the available functions.
        Do not do two times the same thing.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": planning_prompt}],
                temperature=0.1
            )

            plan_text = response.choices[0].message.content.strip()
            start = plan_text.find('{')
            end = plan_text.rfind('}') + 1
            if start != -1 and end > start:
                plan_text = plan_text[start:end]
            
            plan_data = json.loads(plan_text)
            
            return {
                "success": True,
                "plan_data": plan_data
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating plan: {str(e)}"
            }

    def evaluate_progress(self) -> Dict[str, Any]:
        context = {
            "objective": self.agent_state.objective,
            "plan": self.agent_state.plan,
            "current_step": self.agent_state.current_step,
            "completed_steps": self.agent_state.completed_steps,
            "success_criteria": self.agent_state.success_criteria,
            "iteration_count": self.agent_state.iteration_count,
            "errors": self.agent_state.errors
        }
        
        evaluation_prompt = f"""
        Current agent context:
        {json.dumps(context, indent=2, ensure_ascii=False)}

        Analyze the situation and determine:
        1. Is the objective achieved? (check success criteria)
        2. Should we continue with the next step?
        3. Is there an error that requires plan adaptation?

        Respond ONLY with a valid JSON:
        {{
            "objective_achieved": true/false,
            "should_continue": true/false,
            "next_action": {{
                "function_name": "function_name",
                "arguments": {{...}},
                "reasoning": "Explanation of why this action"
            }},
            "status_update": "Status update"
        }}

        Available functions:
        - search_on_google : to perform searches
        - analyze_page_and_click_link : to click on links and navigate
        - get_page_content : to get the content of the current page (it can be useful to validate the objective)

        If the objective is achieved, set "should_continue": false.
        If a critical error prevents continuation, set "should_continue": false.
        Do not do two times the same thing.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": evaluation_prompt}],
                temperature=0.1
            )

            eval_text = response.choices[0].message.content.strip()

            start = eval_text.find('{')
            end = eval_text.rfind('}') + 1
            if start != -1 and end > start:
                eval_text = eval_text[start:end]

            evaluation = json.loads(eval_text)

            return {
                "success": True,
                "evaluation": evaluation
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error evaluating: {str(e)}"
            }

    def execute_autonomous_task(self, user_message: str) -> str:
        self.agent_state = AgentState()

        print("Creating action plan...")

        plan_result = self.create_plan(user_message)
        if not plan_result["success"]:
            return f"Error creating plan: {plan_result['error']}"

        plan_data = plan_result["plan_data"]
        self.agent_state.objective = plan_data["objective"]
        self.agent_state.plan = plan_data["plan"]
        self.agent_state.success_criteria = plan_data["success_criteria"]
        self.agent_state.status = AgentStatus.EXECUTING

        print(f"Objective: {self.agent_state.objective}")
        print(f"Plan: {len(self.agent_state.plan)} steps")
        for step in self.agent_state.plan:
            print(f"{step}")
        print()

        while (self.agent_state.status == AgentStatus.EXECUTING and 
               self.agent_state.iteration_count < self.agent_state.max_iterations):

            self.agent_state.iteration_count += 1
            print(f"Iteration {self.agent_state.iteration_count}")

            eval_result = self.evaluate_progress()
            if not eval_result["success"]:
                self.agent_state.errors.append(eval_result["error"])
                continue

            evaluation = eval_result["evaluation"]

            if evaluation.get("objective_achieved", False):
                self.agent_state.status = AgentStatus.SUCCESS
                print("Objective achieved!")
                break

            if not evaluation.get("should_continue", True):
                self.agent_state.status = AgentStatus.FAILED
                print("Execution stopped")
                break

            next_action = evaluation.get("next_action")
            if next_action:
                function_name = next_action["function_name"]
                arguments = next_action["arguments"]
                reasoning = next_action.get("reasoning", "")

                result = self.execute_function(function_name, arguments)

                step_result = {
                    "iteration": self.agent_state.iteration_count,
                    "function": function_name,
                    "arguments": arguments,
                    "result": result,
                    "reasoning": reasoning
                }
                self.agent_state.completed_steps.append(step_result)

                if result.get("success", False):
                    print(f"{result.get('message', 'Action successful')}")
                else:
                    error_msg = result.get('message', 'Action failed')
                    print(f"{error_msg}")
                    self.agent_state.errors.append(error_msg)
            else:
                print("No action determined")
                break

            print()

        if self.agent_state.iteration_count >= self.agent_state.max_iterations:
            self.agent_state.status = AgentStatus.MAX_ITERATIONS

        return self.generate_final_report()

    def generate_final_report(self) -> str:
        """Generate final execution report"""
        
        status_messages = {
            AgentStatus.SUCCESS: "Mission accomplished successfully!",
            AgentStatus.FAILED: "Mission failed",
            AgentStatus.MAX_ITERATIONS: "Maximum number of iterations reached"
        }
        
        report = f"""
{status_messages.get(self.agent_state.status, "Unknown status")}

Execution Summary
===============================================
Objective: {self.agent_state.objective}
Iterations: {self.agent_state.iteration_count}
Successful actions: {len([s for s in self.agent_state.completed_steps if s['result'].get('success', False)])}
Errors: {len(self.agent_state.errors)}
"""
        return report.strip()

    def chat_with_agent(self, user_message: str) -> str:
        return self.execute_autonomous_task(user_message)

def main():
    load_dotenv()
    print("Autonomous Web Search Agent started...")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("OpenAI API key required!")
        return

    try:
        agent = AutonomousWebSearchAgent(api_key)

        print("\nExample queries:")
        print("- 'open youtube'")
        print("- 'find the medium job page'")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                if not user_input:
                    continue

                print("\n" + "="*50)
                response = agent.chat_with_agent(user_input)
                print("="*50)
                print(f"\n{response}\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}\n")
                
    except Exception as e:
        print(f"Agent initialization failed: {e}")
    finally:
        if 'agent' in locals():
            agent.cleanup()

if __name__ == "__main__":
    main()