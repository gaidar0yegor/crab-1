"""Single source of truth for the Crab-1 agent interface.

Used by the SFT converter, the trainer, and the eval harness so training and
evaluation see the identical system prompt + tool schema (no train/eval skew).
"""
from harness.crab_harness import TOOLS  # native OpenAI-style function specs

# Concise system prompt. The tool *schemas* are provided natively (the chat
# template renders them), so we don't re-list them in prose. The `/no_think`
# tag keeps Qwen3 from emitting long <think> blocks that slow the tool loop.
SYSTEM_PROMPT = (
    "You are Crab-1, an OSINT agent that builds a factual profile of a French "
    "company from its name. Use the provided tools to gather verifiable facts; "
    "always begin with registry_lookup, then find the official website. Report "
    "the official website, the company's administrative department (département) "
    "in the `city` field, and its sector. Do not guess — rely on tool results. "
    "When you have the facts, call submit_answer. /no_think"
)

__all__ = ["TOOLS", "SYSTEM_PROMPT"]
