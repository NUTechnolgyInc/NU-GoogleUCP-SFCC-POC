# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""UCP."""

import asyncio
import functools
import json
import logging
import os
import sys

from pathlib import Path
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
import click
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
import uvicorn

from .agent import root_agent as business_agent
from .agent_executor import ADKAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logging.getLogger("google").setLevel(logging.DEBUG)
logging.getLogger("google_genai").setLevel(logging.DEBUG)
logging.getLogger("google_adk").setLevel(logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)

def create_app():
    """Create and configure the Starlette application."""
    base_path = Path(__file__).parent
    card_path = base_path / "data" / "agent_card.json"
    
    if not card_path.exists():
        logger.error(f"Agent card not found at {card_path}")
        # Fallback for Vercel deployment structure if needed
        # base_path = Path("/var/task/a2a/business_agent/src/business_agent")
        # card_path = base_path / "data" / "agent_card.json"
    
    with card_path.open(encoding="utf-8") as f:
        data = json.load(f)
    agent_card = AgentCard.model_validate(data)

    task_store = InMemoryTaskStore()

    request_handler = DefaultRequestHandler(
        agent_executor=ADKAgentExecutor(
            agent=business_agent,
            extensions=agent_card.capabilities.extensions or [],
        ),
        task_store=task_store,
    )

    a2a_app = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    routes = a2a_app.routes()
    routes.extend(
        [
            Route(
                "/",
                lambda _: json.dumps({"status": "ok", "message": "Business Agent is running"}),
            ),
            Route(
                "/.well-known/ucp",
                lambda _: FileResponse(base_path / "data" / "ucp.json"),
            ),
            Mount(
                "/images",
                app=StaticFiles(directory=str(base_path / "data" / "images")),
                name="images",
            ),
        ]
    )
    return Starlette(routes=routes)

# Expose app for Vercel
app = create_app()

def make_sync(func):
    """Wrap an async function to run synchronously."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=10999)
@make_sync
async def run(host, port):
    """Run the A2A business agent server locally."""
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY must be set")
        exit(1)

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    run()
