import sys
from pathlib import Path

# Resolve project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Add business_agent src to PYTHONPATH
BA_SRC = BASE_DIR / "a2a" / "business_agent" / "src"
sys.path.insert(0, str(BA_SRC))

from business_agent.main import app

# ASGI handler
handler = app
