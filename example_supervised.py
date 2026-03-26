from dotenv import load_dotenv
load_dotenv()

from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm

# 1. Define highly specialized workers
researcher = Agent(
    name="Researcher",
    instructions="Find factual information about the user's topic. Summarize it into bullet points."
)

copywriter = Agent(
    name="Copywriter",
    instructions="Read the research in the chat history. Write a punchy, 2-sentence marketing tweet based on it."
)

editor = Agent(
    name="Editor",
    instructions="Review the tweet. Add exactly 3 relevant hashtags to the end of it."
)

# 2. Initialize Swarm
swarm = Swarm(agents=[researcher, copywriter, editor])

# 3. Run Supervised
if __name__ == "__main__":
    print("🚀 Running Supervised Swarm (Sequential Pipeline)\n")
    # We do NOT provide a start agent. The Supervisor figures out the flow.
    swarm.execute_plan(user_input="I want to post a tweet about the history of the Apollo 11 moon landing.")