"""Drive the shared dialog without a browser or a network connection."""

from importlib.resources import files

import pytest
from test_ending_ui import DIALOG, run
from test_web_notebook import DOM


@pytest.mark.parametrize("page", ["2d", "3d"])
def test_feedback_dialog_sends_private_request_and_thanks(page):
    source = files("whisperwick").joinpath("web3d/feedback.js").read_text()
    source = source.replace("export function", "function")
    run(DOM + DIALOG + source + f"""
document.createTextNode = text => ({{textContent:text}});
const open = setupFeedback('{page}');
const dialog = document.body.children.at(-1), form = dialog.children[1];
// form.children[0] is the report hint (2026-10-21), hidden in plain feedback.
const rating = form.children[1].children[0], tags = form.children[2];
const textBox = form.children[3].children[0], status = form.children[4];
const send = form.children[5], cancel = form.children[6];
assert.equal(textBox.maxLength,2000);
assert.deepEqual(tags.children.slice(1).map(n => n.children[0].value),
  ['confusing','too slow','villagers ignored me','bug','loved it']);
let resets=0; form.reset=() => resets++;
tags.querySelectorAll=() => [tags.children[4].children[0]];
open(); assert.equal(dialog.open,true);
rating.value='4'; textBox.value='Private feedback';
(async () => {{
  await form.onsubmit({{preventDefault() {{}}}});
  assert.equal(requests.length,1);
  assert.equal(requests[0].path,'/feedback');
  assert.deepEqual(JSON.parse(requests[0].options.body),
    {{page:'{page}',rating:4,tags:['bug'],text:'Private feedback',kind:'general'}});
  assert.equal(status.textContent,'Thanks, saved.');
  assert.equal(send.disabled,true); assert.equal(resets,1);
  cancel.onclick(); assert.equal(dialog.open,false);
  open(); assert.equal(send.disabled,false);
  cancel.onclick(); assert.equal(requests.length,1);
}})().catch(e => {{ console.error(e); process.exitCode=1; }});
""")
