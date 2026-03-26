import asyncio
import os
import sys

# Ensure swarm_kit can be imported if running directly from the repo
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from dotenv import load_dotenv
load_dotenv()

from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm

# ==========================================
# 1. MOCK DATABASE (BYOD Persistence)
# ==========================================
db = {}

def save_session(session_id, history, state):
    print(f"[DB] Saving session {session_id}...")
    db[session_id] = {"history": history, "state": state}

def load_session(session_id):
    data = db.get(session_id)
    if data:
        print(f"[DB] Resuming session {session_id}...")
        return data["history"], data["state"]
    return [], {}

# ==========================================
# 2. CUSTOM TOOLS
# ==========================================
def lookup_order(order_id: str):
    """Simulates querying a database for an order."""
    orders = {"ORD-123": "Shipped", "ORD-456": "Processing"}
    return orders.get(order_id, "Order not found.")

lookup_schema = {
    "type": "function",
    "function": {
        "name": "lookup_order",
        "description": "Look up the status of a customer's order.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}
    }
}

# ==========================================
# 3. AGENTS & SWARM
# ==========================================
support = Agent(
    name="Support",
    instructions="You are a support agent. If a user asks about an order, use the lookup tool. Keep responses short.",
    tools=[(lookup_schema, lookup_order)]
)

swarm = Swarm(agents=[support], save_handler=save_session, load_handler=load_session)

async def main():
    print("--- User opens chat ---")
    await swarm.execute_async(
        start_agent_name="Support",
        user_input="Can you check on ORD-123?",
        session_id="user_session_99"
    )
    
    print("\n--- User replies 10 minutes later ---")
    # Swarm automatically loads the history from the DB hook
    await swarm.execute_async(
        start_agent_name="Support",
        user_input="Great, thanks! What about ORD-456?",
        session_id="user_session_99"
    )

if __name__ == "__main__":
    asyncio.run(main())