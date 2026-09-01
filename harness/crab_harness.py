"""Crab-1 tool schemas (OpenAI-style function specs).

Single source of truth for the agent's tool interface — used by the eval
harness and, at training time, baked into the chat template so training and
evaluation see the identical schema.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for a query. Returns up to N results with title, URL, snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_extract",
            "description": "Extract clean markdown content from one or more URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}},
                    "char_limit": {"type": "integer", "default": 8000},
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registry_lookup",
            "description": "Query the French official company registry for SIREN, SIRET, NAF/sector, city, headcount. Returns deterministic structured data.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Submit final structured company profile and finish the episode.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "website": {"type": "string"},
                    "sector": {"type": "string"},
                    "city": {"type": "string"},
                    "headcount": {"type": "string"},
                    "summary": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "website", "city", "summary", "sources"],
            },
        },
    },
]


def call_llm(model, messages, tools=None, temperature=0.3,
             base_url="http://localhost:11434"):
    """Call an OpenAI-compatible endpoint (Ollama by default)."""
    import requests

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
    resp = requests.post(f"{base_url}/v1/chat/completions", json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()
