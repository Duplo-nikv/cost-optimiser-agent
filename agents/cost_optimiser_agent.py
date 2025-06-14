
import json
import logging
from queue import Empty
import subprocess
import os
from typing import List, Dict, Any, Optional

from agent_server import AgentProtocol
from schemas.messages import AgentMessage
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
        self.host_token = os.getenv("HOST_TOKEN")
        self.host_url = host_url
        self.tenant_id = tenant_id
        self.active_states = {
            "rds": ["available","stopped"],  # RDS instances
            "ec2": ["running","stopped"],  # ec2 clusters
           # "opensearch": ["true"],  # OpenSearch domains
           # "ecache": ["available"],  # ElastiCache clusters
            "asg": ["running", "stopped"]  # Auto Scaling Groups
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
            "ec2": f"subscriptions/{self.tenant_id}/GetNativeHosts",
            "asg": f"subscriptions/{self.tenant_id}/GetTenantAsgProfiles"
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

    def get_ec2_state(self) -> List[Dict[str, str]]:
        """
        Returns a list of dicts with EC2 instance name and state.
        """
        ec2_list = self._get_resource("ec2")
        return [{
            "name": ec2.get("FriendlyName"),
            "state": ec2.get("Status"),
            "instance_id": ec2.get("InstanceId")
        } for ec2 in ec2_list if ec2.get("AgentPlatform") != 7]

    def get_asg_state(self) -> List[Dict[str, str]]:
        """
        Returns a list of dicts with EC2 instance name and state.
        """
        asg_list = self._get_resource("asg")
        return [{
            "name": asg.get("FriendlyName"),
            "state": "running" if asg.get("MaxSize", 0) > 0 and asg.get("MinSize", 0) > 0 else "stopped",
        } for asg in asg_list]


    def get_resource_state(self, resource_type: str,inactive_state: bool) -> List[Dict[str, Any]]:
        """
        Get state of resources for a specific resource type.
        """
        if resource_type not in self.active_states:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        
        # Get all resources of this type
        all_resources = getattr(self, f"get_{resource_type}_state")()
        
        # Filter for active/running resources
        entity = []
        possibleState=self.active_states.get(resource_type, [])
        for resource in all_resources:
           # state = resource.get("state", "").lower()
           # obj=f"{resource.get('name')} : {state}"
            entity.append(resource)
            #if inactive_state:
            #    
            #    if state == possibleState[1]:
            #        obj=f"{resource.get('name')} : {state}"
            #        entity.append(obj)
            #else:
            #    if state == possibleState[0]:
            #        obj=f"{resource.get('name')} : {state}"
            #        entity.append(obj)
        
        return entity

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
        data = None
        resources = self.get_running_resources(inactive_state=False)
        if resource_type:
            resources = resources.get(resource_type, [])
        if resource_name:
            resources = [r for r in resources if r.get("name") == resource_name]
        for resource_type,resource_details in resources.items():
           for resource in resource_details:
                name = resource.get("name")
                if resource_type == "ec2":
                    name=resource.get("instance_id")
                if resource_type == "asg":
                    data = json.dumps({
                        "FriendlyName": name,
                        "MaxSize": 0,
                        "MinSize": 0
                    })
                endpoint = self.get_stop_endpoint_resource(resource_type, name)
                headers = {
                    "Authorization": f"Bearer {self.host_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                try:
                    response = requests.post(endpoint, headers=headers, timeout=10, verify=False,data=data)
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error stopping resource {name}: {e}")

    def get_stop_endpoint_resource(self, resource_type: str, name: str) -> str:
        """
        Get the endpoint to stop a resource of a specific type.
        """
        endpoints = {
            "rds": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/rds/instance/{name}/stop",
            "ec2": f"{self.host_url}/subscriptions/{self.tenant_id}/stopNativeHost/{name}",
          #  "opensearch": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/opensearch/{name}/stop",
          #  "ecache": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/ecache/{name}/stop",
            "asg": f"{self.host_url}/subscriptions/{self.tenant_id}/UpdateTenantAsgProfile"
        }
        return endpoints.get(resource_type, "")

    def start_resources(self, resource_type: Optional[str] = None, resource_name: Optional[str] = None) -> None:
        """
        Stop all running resources across all supported types or a specific resource type.

        If resource_type is not specified, all running resources across all supported types will be stopped.
        If resource_type is specified, only the resources of that type that are currently running will be stopped.
        If resource_name is specified, only the resource with that name will be stopped.
        """
        data = None
        resources = self.get_running_resources(inactive_state=True)
        if resource_type:
            resources = resources.get(resource_type, [])
        if resource_name:
            resources = [r for r in resources if r.get("name") == resource_name]
        for resource_type,resource_details in resources.items():
           for resource in resource_details:
                name = resource.get("name")
                if resource_type == "ec2":
                    name=resource.get("instance_id")
                if resource_type == "asg":
                    data = json.dumps({
                        "FriendlyName": name,
                        "MaxSize": 2,
                        "MinSize": 1
                    })
                endpoint = self.get_start_endpoint_resource(resource_type, name)
                headers = {
                    "Authorization": f"Bearer {self.host_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                try:
                    response = requests.post(endpoint, headers=headers, timeout=10, verify=False,data=data)
                    response.raise_for_status()
                except Exception as e:
                    logger.error(f"Error stopping resource {name}: {e}")

    def get_start_endpoint_resource(self, resource_type: str, name: str) -> str:
        """
        Get the endpoint to stop a resource of a specific type.
        """
        endpoints = {
            "rds": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/rds/instance/{name}/start",
            "ec2": f"{self.host_url}/subscriptions/{self.tenant_id}/startNativeHost/{name}",
          #  "opensearch": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/opensearch/{name}/stop",
          #  "ecache": f"{self.host_url}/v3/subscriptions/{self.tenant_id}/aws/ecache/{name}/stop",
            "asg": f"{self.host_url}/subscriptions/{self.tenant_id}/UpdateTenantAsgProfile"
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
                    if custom_state.lower() != "":
                        formatted_output.append(f"  - {name}: {custom_state.lower()}")                    
                    else:
                        formatted_output.append(f"  - {name}: {state}")

        
        return "\n".join(formatted_output)

class CostOptimiserAgent(Resource):
    """
    An agent that creates RDS resource.
    """
   
    def __init__(self, llm: BedrockAnthropicLLM, system_prompt: Optional[str] = None):
        """
        Initialize the CommandAgent with an LLM instance and optional custom system prompt.
        """
        self.llm = llm
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
        self.token="t0"
    def call_llm_for_token(self, messages: list) -> str:
        """
        Given a list of message dicts (chat format), return a semantic operation token like t0, t1, ..., t4.
        The LLM is guided with a system prompt that explains the task clearly.
        """
        system_prompt = """
You are an intelligent command router. Based on the user's request, return the correct operation token from the list below.
Respond only with the token ID. Do not explain or add anything else.

Token mappings:
- tenant details → t0
- get running resource → t1
- get stopped resource → t2
- stop running resources → t3
- start stopped resources → t4

If the user asks anything semantically similar, choose the appropriate token.
Examples:
- "show me tenant info" → t0
- "list active resources" → t1
- "bring up stopped instances" → t4
- "pause all services" → t3
- "retrieve halted machines" → t2

Now process the request and return the correct token.
"""

        response = self.llm.invoke(
            messages=messages,
            model_id=self.model_id,
            system_prompt=system_prompt.strip()
        )

        # Assuming content has only the token
        token = response.strip().lower()
        # Optionally validate if it's one of the expected tokens
        valid_tokens = {"t0", "t1", "t2", "t3", "t4"}
        return token if token in valid_tokens else "fallback"

    def call_bedrock_anthropic_llm(self, messages: list):
        """
        Call the LLM with the provided messages and context.
        """
        system_prompt="""
        You are Duplo Dash, a helpful assistant focused on reducing cost by managing resources by stopping the resources when not in use and starting the resources when in use. Here are the details for the current context:
        You should only introduce yourself if user greets you, dont specify any other information until specificaly asked.
        """
        if any("t0" in msg.get("content","").lower() for msg in messages):

            system_prompt += self.tenantDetail_prompt()

        if any("t1" in msg.get("content", "").lower() or "-0" in msg.get("content", "").lower() for msg in messages):

            system_prompt += self.all_runningResources_prompt(messages)

        elif any("t3" in msg.get("content", "").lower() or "-2" in msg.get("content", "").lower() for msg in messages):

            system_prompt += self.stopAllResources_prompt(messages)

        elif any("t4" in msg.get("content", "").lower() or "-3" in msg.get("content", "").lower() for msg in messages):

            system_prompt += self.startAllResources_prompt(messages)

        elif any("t2" in msg.get("content", "").lower() or "-1" in msg.get("content", "").lower() for msg in messages):
        
            system_prompt += self.all_stoppedResources_prompt(messages)
            
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

                host_url = platform_ctx.get("duplo_base_url", "")
                tenant_id = platform_ctx.get("tenant_id", "")
                tenant_name = platform_ctx.get("tenant_name", "")
                super().__init__(host_url=host_url, tenant_name=tenant_name, tenant_id=tenant_id)          
            
            if role=="user":

                #content = message.get("content", "")
                if "t0"==self.token:
                  preprocessed_messages.append(self.tenant_details())

                elif "t1"==self.token:

                    preprocessed_messages.append(self.all_running_resources())

                elif "t2"==self.token:

                    preprocessed_messages.append(self.all_stopped_resources())  

                elif "t4"==self.token:

                    preprocessed_messages.append(self.start_all_stopped_resources())

                elif "t3"==self.token:

                    preprocessed_messages.append(self.stop_all_running_resources())
    
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
            
        return preprocessed_messages
       

    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        """
        Process user messages and use an LLM to generate responses.
        """
        token_messages=self.preprocess_message_for_token(messages)
        self.token=self.call_llm_for_token(token_messages)
        preprocessed_messages = self.preprocess_messages(messages)
        
        response = self.call_bedrock_anthropic_llm(preprocessed_messages)
        return AgentMessage(content=response)

    
    def tenant_details(self)->Dict[str,Any]:
        content=f"t0"
        return  {
              "role": "user",
              "content": content
          }

    def all_running_resources(self)->Dict[str,Any]:
        content=f"t1:\n\n"
        running_resources = self.get_running_resources(inactive_state=False)
        formatted_resources = self.format_resource_state(running_resources,custom_state="")
        content += f"\n\n{formatted_resources}"
        return  {
              "role": "user",
              "content": content
          }                

    def all_stopped_resources(self)->Dict[str,Any]:
        content=f"t2:\n\n"
        stopped_resources = self.get_running_resources(inactive_state=True)
        formatted_resources = self.format_resource_state(stopped_resources,custom_state="")
        content += f"\n\n{formatted_resources}"
        return  {
              "role": "user",
              "content": content
          }                

    def start_all_stopped_resources(self)->Dict[str,Any]:
        content=f"t4"
        stopped_resources = self.get_running_resources(inactive_state=True)
        formatted_resources = self.format_resource_state(stopped_resources,custom_state="starting")
        self.start_resources()
        content += f"\n\n{formatted_resources}"
        return  {
              "role": "user",
              "content": content
          }                                
    
    def stop_all_running_resources(self)->Dict[str,Any]:
        content=f"t3"
        running_resources = self.get_running_resources(inactive_state=False)
        formatted_resources = self.format_resource_state(running_resources,custom_state="stopping")
        self.stop_resources()
        content += f"\n\n{formatted_resources}"
        return  {
              "role": "user",
              "content": content
          }                                
                    
    def tenantDetail_prompt(self)->str:
        return f"""
Tenant ID: {self.tenant_id}
Tenant Name: {self.tenant_name}
Platform URL: {self.host_url}

You can answer questions about:
1. Tenant information (ID, name)
2. Platform details (URL)
3. Resource states and configurations

When answering questions about tenant or platform details, use the stored information above.
"""

    def all_runningResources_prompt(self,messages: list)->str:
        sentence=messages[-1].get("content", "") 
        word_to_remove="t1"
        new_sentence = sentence.replace(word_to_remove, "")
        cleaned_sentence = ' '.join(new_sentence.split())
        content=cleaned_sentence

        return f"""
The running resource in tenant {self.tenant_name} is {content}.
When answering questions about running resources, use the stored information above.
"""
    def all_stoppedResources_prompt(self,messages: list)->str:
        sentence=messages[-1].get("content", "") 
        word_to_remove="t2"
        new_sentence = sentence.replace(word_to_remove, "")
        cleaned_sentence = ' '.join(new_sentence.split())
        content=cleaned_sentence
        return f"""
The stopped resource in tenant {self.tenant_name} is {content}.
When answering questions about stopped resources, use the stored information above.
""" 
    def stopAllResources_prompt(self,messages: list)->str:  
        sentence=messages[-1].get("content", "") 
        word_to_remove="t3"
        new_sentence = sentence.replace(word_to_remove, "")
        cleaned_sentence = ' '.join(new_sentence.split())
        content=cleaned_sentence
        
        return f"""
Here resource has been put to stop, but it will take some time to stop in tenant {self.tenant_name} is {content}.
When answering questions about stopping all resources, use the stored information above.
"""
    
    def startAllResources_prompt(self,messages: list)->str:  
        sentence=messages[-1].get("content", "") 
        word_to_remove="t4"
        new_sentence = sentence.replace(word_to_remove, "")
        cleaned_sentence = ' '.join(new_sentence.split())
        content=cleaned_sentence
        return f"""
Here resource has been put to start, but it will take some time to start in tenant {self.tenant_name} is {content}.
When answering questions about starting all resources, use the stored information above.
"""



    def preprocess_message_for_token(self,messages: list)->str:
        preprocessed_messages = []
        messages_list = messages.get("messages", [])
        # Set host_url and tenant_id from platform context
        message= messages_list[-1].get("content", "")   
        preprocessed_messages.append({
            "role": "user",
            "content": message
        })
        return preprocessed_messages

    