'''import json
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

        self.host_url = os.getenv("PORTAL_URL", "https://test13.duplocloud.net")
        self.host_token = os.getenv("PORTAL_TOKEN", "AQAAANCMnd8BFdERjHoAwE_Cl-sBAAAAmo512sQX_0CrFLlAuaR1EgAAAAACAAAAAAAQZgAAAAEAACAAAABo3qDvW9Lk_evPoCxXbtRNz3VejFFu5rHGBb9IUEI9kwAAAAAOgAAAAAIAACAAAABRuekZ8Z3w-kbVYbbNNzXCPDI26pGucUXdIwhVKy7nAMAAAAD0jqLNSm6_VrUNn434gBz-6uUeqWao56UJWgCN70cc-UESBpjJHCbm42alKxy8xxuXKLKw6Ynph2H6P1X0CRVGPgHSxDXTXvM4SLqsE1CQeLfOPHGBWNzmoanZsB0_hsFZ6SmdtJmCWyORRJQg4P4WqYv7EIXruJmAf7A_R4mb7mj3UI62e973cH5Imwk4zrBepMm4B5BJIsDtYEl1bnnxWd83G0FLQP5-AP7447GeW5AJfBwvOKP7YgYA157t9b5AAAAAFZL_FJXpTKxT6PetPVegCsflo9qrnrG3hf8Ean9QArc7NCf6Gwv7EZkwHjxvMasF2HjG_pRMKc0AhCRfZ9s12g")
    
    def call_bedrock_anthropic_llm(self, messages: list):
        system_prompt = "You are a helpful assistant named Duplo Dash."
        return self.llm.invoke(messages=messages, model_id=self.model_id, system_prompt=system_prompt)

    def preprocess_messages(self, messages: Dict[str, List[Dict[str, Any]]]):
        preprocessed_messages = []
        messages_list = messages.get("messages", [])
        flag = dict()
        for message in messages_list:
            if message.get("role") == "user":
                tenantDict = self.fetch_and_store_tenant_names()
                # Check if the user's message content matches a tenant name
                if message.get("content") in tenantDict:
                    tenant_name = message.get("content")
                    tenant_id = tenantDict[tenant_name]
                    tenant = Tenant(tenant_name=tenant_name, tenant_id=tenant_id)
                    content= f"You have selected the tenant: {tenant_name} with ID: {tenant_id}."
                    preprocessed_messages.append({"role": "user", "content": content,})
                    flag["tenant"] = True
                else:
                    preprocessed_messages.append({"role": "user", "content": message.get("content", "")})
            elif message.get("role") == "assistant":
                preprocessed_messages.append({"role": "assistant", "content": message.get("content", "")})
        return preprocessed_messages,flag

    def fetch_and_store_tenant_names(self) -> List[str]:
        """
        Calls the external API to fetch tenants and stores their AccountName as TenantName.
        Returns a list of tenant names.
        """
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        url = f"{self.host_url}/adminproxy/GetTenantNames"
        headers = {
            "Authorization": f"Bearer {self.host_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"  # ← Add this

        }
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            tenants = response.json()
            tenant_dict = {tenant.get("AccountName"): tenant.get("TenantId") for tenant in tenants if tenant.get("AccountName") and tenant.get("AccountName") != "default"}
            logger.info(f"Fetched tenants: {tenant_dict}")
            # Store as TenantName (could be in a class variable or returned)
            logger.info(f"Fetched tenants: {tenant_dict}")
            
            return tenant_dict
        except Exception as e:
            logger.error(f"Error fetching tenant names: {e}")
            return []
    
    def ask_user_to_select_tenant(self) -> AgentMessage:
        tenant_names = self.fetch_and_store_tenant_names()
        if not tenant_names:
            prompt = "Sorry, I couldn't fetch the list of tenants. Please try again later."
            return AgentMessage(content=prompt, data=Data(tenants=[]))

        prompt = (
            "I have fetched the following tenants:\n"
            + "\n".join(f"- {name}" for name in tenant_names)
            + "\n\nOn which tenant would you like to create the RDS resource?"
        )
        logger.info(f"Asking user to select tenant: {tenant_names}")
        return AgentMessage(
            content=prompt,
            data=Data(tenant=None),
        )



    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        preprocessed_messages,flag = self.preprocess_messages(messages)
        logger.info(f"Preprocessed messages: {preprocessed_messages}")
       # content = self.call_bedrock_anthropic_llm(messages=preprocessed_messages)
        # Check if any user message contains a tenant block
        if not flag.get("tenant", False):
            # Proceed with LLM or next step
            return self.ask_user_to_select_tenant()
        else:
            m=self.call_bedrock_anthropic_llm(messages=preprocessed_messages)
            logger.info(f"LLM response: {m}")
            return AgentMessage(
                content=m,
            )

    def create_rds_resource(self, tenant_name: str, rds_params: Dict[str, Any]) -> str:
        """
        Placeholder for the actual RDS resource creation logic.
        This should interact with the AWS SDK or CLI to create the RDS instance.
        """
        # Example command to create an RDS instance using AWS CLI
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        url = f"{self.host_url}/adminproxy/GetTenantNames"
        headers = {
            "Authorization": f"Bearer {self.host_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"  # ← Add this

        }
        
#    def preprocess_messages(self, messages: Dict[str, List[Dict[str, Any]]]):
#    preprocessed_messages = []
#    messages_list = messages.get("messages", [])
#    for message in messages_list:
#        role = message.get("role")
#        processed_msg = {"role": role, "content": message.get("content", "")}
#        if message.get("role") == "user":
#            #data = message.get("data", {})
#            #tenant = data.get("tenant") if isinstance(data, dict) else None
#            #if tenant:
#            #    logger.info(f"User message contains tenant: {tenant}")
#            #    processed_message = {"role": "user", "content": message.get("content", "")}
#            preprocessed_messages.append(processed_message)
#        
#        elif message.get("role") == "assistant":
#            tenant_names = self.fetch_and_store_tenant_names()
#            tenant_info="I have fetched the following tenants:\n"+ "\n".join(f"- {tenant_name}" for tenant_name in tenant_names)+ "\n\nOn which tenant would you like to create the RDS resource?"
#            processed_msg["content"] += tenant_info
#            preprocessed_messages.append(processed_message)
#    
#    return preprocessed_messages


class Resource(StateResourceAgent):
    """
    An agent to fetch the state of various resources (RDS, Opensearch, ElastiCache, ASG) for a given tenant.
    Inherits host_url and host_token from RestartRDSAgent.
    """

    def __init__(self, llm: BedrockAnthropicLLM, system_prompt: Optional[str] = None):
        super().__init__(llm, system_prompt)
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    def _get_resource(self, tenant_id: str, resource_type: str) -> List[Dict[str, Any]]:
        """
        Helper to fetch resources of a given type for a tenant.
        """
        resource_map = {
            "rds": f"v3/subscriptions/{tenant_id}/aws/rds/instance",
            "opensearch": "GetOpensearchDomains",
            "ecache": "GetElastiCacheInstances",
            "asg": "GetAutoScalingGroups"
        }
        endpoint = resource_map.get(resource_type)
        if not endpoint:
            logger.error(f"Unknown resource type: {resource_type}")
            return []

        url = f"{self.host_url}/{endpoint}"
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
            logger.error(f"Error fetching {resource_type} for tenant {tenant_id}: {e}")
            return []

    def get_rds_state(self, tenant_id: str) -> List[Dict[str, str]]:
        """
        Returns a list of dicts with RDS instance name and state.
        """
        rds_list = self._get_resource(tenant_id, "rds")
        return [{"name": rds.get("Identifier"), "state": rds.get("InstanceStatus")} for rds in rds_list]

#    def get_opensearch_state(self, tenant_id: str) -> List[Dict[str, str]]:
#        """
#        Returns a list of dicts with Opensearch domain name and state.
#        """
#        domains = self._get_resource(tenant_id, "opensearch")
#        return [{"name": d.get("DomainName"), "state": d.get("DomainStatus", {}).get("Processing", "unknown")} for d in domains]
#
#    def get_ecache_state(self, tenant_id: str) -> List[Dict[str, str]]:
#        """
#        Returns a list of dicts with ElastiCache cluster name and state.
#        """
#        clusters = self._get_resource(tenant_id, "ecache")
#        return [{"name": c.get("CacheClusterId"), "state": c.get("CacheClusterStatus")} for c in clusters]
#
#    def get_asg_state(self, tenant_id: str) -> List[Dict[str, str]]:
#        """
#        Returns a list of dicts with ASG name and state.
#        """
#        asgs = self._get_resource(tenant_id, "asg")
#        return [{"name": a.get("AutoScalingGroupName"), "state": a.get("Status", "unknown")} for a in asgs]
'''

