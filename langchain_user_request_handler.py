import json
from typing import Dict
from discord.ext import commands
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from models import UserRequestState
from langgraph.graph import StateGraph
from src.db.db_handler import query_vector_db
from prompts import USER_REQUEST_PROMPT, USER_REQUEST_OUTPUT_PROMPT

llm = ChatOllama(model="llama3.1", temperature=0)

    
def agent_node(state: UserRequestState) -> Dict:
    """Agent node that processes messages and identifies tool calls"""
    try:
        results = query_vector_db(state["input"].content)
        print(results)

        # Create prompt template with messages placeholder
        prompt = ChatPromptTemplate.from_messages([
            ("system", USER_REQUEST_PROMPT.format(context="\n".join([result["text_content"] for result in results]), user_message=state["input"].content)),
            MessagesPlaceholder(variable_name="chat_history"),
        ])
    
        formatted_prompt = prompt.format(chat_history=state["messages"])

        print("formatted_prompt: ", formatted_prompt)

        # Invoke with chat history
        while True:
            try:
                response = llm.invoke(formatted_prompt + USER_REQUEST_OUTPUT_PROMPT)
                json.loads(response.content)
                break
            except Exception as e:
                print(f"Error invoking agent_node LLM: {e}")
                continue
            
        print("response: ", response)
        return {"messages": [AIMessage(content=json.loads(response.content)['response'])]}
    except Exception as e:
        print(f"Error in agent_node: {e}")
        return state


# Build the LangGraph workflow
def build_workflow():
    """Build the LangGraph workflow"""
    workflow = StateGraph(UserRequestState)

    # Add nodes
    workflow.add_node("agent", agent_node)

    workflow.set_entry_point("agent")
    
    return workflow.compile()

class UserRequestAgent:
    def __init__(self, bot: commands.Bot):
        self.graph = build_workflow()
        self.conversation_history = {}  # Keyed by user_discord_id
        self.user_discord_id = ''
        self.user_name = ''
        self.discord_bot = bot
        
    async def process_message(self, message_content: str, channel_id: str, channel_name: str, user_discord_id: str, user_name: str) -> str:
        """Process a message and return a response"""
        # Initialize state with just the current message, no history

        self.user_discord_id = user_discord_id
        self.user_name = user_name

        if self.user_discord_id not in self.conversation_history:
            self.conversation_history[self.user_discord_id] = []

        # Add the new message to history
        self.conversation_history[self.user_discord_id].append(HumanMessage(content=message_content))

        state = {
            "input": HumanMessage(content=message_content),
            "messages": self.conversation_history[self.user_discord_id].copy(),  # Only include current message
            "discord_bot": self.discord_bot,
            "channel_id": channel_id,
            "channel_name": channel_name
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
                self.conversation_history[self.user_discord_id].append(AIMessage(content=message.content))
                return message.content

        return "I processed your request, but couldn't generate a proper response."
    