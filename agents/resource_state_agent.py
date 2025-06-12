import json
import logging
import subprocess
import os
from typing import List, Dict, Any, Optional

from agent_server import AgentProtocol
from schemas.messages import AgentMessage, Tenant, Data
from services.llm import BedrockAnthropicLLM
import requests
from urllib3.exceptions import InsecureRequestWarning

logger = logging.getLogger(__name__)

class StateResourceAgent(AgentProtocol):
    """
    An agent that creates RDS resource.
    """
   
    def __init__(self, llm: BedrockAnthropicLLM, system_prompt: Optional[str] = None):
        """
        Initialize the CommandAgent with an LLM instance and optional custom system prompt.
        """
        self.llm = llm
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")

        self.host_url = ""
        self.tenant_id=""
        self.tenant_name=""
        self.host_token = os.getenv("PORTAL_TOKEN")

    def call_bedrock_anthropic_llm(self, messages: list):
        """
        Call the LLM with the provided messages and context.
        """
        # Create a comprehensive system prompt with tenant details
        system_prompt = f"""
You are Duplo Dash, a helpful assistant. Here are the details for the current context:
Tenant ID: {self.tenant_id}
Tenant Name: {self.tenant_name}
Platform URL: {self.host_url}

You can answer questions about:
1. Tenant information (ID, name)
2. Platform details (URL)
3. Resource states and configurations

When answering questions about tenant or platform details, use the stored information above.
"""
        return self.llm.invoke(messages=messages, model_id=self.model_id, system_prompt=system_prompt)

    def preprocess_messages(self, messages: Dict[str, List[Dict[str, Any]]]):
        """
        Preprocess messages to include tenant context.
        """
        preprocessed_messages = []
        messages_list = messages.get("messages", [])
        
        # Set host_url and tenant_id from platform context
        for message in messages_list:
            role = message.get("role", "")
            platform_ctx = message.get("platform_context", {})
            
            # Update instance variables with platform context
            if platform_ctx:
                self.host_url = platform_ctx.get("duplo_host_url", self.host_url)
                self.tenant_id = platform_ctx.get("tenant_id", self.tenant_id)
                self.tenant_name = platform_ctx.get("tenant_name", self.tenant_name)
            
            content = message.get("content", "")
            preprocessed_messages.append({
                "role": role,
                "content": content
            })
            
        # Add tenant details to the first message if it's from the user
        if preprocessed_messages and preprocessed_messages[0]["role"] == "user":
            first_msg = preprocessed_messages[0]
            first_msg["content"] = f"Tenant ID: {self.tenant_id}\nTenant Name: {self.tenant_name}\n{first_msg["content"]}"
            
        return preprocessed_messages
       

    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        """
        Process user messages and use an LLM to generate responses.
        """
        preprocessed_messages = self.preprocess_messages(messages)
        logger.info(f"Preprocessed messages: {preprocessed_messages}")

        response = self.call_bedrock_anthropic_llm(preprocessed_messages)
        logger.info(f"LLM response: {response}")

        return AgentMessage(content=response)

    

