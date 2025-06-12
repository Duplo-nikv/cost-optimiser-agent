import json
import logging
from queue import Empty
import subprocess
import os
from typing import List, Dict, Any, Optional

from agent_server import AgentProtocol
from schemas.messages import AgentMessage, Tenant, Data
from services.llm import BedrockAnthropicLLM
import requests
from urllib3.exceptions import InsecureRequestWarning

logger = logging.getLogger(__name__)

class Resource(AgentProtocol):
    """
    Base class for managing resources.
    """
    def __init__(self, host_url: str, tenant_name: str, tenant_id: str):
        """
        Initialize the resource manager.
        """
        self.tenant_name=tenant_name
        self.host_token = "AQAAANCMnd8BFdERjHoAwE_Cl-sBAAAAzSo9l_hs9UC987FR9ftCdQAAAAACAAAAAAAQZgAAAAEAACAAAABuElDGCEMFaFBhDQ1uMkPg1AEQApOutVACe_TMs32osQAAAAAOgAAAAAIAACAAAAADPn06ydfDw-_zpiFasTQOlKHPdeVTqUO3yynx79TJA8AAAABeRfFQ6gAyDcKSIzH0l0u55prh6nnnP3KA1RrGqvzllKuV2uz9jnMFGJY3wVkR4zRBmLdBsIXe-zzNuJ8pDV3hXmHS7D-9JYByWgYsaRLgnq8m2bf6ibkq_x6gJlasafcGso9jh0luA0uRQ8gwCbW8cZfD3rBD99Uvg6Qt5av7vbd2mfNvnqX84AFA8Z4HZF394OGhVRTfZqoCge4Vl2qOWUvUoJRH72uT8-6as1bg2S11Iqyo1tDwTHDLwxCEBIdAAAAAIEbwQZsqAugGN1UM6gVkyA8xV_0F_5wGrRnfToJM_snjmmxppBlzhf15nrWn2TOEdDePN359Te2EkwDZNuHyQA"
        self.host_url = host_url
        self.tenant_id = tenant_id
        self.active_states = {
            "rds": ["available","stopped"],  # RDS instances
           # "opensearch": ["true"],  # OpenSearch domains
           # "ecache": ["available"],  # ElastiCache clusters
           # "asg": ["Active", "InService"]  # Auto Scaling Groups
        }
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    def _get_resource(self, resource_type: str) -> List[Dict[str, Any]]:
        """
        Helper method to fetch resources of a given type for a tenant.
        """
        if resource_type not in self.active_states:
            raise ValueError(f"Unsupported resource type: {resource_type}")

        endpoints = {
            "rds": f"v3/subscriptions/{self.tenant_id}/aws/rds/instance",
           # "opensearch": "GetOpensearchDomains",
           # "ecache": "GetElastiCacheInstances",
           # "asg": "GetAutoScalingGroups"
        }
        
        url = f"{self.host_url}/{endpoints[resource_type]}"
        headers = {
            "Authorization": f"Bearer {self.host_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching {resource_type} for tenant {self.tenant_id}: {e}")
            return []

    def get_rds_state(self) -> List[Dict[str, str]]:
        """
        Returns a list of dicts with RDS instance name and state.
        """
        rds_list = self._get_resource("rds")
        return [{
            "name": rds.get("Identifier"),
            "state": rds.get("InstanceStatus"),
            "engine": rds.get("Engine"),
            "size": rds.get("AllocatedStorage")
        } for rds in rds_list]

    def get_resource_state(self, resource_type: str,inactive_state: bool) -> List[Dict[str, Any]]:
        """
        Get state of resources for a specific resource type.
        """
        if resource_type not in self.active_states:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        
        # Get all resources of this type
        all_resources = getattr(self, f"get_{resource_type}_state")()
        
        # Filter for active/running resources
        active_resources = []
        for resource in all_resources:
            state = resource.get("state", "").lower()
            if inactive_state:
                if state in [s.lower() for s in self.active_states.get(resource_type, [])[1:]]:
                    active_resources.append(resource)
            else:
                if state in [s.lower() for s in self.active_states.get(resource_type, [])]:
                    active_resources.append(resource)
        
        return active_resources

    def get_running_resources(self, inactive_state: bool) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all running resources across all supported types.
        """
        running_states = {}
        for resource_type in self.active_states:
            try:
                running_states[resource_type] = self.get_resource_state(resource_type, inactive_state=inactive_state)
            except Exception as e:
                logger.error(f"Error getting state for {resource_type}: {e}")
                running_states[resource_type] = []
        return running_states
    
    def stop_resources(self, resource_type: Optional[str] = None, resource_name: Optional[str] = None) -> None:
        """
        Stop all running resources across all supported types or a specific resource type.

        If resource_type is not specified, all running resources across all supported types will be stopped.
        If resource_type is specified, only the resources of that type that are currently running will be stopped.
        If resource_name is specified, only the resource with that name will be stopped.
        """
        resources = self.get_running_resources(inactive_state=False)
        if resource_type:
            resources = resources.get(resource_type, [])
        if resource_name:
            resources = [r for r in resources if r.get("name") == resource_name]
        for resource_type,resource_details in resources.items():
           for resource in resource_details:
                name = resource.get("name")
                endpoint = self.get_stop_endpoint_resource(resource_type, name)
                logger.info("*" * 50)
                logger.info(f"Endpoint to stop: {endpoint}")
                logger.info("*" * 50)
                headers = {
                    "Authorization": f"Bearer {self.host_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                try:
                    response = requests.post(endpoint, headers=headers, timeout=10, verify=False)
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error stopping resource {name}: {e}")

    def get_stop_endpoint_resource(self, resource_type: str, name: str) -> str:
        """
        Get the endpoint to stop a resource of a specific type.
        """
        endpoints = {
            "rds": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/rds/instance/{name}/stop",
          #  "opensearch": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/opensearch/{name}/stop",
          #  "ecache": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/ecache/{name}/stop",
          #  "asg": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/asg/{name}/stop"
        }
        return endpoints.get(resource_type, "")

    def start_resources(self, resource_type: Optional[str] = None, resource_name: Optional[str] = None) -> None:
        """
        Stop all running resources across all supported types or a specific resource type.

        If resource_type is not specified, all running resources across all supported types will be stopped.
        If resource_type is specified, only the resources of that type that are currently running will be stopped.
        If resource_name is specified, only the resource with that name will be stopped.
        """
        resources = self.get_running_resources(inactive_state=True)
        if resource_type:
            resources = resources.get(resource_type, [])
        if resource_name:
            resources = [r for r in resources if r.get("name") == resource_name]
        for resource_type,resource_details in resources.items():
           for resource in resource_details:
                name = resource.get("name")
                endpoint = self.get_start_endpoint_resource(resource_type, name)
                logger.info("*" * 50)
                logger.info(f"Endpoint to start: {endpoint}")
                logger.info("*" * 50)
                headers = {
                    "Authorization": f"Bearer {self.host_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                try:
                    response = requests.post(endpoint, headers=headers, timeout=10, verify=False)
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error stopping resource {name}: {e}")

    def get_start_endpoint_resource(self, resource_type: str, name: str) -> str:
        """
        Get the endpoint to stop a resource of a specific type.
        """
        endpoints = {
            "rds": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/rds/instance/{name}/start",
          #  "opensearch": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/opensearch/{name}/stop",
          #  "ecache": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/ecache/{name}/stop",
          #  "asg": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/asg/{name}/stop"
        }
        return endpoints.get(resource_type, "")

    def format_resource_state(self, resources: Dict[str, List[Dict[str, Any]]],custom_state: str) -> str:
        """
        Format resource state information in a user-friendly way.
        """
        formatted_output = []
        
        for resource_type, instances in resources.items():
            if instances:
                formatted_output.append(f"\n{resource_type.upper()}")
                for instance in instances:
                    name = instance.get("name", "")
                    state = instance.get("state", "")
                    if custom_state.lower() is not "":
                        formatted_output.append(f"  - {name}: {custom_state.lower()}")                    
                    else:
                        formatted_output.append(f"  - {name}: {state}")

        
        return "\n".join(formatted_output)

class StateResourceAgent(Resource):
    """
    An agent that creates RDS resource.
    """
   
    def __init__(self, llm: BedrockAnthropicLLM, system_prompt: Optional[str] = None):
        """
        Initialize the CommandAgent with an LLM instance and optional custom system prompt.
        """
        self.llm = llm
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")


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
        if any("running resources" in msg.get("content", "").lower() for msg in messages):
            system_prompt += f"""
