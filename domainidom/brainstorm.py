from __future__ import annotations

import os
from typing import List
import re

import httpx

DEFAULT_MAX = 50


def _get_llm_base_url() -> str | None:
    return os.getenv("OPENAI_BASE_URL") or os.getenv("LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"


def _get_llm_api_key() -> str | None:
    # For LM Studio local, most endpoints accept empty or dummy key
    return os.getenv("OPENAI_API_KEY", "lm-studio")


def _clean_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*|```$", "", s)
    s = s.strip().strip('"\' ,')
    s = re.sub(r"^[-*\d\.\)\]]+\s*", "", s)
    s = s.strip()
    # Drop list bracket artifacts
    if s in {"[", "]", "[", "]", "{" , "}"}:
        return ""
    return s


def brainstorm_names(idea: str, max_candidates: int = DEFAULT_MAX) -> List[str]:
    prompt = (
        "Generate catchy, memorable brand names based on this idea. "
        "Prefer short, pronounceable, positive names. Reply with a JSON array of unique names only.\n\n"
        f"Idea: {idea}\n"
    )

    # Try local LM Studio compatible API first
    base_url = _get_llm_base_url()
    api_key = _get_llm_api_key()
    model = os.getenv("OPENAI_MODEL", "qwen3-coder-30b-a3b-instruct")

    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a naming assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.9,
                "max_tokens": 800,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        # Fallback: simple deterministic generation if no model server available
        base = [
            "Nexora", "Brandora", "Aivanta", "Memora", "Rhymio", "Cleverly", "Fluxio", "Zenvia",
            "Verveo", "Briofy", "Namewise", "Lumico", "Novara", "Vocalo", "Optimio",
        ]
        return base[:max_candidates]

    # Attempt to parse as a JSON array; if not, split lines
    names: List[str] = []
    if content.startswith("["):
        try:
            import json

            names = [str(x) for x in json.loads(content)]
        except Exception:
            pass
    if not names:
        for line in content.splitlines():
            line = _clean_name(line)
            if line:
                names.append(line)

    # Deduplicate and cap
    seen = set()
    uniq = []
    for n in names:
        n = _clean_name(n)
        if not n:
            continue
        low = n.lower()
        if low not in seen:
            seen.add(low)
            uniq.append(n)
        if len(uniq) >= max_candidates:
            break
    return uniq
