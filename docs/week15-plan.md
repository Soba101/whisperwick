# Week 15 plan (picked 2026-10-19: A and B): narrator and faster talk

Rules carry over: the world is physics only; villagers decide; no director, no hints in prompts.
Both pieces are player-side presentation. Neither changes what any villager is told or decides.
C (measure the new game, #109) runs on the PC when it is free; no code needed.

## A. Narrator, engine-written (#108)
On arrival in a place and on Look around, the player's feed gets one short scene line written by code
from what is really there: the place, the time of day, who is here and what they last did, items on the
ground, a body if any. Fixed templates with a few seeded variants per place, so it reads like prose:
"Evening at the Inn. Alice wipes the bar. A cup of tea sits on the counter. The door to the Market is open."
- Only facts the look itself returns (no hidden items, nobody out of sight).
- Shown in the 2D and 3D feeds, styled apart from dialogue (italic).
- Not an event, never in any prompt.
- Check: tests that every sentence maps to a fact in the look result; a test on generated crimes.

## B. Faster, livelier talk (#106)
1. **Streamed replies (display only).** While a villager's reply is being generated, the page shows
   "Alice is speaking..." and the words of the message as they arrive. The engine still applies only the
   final, validated intent. If the final intent is rejected or is not talk, the partial text is removed.
   The model call, prompt, sampling and schema stay exactly the same.
2. **Voice starts on the first sentence** in voice mode (#101), instead of after the whole reply.
3. **Better on-device voices:** Kokoro (kokoro-js, in the browser, WebGPU or WASM, cached after the first
   download) as an option next to the browser voices, one fixed voice per villager.
- Not in this week: shorter villager replies (that changes the prompt or the message limit; needs its own
  rules check, see week 12 option C).
- Check: a test that the event log of a stub run is identical with streaming on and off; latency to first
  visible word measured on 20 live turns before and after.

## Not in this week
- C runs separately. Open world (#102). The backlog (#108-#117 minus this week).
