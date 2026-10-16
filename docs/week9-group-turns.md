# Group turns implementation

Enable with `WHISPERWICK_GROUP_TURNS=on`. The default is `off`; values follow the
existing `on`/`off` settings convention. Run sidecars record the boolean switch.
Model screen replay refuses sources with the switch on. Older sidecars mean off.

The engine and scheduler are unchanged. The run loop owns an optional exchange
queue. Player input still runs first, so a player can interrupt before a queued
line. Queued lines then run before the scheduler builds its due list. A small
player-event hook lets the queue hear interruptions without rereading the event
log every minute.

Pair history records directed own-turn talks only. Starting an exchange clears
both directions for that pair, including when its first line is later rejected.
Both speakers must speak in their own turns again to qualify. Other pairs keep
their independent history. Each queued line records the accepted intent in the
normal repeat history, but does not use the own-turn repeat guard to override
the engine's talk checks.

The prompt reads the last 20 shared events in event-id order from the event log.
An actor counts as a participant; everyone else must be in that event's witnesses.
It never reads memory text. The existing event description accepts a neutral
viewer; moves then say where the actor walked from and to rather than choosing
one speaker's view. Personalities use the existing character text helper.

Replies must match the one-to-three string schema. Blank lines are removed before
code assigns the alternating speakers. A malformed reply or call error records a
failed exchange attempt and falls back to an own turn in the same minute. A first
line rejected by the engine also permits that own turn; it counts as a dropped
exchange, rather than a bad reply. Later rejection cancels the remaining lines.
Speakers stay suppressed through a successful final line's minute, so the answer
is an own turn next minute, including after a one- or two-line exchange.

Statistics count valid replies as `exchanges`, accepted lines as `exchange_lines`,
bad replies as `exchange_failed`, and canceled valid exchanges as `exchange_dropped`.
Every exchange request also counts in `calls` and `turn_reasons.exchange`. Errors
and engine rejections enter the existing error and rejection counters. Exchange
lines carry no claims. Memories, scheduler notifications, and display callbacks
receive each accepted line immediately.

Each exchange attempt produces one final agent-log record. `lines` counts the
nonblank lines written, `logged` and `event_ids` count accepted engine events.
Invalid replies have zero lines and `dropped: "bad reply"`. If a run ends with
lines pending, the record says `dropped: "run ended"` and counts as dropped. This
keeps the saved log consistent with what actually ran, without flushing future
lines into a stopped game.
