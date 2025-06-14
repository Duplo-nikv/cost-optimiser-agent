"""
Run with:   python main.py
Or `uvicorn main:app --port 8000` if you prefer the CLI.
"""

from agent_server import create_chat_app
from services.llm import BedrockAnthropicLLM
from agents.echo_agent import EchoAgent
from agents.llm_passthrough_agent import LLMPassthroughAgent
from agents.cmd_agent import CommandAgent
from agents.boilerplate_agent import BoilerplateAgent
from agents.cost_optimiser_agent import CostOptimiserAgent
import dotenv

# Load environment variables from .env file and override existing ones
dotenv.load_dotenv(override=True)

# Choose which agent to use
# agent = EchoAgent()
#agent = LLMPassthroughAgent(BedrockAnthropicLLM())
#agent = CommandAgent(BedrockAnthropicLLM())
# agent = BoilerplateAgent()  # Default to the boilerplate agent
agent = CostOptimiserAgent(BedrockAnthropicLLM())
app = create_chat_app(agent)


if __name__ == "__main__":
    import uvicorn
        
    # For reload to work, we need to use an import string instead of the app object
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,     # set True for auto-reload in dev
        log_level="info",
    )
