"""
src/llm.py — shared OpenRouter client utilities.

Imported by extractor, differ, and auditor.
Single source of truth for: env config, HTTP call, JSON parsing, JSON loading.
"""

import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL   = os.getenv("MODEL", "deepseek/deepseek-chat")


def call_llm(prompt: str) -> str:
    """POST a single user message to OpenRouter and return the reply text."""
    if not API_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY not set — copy .env.example to .env")
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.0},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def parse_json(raw: str, kind: str = "object"):
    """
    Parse a JSON value from an LLM response.

    Args:
        raw:  raw string returned by the model
        kind: "object" (default) → expects dict, opens on '{'
              "array"            → expects list, opens on '['

    Returns:
        Parsed Python dict or list.
    Raises:
        ValueError if nothing parseable is found.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        open_char, close_char = ("{", "}") if kind == "object" else ("[", "]")
        start = cleaned.find(open_char)
        end   = cleaned.rfind(close_char)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON {kind} from response. First 300 chars:\n{raw[:300]}")


def load_json(path: Path) -> list:
    """Read a JSON file and return the parsed value."""
    return json.loads(Path(path).read_text())
