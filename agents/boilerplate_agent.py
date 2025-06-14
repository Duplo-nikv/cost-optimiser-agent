from typing import Dict, Any, List
from agent_server import AgentProtocol
from schemas.messages import AgentMessage


class BoilerplateAgent(AgentProtocol):
    """
    A minimal boilerplate agent implementation that returns 'Not Implemented' for all requests.
    This serves as a starting point for creating new agents.
    """

    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        """
        Basic implementation that returns a 'Not Implemented' message.
        
        Args:
            messages: A dictionary containing the message history in the format {"messages": [...]} 
            
        Returns:
            An AgentMessage with a 'Not Implemented' response
        """
        return AgentMessage(content="Not Implemented. Override this method with your agent's logic.")
