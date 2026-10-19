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

### B implementation (#106)
- Web play with llama-server streams individual villager act replies by default.
  `WHISPERWICK_STREAM_TALK=off` disables it. Ollama, thinking, shared conversation calls,
  and non-web play keep their existing request path.
- Both pages show a temporary line below the feed; only villagers at the player's place
  can appear. The completed response uses the existing intent parser and engine checks.
- 3D voice mode reads the first complete live sentence, then the committed remainder.
  A preview sequence links the two so rejected drafts cannot suppress a later reply.
- The 3D voice engine menu offers Browser voices and Kokoro (on device). Kokoro loads only
  when selected, using `kokoro-js@1.2.1` from jsDelivr and
  `onnx-community/Kokoro-82M-v1.0-ONNX` with q8 weights. It tries WebGPU then WASM,
  reports download progress, and uses the browser's model cache. Villager IDs choose fixed
  voices. Loading or playback errors fall back to browser speech. The 2D page stays offline.
- Automated checks cover the partial JSON scanner, streamed/non-streamed request and intent
  equality, identical stub-run event logs, visibility, cleanup, sentence handoff, and mocked
  Kokoro loading, fallback and cancellation. The fake server has memory and HTTP transports.
- Still to measure on the model PC: first visible word over 20 live turns before/after.
  Real browser audio, model downloads, GPU/WASM execution and cache reuse need a live check.
