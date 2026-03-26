import typer
from rich.console import Console
import os
import uvicorn

app = typer.Typer(help="The official CLI for your Multi-Agent Framework")
console = Console()

@app.command()
def init():
    """Initialize a new multi-agent project in the current directory."""
    console.print("[bold blue]🚀 Initializing new agent project...[/bold blue]")
    
    os.makedirs("agents", exist_ok=True)
    
    template = """from swarm_kit.core.agent import Agent
from swarm_kit.core.swarm import Swarm

# Define your agents here
researcher = Agent(name="Researcher", instructions="You research things.")

# Run them
if __name__ == "__main__":
    swarm = Swarm(agents=[researcher])
    swarm.execute("Researcher", "Hello world")
"""
    with open("agents/main.py", "w") as f:
        f.write(template)
        
    console.print("[bold green]✔ Done! Created agents/main.py[/bold green]")
    console.print("Run [cyan]python agents/main.py[/cyan] to test it.")

@app.command()
def studio(port: int = 8000):
    """Launch the Agent Studio (UI) to view logs."""
    console.print(f"[bold green]🚀 Launching Agent Studio on http://localhost:{port}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop the server[/dim]")
    
    uvicorn.run("swarm_kit.ui.server:app", host="127.0.0.1", port=port, log_level="warning")

def run():
    app()

if __name__ == "__main__":
    run()