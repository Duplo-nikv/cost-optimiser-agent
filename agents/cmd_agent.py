import json

import logging
import traceback

import subprocess
import os
from typing import List, Dict, Any, Optional

from agent_server import AgentProtocol
from schemas.messages import AgentMessage, Command, ExecutedCommand, Data
from services.llm import BedrockAnthropicLLM

logger = logging.getLogger(__name__)

class CommandAgent(AgentProtocol):
    """
    An agent that processes user messages, executes terminal commands with user approval,
    and uses an LLM to generate responses and suggest commands.
    """
    
    def __init__(self, llm: BedrockAnthropicLLM, system_prompt: Optional[str] = None):
        """
        Initialize the CommandAgent with an LLM instance and optional custom system prompt.
        
        Args:
            llm: An instance of BedrockAnthropicLLM for generating responses
            system_prompt: Optional custom system prompt to override the default
        """
        self.llm = llm
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.response_schema = self._create_response_schema()
    
    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        """
        Process user messages, execute commands if approved, and generate a response.
        
        Args:
            messages: A dictionary containing message history in the format {"messages": [...]}
            
        Returns:
            An AgentMessage containing the response, suggested commands, and executed commands
        """
        # Process messages to handle command execution and prepare for LLM
        processed_messages, executed_commands = self.process_messages(messages)
        
        # Generate response from LLM
        llm_response = self.call_llm(processed_messages)
        
        # Extract commands from LLM response
        commands = self._extract_commands(llm_response)
        
        # Create and return the agent message with both suggested and executed commands
        return AgentMessage(
            content=llm_response.get("content", "I'm unable to provide a response at this time."),
            data=Data(
                cmds=[Command(command=cmd["command"]) for cmd in commands],
                executed_cmds=[ExecutedCommand(command=cmd["command"], output=cmd["output"]) 
                              for cmd in executed_commands]
            )
        )
    
    def process_messages(self, messages: Dict[str, List[Dict[str, Any]]]) -> tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """
        Process the raw messages to handle command execution and prepare for LLM.
        
        Args:
            messages: A dictionary containing message history in the format {"messages": [...]}
            
        Returns:
            A tuple containing:
            - A list of processed messages ready for the LLM
            - A list of executed commands with their outputs
        """
        processed_messages = []
        executed_cmds = []
        
        # Extract the messages list from the dictionary
        messages_list = messages.get("messages", [])
        
        for msg in messages_list:
            # Ensure we're only processing messages with valid roles (user or assistant)
            role = msg.get("role")
            if role not in ["user", "assistant"]:
                continue
                
            # Create a basic message with role and content
            processed_msg = {"role": role, "content": msg.get("content", "")}
            
            # Process user messages with approved commands
            if role == "user":
                data = msg.get("data", {})
                
                # Check for commands to execute - only in the current message
                if "cmds" in data and msg == messages_list[-1]:  # Only check the most recent message
                    logger.info(f"Processing commands in most recent user message: {data['cmds']}")
                    for cmd in data["cmds"]:
                        if cmd.get("execute", False):
                            logger.info(f"Executing approved command: {cmd['command']}")
                            # Execute the approved command
                            output = self.execute_cmd(cmd["command"])
                            
                            # Track executed commands
                            executed_cmds.append({
                                "command": cmd["command"],
                                "output": output
                            })
                            
                            # Append command output to the message content
                            cmd_info = f"\n\nExecuted command: {cmd['command']}\nOutput: {output}"
                            processed_msg["content"] += cmd_info
                        else:
                            logger.info(f"Skipping command without execute flag: {cmd['command']}")
                
                # Include previously executed commands
                if "executed_cmds" in data and data["executed_cmds"]:
                    for cmd in data["executed_cmds"]:
                        executed_cmds.append(cmd)
                        cmd_info = f"\n\nPreviously executed: {cmd['command']}\nOutput: {cmd['output']}"
                        processed_msg["content"] += cmd_info
            
            # Add the processed message to the list
            processed_messages.append(processed_msg)
        
        return processed_messages, executed_cmds
    
    def call_llm(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make an API call to the LLM with the processed messages.
        
        Args:
            messages: A list of processed message dictionaries
            
        Returns:
            The LLM response as a dictionary
        """
        try:
            # Use the schema as a tool to structure the response
            tool_choice = {
                "type": "tool",
                "name": "return_response"
            }
            
            # Invoke the LLM with the messages, system prompt, and response schema
            model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")
            response = self.llm.invoke(
                model_id=model_id,
                messages=self.llm.normalize_message_roles(messages),
                max_tokens=4000,
                system_prompt=self.system_prompt,
                tools=[self.response_schema],
                tool_choice=tool_choice
            )
            
            logger.info(f"LLM Response: {response}")
            return response
        except Exception as e:
            traceback_error = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error("Error while making LLM API call:\n%s", traceback_error)

            if "An error occurred (ExpiredTokenException) when calling the InvokeModel operation: The security token included in the request is expired" in str(e):
                solution = "If running the agent locally with Bedrock, refresh the aws creds in the .env file (use the env_update_aws_creds.sh script if using DuploCloud; refer README)."
                raise Exception(f"Error while making LLM API call: {str(e)}. {solution}")
            else:
                raise Exception(f"Error while making LLM API call: {str(e)}")
    
    def execute_cmd(self, command: str) -> str:
        """
        Execute a terminal command and return its output.
        
        Args:
            command: The command string to execute
            
        Returns:
            The command output as a string
        """
        try:
            logger.info(f"Executing command: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
            
            # Combine stdout and stderr for the output
            output = result.stdout
            if result.stderr:
                if output:
                    output += f"\n\nErrors:\n{result.stderr}"
                else:
                    output = f"Errors:\n{result.stderr}"
                    
            if not output:
                output = "Command executed successfully with no output."
                
            return output
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return f"Error executing command: {str(e)}"
    
    def _extract_commands(self, llm_response: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract commands from the LLM response.
        
        Args:
            llm_response: The response from the LLM
            
        Returns:
            A list of command dictionaries
        """
        commands = []
        
        # Extract commands if they exist in the response
        if "terminal_commands" in llm_response:
            commands = llm_response["terminal_commands"]
        
        return commands
    
    def _default_system_prompt(self) -> str:
        """
        Return the default system prompt for the LLM.
        
        Returns:
            The system prompt string
        """
        return """
        You are a helpful terminal command assistant. Your role is to assist users by suggesting 
        appropriate terminal commands to accomplish their tasks and explain the commands clearly.
        
        Guidelines:
        1. Suggest precise, safe terminal commands that directly address the user's request
        2. Explain what each command does and why you're suggesting it
        3. If multiple commands are needed, list them in the correct sequence
        4. Be mindful of different operating systems - ask for clarification if needed
        5. Provide clear, concise explanations in plain language
        6. If a task cannot be accomplished with terminal commands, explain why and suggest alternatives
        7. Always prioritize safe commands that won't damage the user's system
        
        Always use the structured response format to organize your suggestions.
        """
    
    def _create_response_schema(self) -> Dict[str, Any]:
        """
        Create the JSON schema for structured LLM responses.
        
        Returns:
            The response schema as a dictionary
        """
        return {
            "name": "return_response",
            "description": "Generate a structured response with explanatory text and terminal commands",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The main response text to display to the user. Should provide a clear explanation."
                    },
                    "terminal_commands": {
                        "type": "array",
                        "description": "Terminal commands that will be displayed to the user for approval before execution.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "The complete terminal command string to be executed."
                                },
                                "explanation": {
                                    "type": "string",
                                    "description": "A brief explanation of what this command does."
                                }
                            },
                            "required": ["command"]
                        }
                    }
                },
                "required": ["content"]
            }
        }
