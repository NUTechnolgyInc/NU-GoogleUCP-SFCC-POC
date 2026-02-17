import sys
from pathlib import Path

# Resolve project root
BASE_DIR = Path(__file__).resolve().parent.parent

# Add business_agent src to PYTHONPATH
BA_SRC = BASE_DIR / "apps" / "business_agent" / "src"
sys.path.insert(0, str(BA_SRC))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("api/index.py: Loading business_agent app")

from business_agent.main import app

# ASGI handler
handler = app
logger.info("api/index.py: App loaded successfully")
