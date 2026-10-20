# Week 16 A and D: engine interface

Villagers may submit these intents. The player retains the existing actions.
Every successful action is recorded; a rejection changes no world facts or events.

`gesture` takes `text`, a single line of at most 80 characters. A deterministic
word check rejects physical result verbs, item ids/names, and absent people's
ids/names. Gestures have talk's witnesses and enter their memories and the feeds.
The web view uses its existing small interaction animation cue.

`make` takes `name`, `params`, `needs`, and `does`. Names are unique across makers,
use lowercase letters, digits and underscores, and cannot name a built-in action.
`params` is a subset of `item`, `person`, `exit`. The optional `use` object supplies
exactly those parameters for an immediate invocation. Without `use`, only the
shape is checked; creating a definition does not require its preconditions yet.

| Need | Parameter | Check |
| --- | --- | --- |
| `holds_item` | `item` | Actor holds it |
| `item_here` | `item` | Ground item is visible to actor here |
| `item_hidden_here` | `item` | Hidden ground item is here |
| `person_here` | `person` | Living person is here |
| `at_place:<location id>` | none | Actor is at that location |

| Effect | Parameter | Result |
| --- | --- | --- |
| `put_item_here` | `item` | Held item goes on the ground, visible |
| `hide_item_here` | `item` | Held item goes on the ground, known only to actor |
| `reveal_hidden_here` | none | All hidden items here become known to everyone present |
| `take_item_here` | `item` | Visible ground item becomes held |
| `move_self_exit` | `exit` | Actor walks through an adjacent exit |

Needs are checked before the steps. Steps execute in order on a deep copy.
Each step and the final copy must preserve the item/person sets, other people's
locations, life, custody, secrets, clock, RNG, log, and every undeclared field.
Ordinary placement, custody and exit checks also apply. Only the verified engine
changes are committed, together with one event containing the resolved steps.

A later intent uses the made name as `action`, with its declared argument fields.
It runs the stored definition through the same checks. Only its maker can use it.
Definitions are rebuilt from `make` events when loading, and replay submits the
saved proposals through the engine again. The model never supplies state patches.

Hidden items retain `hidden: true` and a sorted `known_by` list after a reveal.
This gives knowledge to the people present then, without exposing the item to
later arrivals. Taking clears hiding; hiding again resets knowledge to the hider.
A hiding step has no other witnesses. Multi-step events keep separate audiences
for each step, so a witnessed walk does not expose an earlier hidden item.
Past observations and spoken words remain memories of what was seen or heard.

Unknown villager actions still reject normally. Their `{tick, actor, action,
intent}` records go in `wishes` in the run's JSON sidecar, outside world state and
the event log. `whisperwick wishes DB` prints counts in action-name order.

Legacy item saves omit unused hiding fields. The original event snapshot stays
unchanged. Live Victor benchmark runs and a human play session remain to be done.
