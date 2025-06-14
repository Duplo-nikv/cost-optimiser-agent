from typing import Dict, Any, List
from agent_server import AgentProtocol
from schemas.messages import AgentMessage


class EchoAgent(AgentProtocol):
    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        # Extract messages list from the messages dictionary
        messages_list = messages.get("messages", [])
        
        # Find the last user message
        last_user = next((m for m in reversed(messages_list) if m.get("role") == "user"), None)
        text = last_user.get("content", "") if last_user else "I heard nothing."
        
        return AgentMessage(content=f"Echo: {text}")