# Docs index

Start here after reading the root [README](../README.md).

## Concept & research

1. [00 — Concept](00-concept.md) — what Praatao is  
2. [01 — Architecture](01-architecture.md) — sense / decide / render  
3. [02 — Tech stack](02-tech-stack.md) — languages & frameworks  
4. [03 — Praat integration](03-praat-integration.md) — `--send`, probes, GUI facts  
5. [04 — Literature](04-literature.md) — papers & evidence  
6. [05 — Learning resources](05-learning-resources.md) — tutorials to study  
7. [06 — Related systems](06-related-systems.md) — overlay analogues  
8. [07 — Roadmap](07-roadmap.md) — action steps  
9. [08 — Community pain points](08-community-pain-points.md) — web/teaching gotchas used in v0 tips  

## v1 decisions (read these first if you are new)

10. [09 — "Python for Praat": does the package exist?](09-python-for-praat.md) — the package survey, and why Parselmouth is not the answer here  
11. [10 — Sensing strategy](10-sensing-strategy.md) — **ADR-004**: UIA vs. screen coordinates vs. vision, with measured evidence  
12. [12 — v1 architecture](12-architecture-v1.md) — the system that is actually built, module by module  
13. [13 — Content guide](13-content-guide.md) — how to write a knowledge entry or a lesson pack  
14. [CONTRACTS.md](CONTRACTS.md) — module interfaces, and the verified Praat scripting API  

## The board and the notes of 2026-11-05

15. [architecture-board.html](architecture-board.html) — **the architecture board**: one page that shows how the data flows (open it in a browser)  
16. [15 — Performance](15-performance.md) — what the hover costs, before and after the optimisation  
17. [16 — The card's design](16-card-design.md) — what the hover card looked like, what was wrong with it, and what the best tools do  
18. [17 — Parselmouth checks](17-parselmouth-checks.md) — every number in the knowledge base, recomputed with Praat's own algorithms  

## Working notes

19. [pain-points.md](pain-points.md) — your confusion backlog (fill in)  
20. [references.bib](references.bib) — BibTeX  

## Code

* [`../praatao/`](../praatao/) — the v1 package (`sensors` / `tutor` / `ui`)  
* [`../run.py`](../run.py) — entry point  
* [`../prototypes/v0/`](../prototypes/v0/) — the earlier v0 coach prototype (Tk, relative-rect highlights)  
* [`../prototypes/v1/experiments/`](../prototypes/v1/experiments/) — the measurements behind ADR-004  
