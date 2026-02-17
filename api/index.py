"""
Vercel serverless function entry point for Python Business Agent.
This file is detected by Vercel and proxies to the actual application.
"""
import sys
from pathlib import Path

# Add the business_agent source directory to Python path
business_agent_path = Path(__file__).parent.parent / "a2a" / "business_agent" / "src"
sys.path.insert(0, str(business_agent_path))

# Import the actual application
from business_agent.main import app

# Vercel expects a handler or app object
# Since we're using Starlette/ASGI, we can export the app directly
handler = app
