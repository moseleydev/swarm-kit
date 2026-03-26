import json
import os
from typing import List, Dict, Any, Optional, Callable, Tuple
from .agent import Agent
from rich.console import Console
from litellm import completion

console = Console()

class Swarm:
    def __init__(
        self, 
        agents: List[Agent], 
        planner_model: str = "gpt-4o",
        save_handler: Optional[Callable[[str, List, Dict], None]] = None,
        load_handler: Optional[Callable[[str], Tuple[List, Dict]]] = None
    ):
        self.history: List[Dict[str, Any]] = []
        self.agent_registry = {agent.name: agent for agent in agents}
        self.log_file = ".swarm_runs.jsonl"
        self.planner_model = planner_model
        
        # Database Hooks
        self.save_handler = save_handler
        self.load_handler = load_handler

    def _save_log(self, agent_name: str, action: str, content: str):
        log_entry = json.dumps({"agent": agent_name, "action": action, "content": content})
        with open(self.log_file, "a") as f:
            f.write(log_entry + "\n")

    # ==========================================
    # MODE 1: UNSUPERVISED (SYNC)
    # ==========================================
    def execute(self, start_agent_name: str, user_input: str, state: Optional[Dict[str, Any]] = None, max_turns: int = 15):
        """Standard sync decentralized execution."""
        self.history.append({"role": "user", "content": user_input})
        global_state = state if state is not None else {}
        
        if os.path.exists(self.log_file): os.remove(self.log_file)
        self._save_log("System", "Start", f"User Input: {user_input}")
        
        current_agent = self.agent_registry.get(start_agent_name)
        if not current_agent: return console.print(f"[red]Error: Agent not found.[/red]")

        console.print(f"[bold blue]Swarm:[/bold blue] Task started with [magenta]{current_agent.name}[/magenta] (Unsupervised)\n")

        for turn in range(max_turns):
            output = current_agent.run(self.history, global_state)
            if output.content:
                console.print(f"[green]{current_agent.name}:[/green] {output.content}\n")
                self.history.append({"role": "assistant", "content": output.content})
                self._save_log(current_agent.name, "Response", output.content)
            
            if output.tool_calls:
                action_taken = False
                for tool in output.tool_calls:
                    tool_name, args = tool["name"], tool["arguments"]
                    if tool_name in current_agent.functions:
                        console.print(f"[bold magenta]⚙️ Executing Tool:[/bold magenta] {tool_name}({args})")
                        try: res = current_agent.functions[tool_name](**args)
                        except Exception as e: res = f"Error: {e}"
                        console.print(f"[dim]Result: {res}[/dim]\n")
                        self.history.append({"role": "system", "content": f"Tool '{tool_name}' returned: {res}"})
                        action_taken = True
                        break
                    elif tool_name == "update_state":
                        k, v = args.get("key"), args.get("value")
                        global_state[k] = v
                        console.print(f"[bold cyan]💾 State Updated:[/bold cyan] {k} = {v}")
                        self.history.append({"role": "system", "content": f"System: State updated '{k}' to '{v}'."})
                        action_taken = True
                        break 
                    elif tool_name == "transfer":
                        next_agent = args.get("next_agent")
                        if next_agent in self.agent_registry and next_agent != current_agent.name:
                            console.print(f"[bold yellow]🔄 Transferring to {next_agent}...[/bold yellow]\n")
                            self.history.append({"role": "system", "content": f"System: Transferred to {next_agent}."})
                            current_agent = self.agent_registry[next_agent]
                            action_taken = True
                        break 
                if action_taken: continue 
            
            console.print("[bold blue]Swarm:[/bold blue] Task complete. 🏁")
            break

    # ==========================================
    # MODE 1.5: UNSUPERVISED (ASYNC WITH DB HOOKS)
    # ==========================================
    async def execute_async(self, start_agent_name: str, user_input: str, state: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None, max_turns: int = 15):
        """Non-blocking execution with database persistence."""
        global_state = state if state is not None else {}
        
        # 1. LOAD FROM DATABASE
        if session_id and self.load_handler:
            loaded_history, loaded_state = self.load_handler(session_id)
            if loaded_history: self.history = loaded_history
            if loaded_state: global_state.update(loaded_state)
            console.print(f"[dim]Loaded session {session_id} from database.[/dim]")

        self.history.append({"role": "user", "content": user_input})
        if os.path.exists(self.log_file): os.remove(self.log_file)
        self._save_log("System", "Start", f"Async User Input: {user_input}")
        
        current_agent = self.agent_registry.get(start_agent_name)
        if not current_agent: return console.print(f"[red]Error: Agent not found.[/red]")

        console.print(f"[bold blue]Swarm:[/bold blue] Async Task started with [magenta]{current_agent.name}[/magenta]\n")

        for turn in range(max_turns):
            # AWAIT THE ASYNC AGENT
            output = await current_agent.run_async(self.history, global_state)
            if output.content:
                console.print(f"[green]{current_agent.name}:[/green] {output.content}\n")
                self.history.append({"role": "assistant", "content": output.content})
                self._save_log(current_agent.name, "Response", output.content)
            
            if output.tool_calls:
                action_taken = False
                for tool in output.tool_calls:
                    tool_name, args = tool["name"], tool["arguments"]
                    if tool_name in current_agent.functions:
                        console.print(f"[bold magenta]⚙️ Executing Tool:[/bold magenta] {tool_name}({args})")
                        try: res = current_agent.functions[tool_name](**args)
                        except Exception as e: res = f"Error: {e}"
                        self.history.append({"role": "system", "content": f"Tool '{tool_name}' returned: {res}"})
                        action_taken = True
                        break
                    elif tool_name == "update_state":
                        k, v = args.get("key"), args.get("value")
                        global_state[k] = v
                        console.print(f"[bold cyan]💾 State Updated:[/bold cyan] {k} = {v}")
                        self.history.append({"role": "system", "content": f"System: State updated '{k}' to '{v}'."})
                        action_taken = True
                        break 
                    elif tool_name == "transfer":
                        next_agent = args.get("next_agent")
                        if next_agent in self.agent_registry and next_agent != current_agent.name:
                            console.print(f"[bold yellow]🔄 Transferring to {next_agent}...[/bold yellow]\n")
                            self.history.append({"role": "system", "content": f"System: Transferred to {next_agent}."})
                            current_agent = self.agent_registry[next_agent]
                            action_taken = True
                        break 
                if action_taken: continue 
            
            console.print("[bold blue]Swarm:[/bold blue] Task complete. 🏁")
            break

        # 2. SAVE TO DATABASE
        if session_id and self.save_handler:
            self.save_handler(session_id, self.history, global_state)
            console.print(f"[dim]Saved session {session_id} to database.[/dim]")

    # ==========================================
    # MODE 2: SUPERVISED / PLANNER (SYNC)
    # ==========================================
    def _generate_plan(self, user_input: str) -> List[Dict[str, str]]:
        agent_descriptions = "\n".join([f"- {name}: {agent.instructions}" for name, agent in self.agent_registry.items()])
        system_prompt = f"""You are a Master Orchestrator. Break the user's request into a sequential plan.
        Available Agents:\n{agent_descriptions}\nReturn ONLY a JSON object with a 'plan' array. Each item must have 'agent_name' and 'task'."""
        
        console.print("[bold yellow]🧠 Supervisor is generating a plan...[/bold yellow]")
        response = completion(
            model=self.planner_model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}],
            response_format={"type": "json_object"} 
        )
        return json.loads(response.choices[0].message.content).get("plan", [])

    def execute_plan(self, user_input: str, state: Optional[Dict[str, Any]] = None):
        """Sync Execution of a strict plan."""
        self.history.append({"role": "user", "content": user_input})
        global_state = state if state is not None else {}
        
        if os.path.exists(self.log_file): os.remove(self.log_file)
        self._save_log("System", "Start", f"User Input (Plan Mode): {user_input}")
        
        plan = self._generate_plan(user_input)
        console.print(f"\n[bold magenta]📋 Execution Plan:[/bold magenta]")
        for i, step in enumerate(plan): console.print(f"  {i+1}. [cyan]{step['agent_name']}[/cyan]: {step['task']}")
        print()

        for step in plan:
            agent_name, task = step.get("agent_name"), step.get("task")
            current_agent = self.agent_registry.get(agent_name)
            if not current_agent: continue
                
            console.print(f"[bold blue]Swarm:[/bold blue] Running step with [magenta]{current_agent.name}[/magenta]")
            self.history.append({"role": "system", "content": f"Supervisor Instruction for {current_agent.name}: {task}. Execute this step and update state/use tools if needed."})
            
            for _ in range(3):
                output = current_agent.run(self.history, global_state)
                if output.content:
                    console.print(f"[green]{current_agent.name}:[/green] {output.content}\n")
                    self.history.append({"role": "assistant", "content": output.content})
                    self._save_log(current_agent.name, "Response", output.content)
                
                if output.tool_calls:
                    action_taken = False
                    for tool in output.tool_calls:
                        tool_name, args = tool["name"], tool["arguments"]
                        if tool_name in current_agent.functions:
                            console.print(f"[bold magenta]⚙️ Executing Tool:[/bold magenta] {tool_name}({args})")
                            try: res = current_agent.functions[tool_name](**args)
                            except Exception as e: res = f"Error: {e}"
                            self.history.append({"role": "system", "content": f"Tool '{tool_name}' returned: {res}"})
                            action_taken = True
                            break
                        elif tool_name == "update_state":
                            k, v = args.get("key"), args.get("value")
                            global_state[k] = v
                            console.print(f"[bold cyan]💾 State Updated:[/bold cyan] {k} = {v}")
                            self.history.append({"role": "system", "content": f"State updated '{k}' to '{v}'."})
                            action_taken = True
                            break
                        elif tool_name == "transfer":
                            self.history.append({"role": "system", "content": "You are in Planner mode. Do not transfer."})
                            action_taken = True
                            break
                    if action_taken: continue
                break 

        console.print("[bold blue]Swarm:[/bold blue] All planned steps complete. 🏁")
        console.print(f"\n[bold magenta]Final State:[/bold magenta] {json.dumps(global_state, indent=2)}")
        self._save_log("System", "Complete", f"Plan finished. Final State: {json.dumps(global_state)}")

    # ==========================================
    # MODE 2.5: SUPERVISED / PLANNER (ASYNC WITH DB)
    # ==========================================
    async def execute_plan_async(self, user_input: str, state: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None):
        """Async Execution of a strict plan with database hooks."""
        global_state = state if state is not None else {}
        
        if session_id and self.load_handler:
            loaded_history, loaded_state = self.load_handler(session_id)
            if loaded_history: self.history = loaded_history
            if loaded_state: global_state.update(loaded_state)
            console.print(f"[dim]Loaded session {session_id} from database.[/dim]")

        self.history.append({"role": "user", "content": user_input})
        if os.path.exists(self.log_file): os.remove(self.log_file)
        self._save_log("System", "Start", f"Async Plan Input: {user_input}")
        
        plan = self._generate_plan(user_input) # Supervisor API call is still sync here for simplicity
        
        console.print(f"\n[bold magenta]📋 Execution Plan:[/bold magenta]")
        for i, step in enumerate(plan): console.print(f"  {i+1}. [cyan]{step['agent_name']}[/cyan]: {step['task']}")
        print()

        for step in plan:
            agent_name, task = step.get("agent_name"), step.get("task")
            current_agent = self.agent_registry.get(agent_name)
            if not current_agent: continue
                
            console.print(f"[bold blue]Swarm:[/bold blue] Running step with [magenta]{current_agent.name}[/magenta]")
            self.history.append({"role": "system", "content": f"Supervisor Instruction for {current_agent.name}: {task}. Execute this step and update state/use tools if needed."})
            
            for _ in range(3):
                # AWAIT THE ASYNC AGENT
                output = await current_agent.run_async(self.history, global_state)
                if output.content:
                    console.print(f"[green]{current_agent.name}:[/green] {output.content}\n")
                    self.history.append({"role": "assistant", "content": output.content})
                    self._save_log(current_agent.name, "Response", output.content)
                
                if output.tool_calls:
                    action_taken = False
                    for tool in output.tool_calls:
                        tool_name, args = tool["name"], tool["arguments"]
                        if tool_name in current_agent.functions:
                            console.print(f"[bold magenta]⚙️ Executing Tool:[/bold magenta] {tool_name}({args})")
                            try: res = current_agent.functions[tool_name](**args)
                            except Exception as e: res = f"Error: {e}"
                            self.history.append({"role": "system", "content": f"Tool '{tool_name}' returned: {res}"})
                            action_taken = True
                            break
                        elif tool_name == "update_state":
                            k, v = args.get("key"), args.get("value")
                            global_state[k] = v
                            console.print(f"[bold cyan]💾 State Updated:[/bold cyan] {k} = {v}")
                            self.history.append({"role": "system", "content": f"State updated '{k}' to '{v}'."})
                            action_taken = True
                            break
                        elif tool_name == "transfer":
                            self.history.append({"role": "system", "content": "You are in Planner mode. Do not transfer."})
                            action_taken = True
                            break
                    if action_taken: continue
                break 

        console.print("[bold blue]Swarm:[/bold blue] All planned steps complete. 🏁")
        console.print(f"\n[bold magenta]Final State:[/bold magenta] {json.dumps(global_state, indent=2)}")
        self._save_log("System", "Complete", f"Plan finished. Final State: {json.dumps(global_state)}")

        if session_id and self.save_handler:
            self.save_handler(session_id, self.history, global_state)
            console.print(f"[dim]Saved session {session_id} to database.[/dim]")