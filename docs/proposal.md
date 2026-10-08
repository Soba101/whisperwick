# Whisperwick: proposal (short version)

## Decisions
| Topic | Decision |
|---|---|
| Purpose | Research experiment, packaged as a portfolio piece |
| Time | 6 weeks, side-project pace, hard stop |
| Build order | Vertical slice first: 5 NPCs + murder scenario by week 2 |
| Agent runtime | Direct OpenAI-compatible calls with JSON-schema outputs (no Hermes in v0.1) |
| Models | Local only. ~30B quantised for everything first; ~8B tier added in week 5 |
| Evaluation | Ablations + LLM judge + blind human ranking |
| Player | Scripted perturbations in v0.1; interactive in v0.2 |

## Evaluation conditions (same 5 seeds each)
- **Full**: everything on.
- **No beliefs**: belief table removed.
- **No memory**: memory stream removed.
- **Scripted**: hand-written investigation (the ceiling).

**GO if** Full beats No-beliefs on coherence rank and belief accuracy in at least 4 of 5 seeds,
with 100% of beliefs having a valid source.

## Prior art
- [Generative Agents](https://arxiv.org/abs/2304.03442): memory, reflection, planning (Stanford 2023).
- [Project Sid](https://arxiv.org/abs/2411.00114): 1,000+ agents in Minecraft.
- [AI Town](https://github.com/a16z-infra/ai-town): open-source starter kit.
- [Are LLM Agents Behaviorally Coherent?](https://arxiv.org/html/2509.03736v1): small models are too agreeable.
- Skyrim mods: Mantella, CHIM, SkyrimNet. They do player dialogue and memory, but not belief sources.
