import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from dotenv import load_dotenv
load_dotenv()

from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm

# ==========================================
# 1. MOCK DATABASE
# ==========================================
pipeline_db = {}
def save_pipeline(session_id, history, state): pipeline_db[session_id] = {"state": state}
def load_pipeline(session_id): return [], pipeline_db.get(session_id, {}).get("state", {})

# ==========================================
# 2. AGENTS & SWARM
# ==========================================
extractor = Agent(
    name="Extractor",
    instructions="Extract the core entities from the user's prompt and update the global state."
)

writer = Agent(
    name="Writer",
    instructions="Read the global state and write a 1-sentence summary of the entities."
)

swarm = Swarm(
    agents=[extractor, writer], 
    save_handler=save_pipeline, 
    load_handler=load_pipeline
)

async def main():
    print("--- Running Supervised Data Pipeline ---")
    await swarm.execute_plan_async(
        user_input="Apple just released the M4 MacBook Pro in Space Black for $1999.",
        session_id="job_404"
    )
    
    print("\n--- Final Database Record ---")
    print(pipeline_db)

if __name__ == "__main__":
    asyncio.run(main())