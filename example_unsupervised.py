from dotenv import load_dotenv
load_dotenv()

from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm

# A. The actual Python function
def process_refund(order_number: str) -> str:
    """Simulates hitting a payment gateway to process a refund."""
    # In a real SaaS app, you would hit Stripe's API here
    return f"Success! A refund has been issued to the original payment method for order {order_number}."

# B. The JSON Schema (so the LLM understands it)
refund_schema = {
    "type": "function",
    "function": {
        "name": "process_refund",
        "description": "Process a refund for a customer. Call this ONLY after you have their order number.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {"type": "string", "description": "The ID of the order, e.g., ORD-123"}
            },
            "required": ["order_number"]
        }
    }
}

# Define the Agents
triage_agent = Agent(
    name="Triage",
    instructions="You are the front desk. Ask the user what they need. If it is a refund, transfer to 'Billing'. If it is a bug, transfer to 'Tech'."
)

billing_agent = Agent(
    name="Billing",
    instructions="You handle refunds. Ask for their order number if they didn't provide it. Once you have it, use the `process_refund` tool to issue the refund. Tell the user the result. Do not transfer.",
    tools=[(refund_schema, process_refund)] 
)

tech_agent = Agent(
    name="Tech",
    instructions="You fix bugs. Ask them to describe the error code, then offer a solution. Do not transfer."
)


swarm = Swarm(agents=[triage_agent, billing_agent, tech_agent])

if __name__ == "__main__":
    print("🚀 Running Unsupervised Swarm (Dynamic Chat)\n")
    

    swarm.execute(
        start_agent_name="Triage", 
        user_input="I am very angry. I want a refund for my subscription. My order number is INV-992."
    )