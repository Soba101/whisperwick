"""Opt-in live test. Needs the real model server, so it is skipped by default.

Run it with: LLM_BASE_URL=... LLM_MODEL=... uv run pytest tests/test_llm_live.py
We check the environment (not the .env file) so normal runs never touch the network.
"""

import os

import pytest
from helpers import fresh_world

from whisperwick import llm_agent, settings
from whisperwick.llm_client import OllamaClient


@pytest.mark.skipif(not os.environ.get("LLM_BASE_URL"), reason="needs the model server")
def test_every_living_npc_gets_a_valid_turn_from_the_real_model():
    world = fresh_world()
    client = OllamaClient(settings.llm_base_url(), settings.llm_model())
    stats = {}
    for npc_id in sorted(n for n in world.npcs if world.npcs[n].alive):
        result = llm_agent.act(world, npc_id, client, stats=stats)
        assert result.ok, f"{npc_id}: {result.reason}"
    assert stats.get("errors", 0) == 0
