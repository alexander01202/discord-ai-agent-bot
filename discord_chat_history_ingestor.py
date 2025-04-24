from typing import Dict, List, Tuple, Any
import json
import asyncio
from discord.ext import commands

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama

# LangGraph imports
from langgraph.graph import END, StateGraph

# Output Structure
from models import AgentState, ToolCall
from prompts import OUTPUT_PROMPT, SYSTEM_PROMPT_FOR_CHAT_HISTORY
from src.langchain_tools.tools import fetch_employees_tool, create_task_tool, update_task_tool, log_employees_to_db_from_channel_tool, update_employee_tool, log_employee_tool, log_employee_schedule_tool, get_task_tool

# Define the chat model
llm = ChatOllama(model="llama3.1", temperature=0)


# Create a custom tool executor
class SimpleToolExecutor:
    """Simple tool executor that can run tools by name"""

    def __init__(self, tools: List[BaseTool]):
        self.tools = {tool.name: tool for tool in tools}

    def invoke(self, tool_call: ToolCall) -> Any:
        """Execute a tool by name with given inputs"""
        tool_name = tool_call.tool
        tool_input = tool_call.tool_input

        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")

        tool = self.tools[tool_name]
        return tool.invoke(tool_input)


# Helper functions for RunnableSequence to process messages and handle tool parsing
def parse_tool_calls(llm_response) -> List[ToolCall]:
    """Parse LLM response for tool calls"""

    try:
        json_response = json.loads(llm_response.content)
        if not json_response.get("tools_needed"):
            return []

        tools_needed = json_response.get("tools_needed", [])
        tools_with_params = json_response.get("tools_with_params", [])

        tool_calls = []
        for tool_name in tools_needed:
            formatted_tool_name = tool_name.lower().replace(" ", "_")
            tool_input = tools_with_params.get(formatted_tool_name, {})
            if not tool_input:
                tool_input = tools_with_params.get(tool_name, {})
            
            tool_calls.append(ToolCall(
                tool=formatted_tool_name,
                tool_input=tool_input
            ))

        return tool_calls
    except Exception as e:
        print(f"Error parsing tool calls: {e}")
        return []


def update_state_with_response(state: AgentState, llm_response) -> AgentState:
    """Update state with LLM response and parsed tool calls"""
    new_state = state.copy()
    try:
        # Parse the JSON response
        response_data = json.loads(llm_response.content)
        # If no tools needed, return empty response
        if not response_data.get("tools_needed"):
            new_state["messages"] = new_state["messages"] + [AIMessage(content="")]
            new_state["current_tool_calls"] = []
            return new_state
            
        # Process tool calls if tools needed
        tool_calls = parse_tool_calls(llm_response)
        new_state["messages"] = new_state["messages"] + [llm_response]

        if tool_calls:
            new_state["current_tool_calls"] = [tc.model_dump() for tc in tool_calls]
        else:
            new_state["current_tool_calls"] = []

    except Exception as e:
        print(f"Error updating state with response: {e}")
    finally:
        return new_state
    

# LangGraph nodes
def agent_node(state: AgentState) -> Dict:
    """Agent node that processes messages and identifies tool calls"""
    try:
        # Create prompt template with messages placeholder
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT_FOR_CHAT_HISTORY),
            MessagesPlaceholder(variable_name="chat_history")
        ])
        formatted_prompt = prompt.format(chat_history=state["messages"])
        # Invoke with chat history
        while True:
            try:
                response = llm.invoke(formatted_prompt + OUTPUT_PROMPT)
                json.loads(response.content)
                break
            except Exception as e:
                print(f"Error invoking agent_node LLM: {e}")
                continue
            
        print("response: ", response)
        # Update state with response
        return update_state_with_response(state, response)
    except Exception as e:
        print(f"Error in agent_node: {e}")
        return state


