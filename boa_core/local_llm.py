"""
Local Model client for privacy-preserving legal reasoning.
Connects to local OpenAI-compatible endpoints (Ollama, LM Studio, LocalAI)
with an explicit "IDK" prompt protocol to guarantee zero hallucination.
"""
import requests
from typing import Optional, Dict, Any
from .config import (
    LOCAL_MODEL_ENABLED,
    LOCAL_MODEL_BASE_URL,
    LOCAL_MODEL_NAME,
    LOCAL_MODEL_TIMEOUT
)

IDK_SYSTEM_PROMPT = """You are a meticulous Singapore litigation assistant.
Your task is to summarize the legal proposition for which an authority was cited in a single sentence for a court Bundle of Authorities index.
RULES:
1. State the key proposition concisely in one sentence (e.g. "The Court held that...").
2. Do NOT guess or hallucinate facts not in the provided sentence.
3. If you are uncertain or the excerpt does not clearly state the proposition, you MUST respond ONLY with the exact word: "IDK".
"""


class LocalLLMClient:
    """Client for local model endpoints running on localhost."""

    def __init__(
        self,
        base_url: str = LOCAL_MODEL_BASE_URL,
        model_name: str = LOCAL_MODEL_NAME,
        timeout: int = LOCAL_MODEL_TIMEOUT
    ):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def check_health(self) -> Dict[str, Any]:
        """Checks if the local model server is reachable."""
        if not LOCAL_MODEL_ENABLED:
            return {"status": "disabled", "message": "Local model is disabled in .env"}

        try:
            # Check models endpoint
            url = f"{self.base_url}/models"
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                return {
                    "status": "online",
                    "url": self.base_url,
                    "model": self.model_name
                }
        except Exception as e:
            return {
                "status": "offline",
                "url": self.base_url,
                "error": str(e)
            }
        return {"status": "offline", "url": self.base_url}

    def summarize_relevance(self, authority_title: str, citing_sentence: str) -> Optional[str]:
        """
        Generates a 1-sentence relevance summary from the citing sentence.
        Returns None if uncertain or if the model responds with IDK.
        """
        if not LOCAL_MODEL_ENABLED or not citing_sentence:
            return None

        prompt = (
            f"Authority: {authority_title}\n"
            f"Citing Sentence from Submissions: \"{citing_sentence}\"\n\n"
            f"Summarize the legal relevance in one objective sentence, or respond with 'IDK':"
        )

        try:
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": IDK_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 100
            }
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                if content.upper() == "IDK" or "IDK" in content.upper() and len(content) < 10:
                    return None
                return content
        except Exception:
            return None

        return None
