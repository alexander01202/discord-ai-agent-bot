from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TypedDict, Union
import datetime
from discord.ext import commands

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

class Message(BaseModel):
    response: str
    tools_needed: List[str] = Field(default_factory=list)
    tools_with_params: List[Dict[str, Any]] = Field(default_factory=list)

# Models for structured data
class TaskInput(BaseModel):
    channel_id: str = Field(..., description="Discord channel ID")
    channel_name: str = Field(..., description="Discord channel name")
    task_name: str = Field(..., description="The name of the task")
    description: Optional[str] = Field('', description="Description of what needs to be done")
    assignee_id: Optional[str] = Field('', description="ID of the employee who will do the task")
    priority: Optional[str] = Field('', description="Priority level: LOW, MEDIUM, HIGH, or URGENT")
    reminder_frequency: Optional[str] = Field('', description="How often to remind: HOURLY, DAILY, WEEKLY, MONTHLY, or ONCE")
    due_date: Optional[str] = Field('', description="Due date in YYYY-MM-DD HH:MM format")
    specific_weekday: Optional[int] = Field('', description="0=Monday through 6=Sunday")
    date_created: Optional[str] = datetime.datetime.now().isoformat()


# State definitions for the graph
class AgentState(TypedDict):
    input: HumanMessage
    messages: List[Union[HumanMessage, AIMessage, SystemMessage]]
    current_tool_calls: List[Dict[str, Any]]  # Tool name and inputs
    channel_id: str
    channel_name: str
    discord_bot: commands.Bot
    prompt: str

class UserRequestState(TypedDict):
    input: HumanMessage
    messages: List[Union[HumanMessage, AIMessage, SystemMessage]]
    discord_bot: commands.Bot
    channel_id: str
    channel_name: str

class DiscordChatHistoryIngestorState(TypedDict):
    input: HumanMessage
    messages: List[Union[HumanMessage, AIMessage, SystemMessage]]
    discord_bot: commands.Bot
    channel_id: str
    current_tool_calls: List[Dict[str, Any]]  # Tool name and inputs
    channel_name: str

# Create a custom tool invocation structure as replacement for ToolInvocation
class ToolCall(BaseModel):
    tool: str
    tool_input: Dict[str, Any]