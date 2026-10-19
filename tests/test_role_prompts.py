"""Role identity stays private unless authored memory or visible trade explains it."""

import json

import pytest

from whisperwick import act_prompt, interview, thought_prompt
from whisperwick.memory import Memories, seed_evidence
from whisperwick.roles import ROLE_IDS, apply_role, load_role
from whisperwick.scenario import build_world, load_scenario


@pytest.mark.parametrize("role_id", ROLE_IDS)
@pytest.mark.parametrize("distinct_title", [False, True])
def test_role_titles_never_feed_villager_prompts(monkeypatch, role_id, distinct_title):
    role = load_role(role_id)
    if distinct_title:
        # The peddler's real title equals its public trade. A distinct title checks
        # the private field's isolation without forbidding that visible fact.
        role.player.title = f"Private identity for {role_id}"
    monkeypatch.setattr("whisperwick.roles.load_role", lambda _: role)
    sc = apply_role(load_scenario("scenarios/murder_of_the_mayor.yaml"), role_id)
    world = build_world(sc)
    memories = Memories()
    seed_evidence(memories, sc.evidence, world.clock.tick)
    try:
        for npc in world.npcs.values():
            if npc.id == "player" or not npc.alive:
                continue
            # Put the player in front of every villager to exercise people_label.
            world.npcs["player"].location = npc.location
            stream = memories[npc.id]
            shown = {f"m{i}": m for i, m in enumerate(stream.memories)}
            prompts = [
                act_prompt.build_messages(world, npc.id,
                                          evidence=[m.text for m in stream.memories]),
                thought_prompt.messages(world, npc.id, sc.personality.get(npc.id),
                                        shown, None),
                interview.messages(world, npc.id, stream),
            ]
            for prompt in prompts:
                text = json.dumps(prompt)
                assert sc.private_fact not in text
                if distinct_title or (
                    role.player.title != role.player.occupation
                    and not (role.memory and npc.id == role.memory.npc)
                ):
                    assert role.player.title not in text
                if not distinct_title and role.memory and npc.id == role.memory.npc:
                    assert role.memory.text in text
    finally:
        world.log.db.close()
