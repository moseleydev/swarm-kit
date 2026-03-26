from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import json

app = FastAPI()
LOG_FILE = ".swarm_runs.jsonl"

@app.get("/api/logs")
def get_logs():
    """Returns the raw JSON logs for the frontend to render smoothly."""
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
    return {"logs": logs}

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serves the static SPA dashboard."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Agent Studio</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            /* Custom scrollbar for a sleek look */
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #09090b; }
            ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
            
            /* Smooth transitions for new log entries */
            .log-entry { animation: fadeIn 0.3s ease-in-out; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        </style>
    </head>
    <body class="bg-zinc-950 text-zinc-300 font-sans h-screen flex flex-col antialiased">
        
        <header class="bg-zinc-900 border-b border-zinc-800 px-6 py-4 flex justify-between items-center sticky top-0 z-10">
            <div class="flex items-center gap-3">
                <div class="text-2xl">🤖</div>
                <div>
                    <h1 class="text-zinc-100 font-semibold text-lg leading-tight">Agent Studio</h1>
                    <p class="text-zinc-500 text-xs font-mono">localhost:8000</p>
                </div>
            </div>
            <div class="flex items-center gap-2 px-3 py-1 bg-zinc-950 border border-zinc-800 rounded-full">
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span class="text-xs font-medium text-zinc-400 tracking-wide uppercase">Live</span>
            </div>
        </header>

        <main class="flex-1 overflow-y-auto p-6 scroll-smooth" id="scroll-container">
            <div class="max-w-4xl mx-auto flex flex-col gap-4" id="log-container">
                <div class="text-center py-20 text-zinc-600 font-mono text-sm animate-pulse" id="loading-state">
                    Waiting for swarm execution...
                </div>
            </div>
        </main>

        <script>
            const logContainer = document.getElementById('log-container');
            const scrollContainer = document.getElementById('scroll-container');
            let logCount = 0;
            let isAutoScrolling = true;

            // Detect if user scrolls up, so we don't force them back down
            scrollContainer.addEventListener('scroll', () => {
                const isAtBottom = scrollContainer.scrollHeight - scrollContainer.scrollTop <= scrollContainer.clientHeight + 50;
                isAutoScrolling = isAtBottom;
            });

            function getBadgeStyle(action, agent) {
                if (action === 'Error') return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
                if (action === 'Complete') return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
                if (action === 'Transfer') return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
                if (agent === 'System') return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
                return 'bg-zinc-800 text-zinc-300 border-zinc-700'; // Default Response
            }

            async function fetchLogs() {
                try {
                    const res = await fetch('/api/logs');
                    const data = await res.json();
                    
                    if (data.logs.length > logCount) {
                        // Clear loading state if it exists
                        if (logCount === 0) logContainer.innerHTML = '';

                        // Append only new logs
                        for (let i = logCount; i < data.logs.length; i++) {
                            const log = data.logs[i];
                            const badgeClass = getBadgeStyle(log.action, log.agent);
                            
                            const logEl = document.createElement('div');
                            logEl.className = 'log-entry bg-zinc-900 border border-zinc-800 rounded-lg p-5 shadow-sm';
                            
                            // Format content: wrap code blocks if any, or just maintain whitespace
                            const formattedContent = log.content.replace(/</g, "&lt;").replace(/>/g, "&gt;");

                            logEl.innerHTML = `
                                <div class="flex items-center gap-3 mb-3">
                                    <span class="font-bold text-zinc-200">${log.agent}</span>
                                    <span class="px-2.5 py-0.5 rounded-full text-xs font-medium border ${badgeClass}">
                                        ${log.action}
                                    </span>
                                </div>
                                <div class="text-zinc-400 text-sm font-mono whitespace-pre-wrap leading-relaxed">${formattedContent}</div>
                            `;
                            logContainer.appendChild(logEl);
                        }
                        
                        logCount = data.logs.length;

                        // Auto-scroll to bottom if the user hasn't scrolled up manually
                        if (isAutoScrolling) {
                            scrollContainer.scrollTop = scrollContainer.scrollHeight;
                        }
                    }
                } catch (error) {
                    console.error("Failed to fetch logs:", error);
                }
            }

            // Fetch immediately, then every 1 second
            fetchLogs();
            setInterval(fetchLogs, 1000);
        </script>
    </body>
    </html>
    """
    return html_content