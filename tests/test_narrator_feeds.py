"""Both real feed renderers use scene metadata, even when the words are identical."""

import shutil
import subprocess
from pathlib import Path

import pytest
from test_web_notebook import DOM

from whisperwick.web_js import JS
from whisperwick.web_style import CSS


@pytest.mark.parametrize("three_d", [False, True])
def test_scene_flags_style_the_correct_row_without_parsing(three_d):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is needed to exercise feed rendering")
    # The 3D panel only needs a few extra DOM operations, not a WebGL scene.
    setup = DOM + """
Element.prototype.prepend = function(x) { this.children.unshift(x); };
Element.prototype.append = Element.prototype.appendChild;
const feed = get('feed');
const line = 'Identical words for a scene and an ordinary line';
const state = {feed:[line,line], feed_total:2,
  feed_flags:[{scene:true},{scene:false}], you:{place:{name:'Market'}}, known:null};
"""
    if three_d:
        source = Path("whisperwick/web3d/panels.js").read_text()
        source = source.replace("import {clothing} from './palette.js';", "const clothing=()=>0;")
        # Live talk (#106) draws below the feed; this check is only about feed rows.
        source = source.replace("import {drawLiveTalk} from './live-talk.js';",
                                "const drawLiveTalk=()=>{};")
        source = source.replace("export class Panels", "class Panels")
        render = "const panels=new Panels(); panels.draw(state); panels.draw(state);"
        style = Path("whisperwick/web3d/style.css").read_text()
    else:
        source, render, style = JS, "drawFeed(state); drawFeed(state);", CSS
    # Keep the harness's lexical names separate from the actual renderer.
    script = setup + """
const create = document.createElement;
document.createElement = tag => {
  const row = create(tag); row.classList.add = name => row.classes.add(name); return row;
};
{
""" + source + render + """
}
assert.equal(feed.children.length,2);
assert.equal(feed.children[0].classes.has('scene'),true);
assert.equal(feed.children[1].classes.has('scene'),false);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "#feed .scene { font-style:italic; }" in style
