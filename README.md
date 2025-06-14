# Service Desk Agents

A flexible, protocol-based service desk agent framework built with FastAPI that enables various agent implementations to respond to user chat messages.

## Overview

This project provides a modular framework for creating, testing and deploying agents that can integrate with DuploCloud Service Desk and can:

- Process chat messages from users
- Integrate with AWS Bedrock for LLM capabilities (especially Anthropic Claude models)
- Provide a standardized message schema for communication
- Include a mock UI for testing interactions

## Project Structure

```
├── agent_server.py         # FastAPI server and agent protocol definition
├── agents/                 # Agent implementations
│   ├── boilerplate_agent.py # Minimal starter boilerplate agent
│   ├── cmd_agent.py        # Command-execution agent implementation
│   ├── echo_agent.py       # Simple echo agent implementation
│   └── llm_passthrough_agent.py # Agent that passes through to LLM
├── main.py                 # Application entry point
├── schemas/                # Pydantic data models
│   └── messages.py         # Message schema definitions
├── services/               # Service implementations
│   └── llm.py              # AWS Bedrock LLM integration
└── service_desk_mock_ui.py # Mock UI for testing
```

## Getting Started

### Prerequisites

- Python 3.8+
- The application uses AWS Bedrock for LLM functionality. Configure your AWS credentials in the `.env` file (refer to env.example) or through standard AWS credential methods (environment variables, IAM roles, etc.) when running locally. Not required when deployed in DuploCloud.

### Installation

1. Clone the repository:

```bash
git clone https://github.com/duplocloud/service-desk-agents.git
cd service-desk-agents
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy the environment example file and configure it:

```bash
cp env.example .env
```

Edit the `.env` file with your AWS credentials and other configuration values.

### AWS Credentials Setup

Use [`env_update_aws_creds.sh`](./env_update_aws_creds.sh) to fetch temporary AWS credentials via `duplo-jit`. It creates `.env` if not present, adds missing variables, and updates credentials. Uses default host (`https://duplo.hackathon.duploworkshop.com/`) and tenant (`agents`), overridable with `--host` and `--tenant` arguments.

Make executable and run:
```bash
chmod +x env_update_aws_creds.sh
./env_update_aws_creds.sh [--host=HOST_URL] [--tenant=TENANT_NAME]
```

### Running the Application

Start the server:

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --port 8000 --reload
```

### API Endpoints

- **Health Check**: `GET /health`
- **Send Message**: `POST /api/sendMessage`

### Testing the API

- Import the postman collection in the project root (service-desk-agent.postman_collection.json) into postman to try out the /health and /api/sendMessage endpoints

(or)

- Sample cURL for /api/sendMessage:
```
  curl --location 'http://localhost:8000/api/sendMessage' \
--header 'Content-Type: application/json' \
--data '{
 "messages" : [
    {
        "role" : "user",
        "content" : "Hi! What'\''s your name?"
    }
    ]   
}'

```

### Testing the Agent API using Service Desk Mock UI (Work in progress)

```bash
python service_desk_mock_ui.py
```

Note: This is a simple mock UI for testing interactions. Creates a UI that connects to the FastAPI server at `http://localhost:8000/api/sendMessage`. It does not mock all service desk features and only replciates the content and terminal command approval/rejection features. Future support will be added to mock all service desk features for local testing.

### Common Errors and Solutions:

- 404 while testing the /sendMessage API endpoint:
SolutionLTry to replace `0.0.0.0` in the url with `localhost` when making the API call

- `An error occurred (ExpiredTokenException) when calling the InvokeModel operation: The security token included in the request is expired`
Update the aws creds in the .env file (use the env_update_aws_creds.sh script to update it automatically using duplo jit)  

## Boilerplate Agents

The framework includes three boilerplate agent implementations that can be used as-is or as a foundation for custom agents:

### 1. EchoAgent

A simple agent that echoes back the user's last message.

- **Implementation**: `agents/echo_agent.py`
- **Functionality**: Extracts the last user message and returns it prefixed with "Echo: "
- **Use Case**: Useful for testing the messaging framework and verifying that communication is working properly


### 2. LLMPassthroughAgent

A simple agent that passes messages directly to an LLM and returns the response.

- **Implementation**: `agents/llm_passthrough_agent.py`
- **Functionality**: Preprocesses messages and sends them to AWS Bedrock Anthropic LLM, then returns the LLM's response
- **Use Case**: Useful for general conversational assistance without custom processing logic

### 3. CommandAgent

A more sophisticated agent that can process messages, execute terminal commands, and leverage LLM capabilities.

- **Implementation**: `agents/cmd_agent.py`
- **Functionality**:
  - Processes user messages and handles approved command execution
  - Uses AWS Bedrock Anthropic LLM to generate responses and suggest commands
  - Provides structured responses with explanations for suggested commands
  - Tracks and includes executed command outputs in responses
- **Use Case**: Ideal for providing CLI assistance, executing system operations, and helping users with terminal-based tasks

## Creating a New Agent

The easiest way to create a new agent is to modify the existing `BoilerplateAgent` in `agents/boilerplate_agent.py` which provides a minimal implementation of the `AgentProtocol` interface.

Alternatively, you can implement the `AgentProtocol` interface from scratch:

```python
from typing import Dict, Any, List
from agent_server import AgentProtocol
from schemas.messages import AgentMessage

class MyCustomAgent(AgentProtocol):
    def invoke(self, messages: Dict[str, List[Dict[str, Any]]]) -> AgentMessage:
        # Extract messages list from the dictionary
        messages_list = messages.get("messages", [])
        
        # Your agent logic here
        return AgentMessage(content="Your response")
```

After creating your agent, update `main.py` to use it by importing your agent class and updating the agent variable to point to your `agent` instance.

Sample starting point:

Update boilerplate_agent.py to create the following agents.

- Level 1: Refer to the llm_passthrough_agent.py and update the system prompt to give it your information so that it can answer questions about you.

- Level 2: Refer to the CMD boilerplate agent, and update it (the sytem prompt and the json schema descriptions) so that it runs only aws cli commands.

## Coming Soon (Hopefully before tomorrow)

- A boilerplate for a tool calling agent using strands, so that you can create an agent by just adding some python functions with doc strings (tools) and by editing a system prompt
- Boilerplate for workflows
- Better service desk mock UI
- More comprehensive postman collection for testing
- Dockerizaiton

## References:

- Service Desk Request Response Structure:
https://docs.duplocloud.com/docs/ai-suite/ai-studio/developers

## License
See the [LICENSE](LICENSE) file for details.
