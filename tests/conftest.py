"""Week 16 actions are off by default (#122); their own tests switch them on."""

import pytest

from whisperwick import made_prompt

WEEK16_TESTS = {"test_gestures", "test_made_actions", "test_made_checks", "test_made_replay",
                "test_hidden_items", "test_wishes", "test_act_prompt"}


@pytest.fixture(autouse=True)
def week16_actions(request):
    made_prompt.ENABLED = request.module.__name__.split(".")[-1] in WEEK16_TESTS
    yield
    made_prompt.ENABLED = False
