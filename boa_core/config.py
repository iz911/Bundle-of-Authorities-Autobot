"""
Configuration manager for BOA Autobot.
Loads environment variables from .env with fallbacks for local models and server ports.
"""
import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Server Settings
PORT: int = int(os.getenv("PORT", 2345))
HOST: str = os.getenv("HOST", "127.0.0.1")

# Local Model Settings (Ollama / LM Studio / LocalAI)
LOCAL_MODEL_ENABLED: bool = os.getenv("LOCAL_MODEL_ENABLED", "true").lower() in ("true", "1", "yes")
LOCAL_MODEL_PORT: int = int(os.getenv("LOCAL_MODEL_PORT", 11434))
LOCAL_MODEL_BASE_URL: str = os.getenv("LOCAL_MODEL_BASE_URL", f"http://localhost:{LOCAL_MODEL_PORT}/v1")
LOCAL_MODEL_NAME: str = os.getenv("LOCAL_MODEL_NAME", "llama3.2")
LOCAL_MODEL_TIMEOUT: int = int(os.getenv("LOCAL_MODEL_TIMEOUT", 15))

# No cloud model keys and no source addresses are read here on purpose: nothing uses them.
# The only source looked up is eLitigation (see retriever.py).