The running resource in tenant {self.tenant_name} is {messages[-1].get("content", "")}.
You are a precise echo. When the user provides a sentence, you must repeat it exactly, without adding or removing anything. Do not change punctuation, casing, or formatting. Just return the exact sentence as-is.
"""
        elif any("Stopping all" in msg.get("content", "").lower() for msg in messages):
            system_prompt += f"""
The resource being stopped in tenant {self.tenant_name} is {messages[-1].get("content", "")}.
You are a precise echo. When the user provides a sentence, you must repeat it exactly, without adding or removing anything. Do not change punctuation, casing, or formatting. Just return the exact sentence as-is.
"""
        elif any("Starting all" in msg.get("content", "").lower() for msg in messages):
            system_prompt += f"""
The resource being started in tenant {self.tenant_name} is {messages[-1].get("content", "")}.
You are a precise echo. When the user provides a sentence, you must repeat it exactly, without adding or removing anything. Do not change punctuation, casing, or formatting. Just return the exact sentence as-is.
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

                host_url = platform_ctx.get("duplo_host_url", "")
                tenant_id = platform_ctx.get("tenant_id", "")
                tenant_name = platform_ctx.get("tenant_name", "")
                super().__init__(host_url=host_url, tenant_name=tenant_name, tenant_id=tenant_id)          
            if role=="user":
                content = message.get("content", "")
                #Processing to get all Active resources
                if "all running" in content.lower() or "active resources" in content.lower():
                    content=f"Here are the running resources for tenant {self.tenant_name}:\n\n"
                    running_resources = self.get_running_resources(inactive_state=False)
                    formatted_resources = self.format_resource_state(running_resources,custom_state="")
                    content += f"\n\n{formatted_resources}"
                    logger.info("*" * 50)
                    logger.info(f"Content: {content}")
                    logger.info("*" * 50)

                    preprocessed_message={
                        "role": "user",
                        "content": content
                    }
                    preprocessed_messages.append(preprocessed_message)
                elif "get all stopped" in content.lower() or "get inactive resources" in content.lower() or "show inactive resources" in content.lower() or "show all stopped" in content.lower():
                    content=f"Here are the stopped resources for tenant {self.tenant_name}:\n\n"
                    stopped_resources = self.get_running_resources(inactive_state=True)
                    formatted_resources = self.format_resource_state(stopped_resources,custom_state="")
                    content += f"\n\n{formatted_resources}"
                    logger.info("*" * 50)
                    logger.info(f"Content: {content}")
                    logger.info("*" * 50)

                    preprocessed_message={
                        "role": "user",
                        "content": content
                    }
                    preprocessed_messages.append(preprocessed_message)  
                elif "start" in content.lower() or "resume" in content.lower():
                    content=f"Starting all resources for tenant {self.tenant_name}..."
                    formatted_resources = self.format_resource_state(running_resources,custom_state="starting")
                    self.start_resources()
                    content += f"\n\n{formatted_resources}"
                    logger.info("*" * 50)
                    logger.info(f"Content: {content}")
                    logger.info("*" * 50)

                    preprocessed_message={
                        "role": "user",
                        "content": content
                    }
                    preprocessed_messages.append(preprocessed_message)
                elif "stop all" in content.lower() or "stop" in content.lower() or "pause" in content.lower():
                    content=f"Stopping all resources for tenant {self.tenant_name}..."
                    formatted_resources = self.format_resource_state(running_resources,custom_state="stopping")
                    self.stop_resources()
                    content += f"\n\n{formatted_resources}"
                    logger.info("*" * 50)
                    logger.info(f"Content: {content}")
                    logger.info("*" * 50)

                    preprocessed_message={
                        "role": "user",
                        "content": content
                    }
                    preprocessed_messages.append(preprocessed_message)
                
                else:
                    preprocessed_messages.append({
                        "role": role,
                        "content": message.get("content", "")
                    })
            else:
                preprocessed_messages.append({
                "role": role,
                "content": message.get("content", "")
            })

            
        # Add tenant details to the first message if it's from the user
        #if preprocessed_messages and preprocessed_messages[0]["role"] == "user":
        #    first_msg = preprocessed_messages[0]
        #    first_msg["content"] = f"Tenant ID: {self.tenant_id}\nTenant Name: {self.tenant_name}\n{first_msg["content"]}"
            
        return preprocessed_messages
       

    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        """
        Process user messages and use an LLM to generate responses.
        """
        preprocessed_messages = self.preprocess_messages(messages)
        logger.info(f"Preprocessed messages: {preprocessed_messages}")

        response = self.call_bedrock_anthropic_llm(preprocessed_messages)
      #  logger.info(f"LLM response: {response}")

        return AgentMessage(content=response)

    