class Resource:
    """
    Base class for managing resources.
    """
    def __init__(self, host_url: str, host_token: str, tenant_id: str):
        """
        Initialize the resource manager.
        """
        self.host_url = host_url
        self.host_token = host_token
        self.tenant_id = tenant_id
        self.active_states = {
            "rds": ["available"],  # RDS instances
            "opensearch": ["true"],  # OpenSearch domains
            "ecache": ["available"],  # ElastiCache clusters
            "asg": ["Active", "InService"]  # Auto Scaling Groups
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
            "opensearch": "GetOpensearchDomains",
            "ecache": "GetElastiCacheInstances",
            "asg": "GetAutoScalingGroups"
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

    def get_resource_state(self, resource_type: str) -> List[Dict[str, Any]]:
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
            if state in [s.lower() for s in self.active_states.get(resource_type, [])]:
                active_resources.append(resource)
        
        return active_resources

    def get_running_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all running resources across all supported types.
        """
        running_states = {}
        for resource_type in self.active_states:
            try:
                running_states[resource_type] = self.get_resource_state(resource_type)
            except Exception as e:
                logger.error(f"Error getting state for {resource_type}: {e}")
                running_states[resource_type] = []
        return running_states

    def format_resource_state(self, resources: Dict[str, List[Dict[str, Any]]]) -> str:
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
                    formatted_output.append(f"  - {name}: {state}")
        
        return "\n".join(formatted_output)