def format_tool_results(state: AgentState, tool_results: List[Tuple[ToolCall, Any]]) -> AgentState:
    """Format tool results as messages and update state"""
    result_messages = []
    for tool_call, result in tool_results:
        result_message = json.dumps(result, indent=2)
        result_messages.append(AIMessage(content=result_message))

    new_state = state.copy()
    new_state["messages"] = new_state["messages"] + result_messages
    new_state["current_tool_calls"] = []
    return new_state


def execute_tools_node(state: AgentState) -> Dict:
    """Execute tools node that runs tools and formats results"""
    tool_executor = SimpleToolExecutor(tools=[fetch_employees_tool, create_task_tool, update_task_tool, log_employees_to_db_from_channel_tool, update_employee_tool, log_employee_tool, log_employee_schedule_tool, get_task_tool])
    results = []

    task_was_created = False

    print(f'Current tool calls: {state["current_tool_calls"]}')

    for tool_call_dict in state["current_tool_calls"]:
        tool_call = ToolCall(**tool_call_dict)

        if tool_call.tool == "create_task_tool":
            task_was_created = True

        # Channel ID injection for create_task
        if not tool_call.tool_input.get("channel_id"):
            tool_call.tool_input["channel_id"] = state.get("channel_id")
        if not tool_call.tool_input.get("channel_name"):
            tool_call.tool_input["channel_name"] = state.get("channel_name")
        if tool_call.tool == "log_employees_to_db_from_channel_tool":
            tool_call.tool_input["discord_bot"] = state.get("discord_bot")

        result = tool_executor.invoke(tool_call)
        results.append((tool_call, result))
    
    new_state = format_tool_results(state, results)

    # Now ask the LLM to summarize it conversationally
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT_FOR_CHAT_HISTORY),
        MessagesPlaceholder(variable_name="chat_history")
    ])
    formatted_prompt = prompt.format(chat_history=new_state["messages"])
    
    # Safe retry loop if response is bad JSON
    while True:
        try:
            response = llm.invoke(formatted_prompt + "Respond using this format: **Task name:** <task name>\n\n**Task description:** <task description>\n\n**Task assignee:** <task assignee / discord username>.")
            break
        except Exception as e:
            print("❌ Error in final response generation:", e)
            continue
    # if task_was_created:
    #     task_channel_id = 1361986399259332738
    #     state['discord_bot'].get_channel(task_channel_id).send(response.content)
    new_state["messages"].append(response.content)
    return new_state


def should_continue(state: AgentState) -> str:
    """Decide whether to execute tools or finish the conversation"""
    if "current_tool_calls" in state and state["current_tool_calls"]:
        return "execute_tools"
    return "end"


# Build the LangGraph workflow
def build_workflow():
    """Build the LangGraph workflow"""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("execute_tools", execute_tools_node)

    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "execute_tools": "execute_tools",
            "end": END
        }
    )
    
    return workflow.compile()


class DiscordChatHistoryIngestor:
    def __init__(self, bot: commands.Bot):
        self.graph = build_workflow()
        self.discord_bot = bot

    async def process_message(self, message_content: str, channel_id: str, channel_name: str) -> str:
        """Process a message and return a response"""
        # Initialize state with just the current message, no histor

        MESSAGE_CONTENT = f"Here is the message history: \n\n START OF MESSAGE HISTORY \n\n {message_content.replace(":", '-')} \n\n END OF MESSAGE HISTORY"
        state = {
            "input": HumanMessage(content=MESSAGE_CONTENT),
            "messages": [HumanMessage(content=MESSAGE_CONTENT)],
            "channel_id": channel_id,
            "channel_name": channel_name,
            "current_tool_calls": [],
            "discord_bot": self.discord_bot
        }

        # Run the graph
        final_state = None
        for output in self.graph.stream(state):
            # Get the latest state no matter the node
            for node_name, node_state in output.items():
                final_state = node_state

        # Get the last AI message as the response
        for message in reversed(final_state["messages"]):
            if isinstance(message, AIMessage):
                return message.content

        return "I processed your request, but couldn't generate a proper response."