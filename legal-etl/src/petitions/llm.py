from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx


class LLMClient(Protocol):
    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        ...


@dataclass
class LocalQwenClient:
    """
    Minimal client for a locally hosted Qwen model via Ollama HTTP API.
    """

    model: str = "qwen2.5:32b-instruct"
    endpoint: str = "http://localhost:11434/api/generate"
    timeout: float = 120.0

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
        }
        try:
            resp = httpx.post(self.endpoint, json=payload, timeout=self.timeout)
        except Exception as exc:  # pragma: no cover - network errors are environment specific
            raise RuntimeError(
                "Ollama/Qwen endpoint'a bağlanılamadı. "
                "Lütfen `ollama serve` ve modeli ayakta olduğundan emin olun."
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama/Qwen API hatası: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        # Ollama returns {"response": "..."}
        if "response" in data:
            return data["response"]
        if "message" in data:
            # Some deployments may return under `message`
            return data["message"]
        raise RuntimeError(f"Beklenmedik Ollama yanıtı: {json.dumps(data)}")


@dataclass
class StaticLLMClient:
    """
    Test/deterministic client.
    """

    text: str

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        return self.text
