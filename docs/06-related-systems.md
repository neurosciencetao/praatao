# Related systems & analogues

Praatao sits at the intersection of **software onboarding**, **ITS**, and **phonetics tooling**. None of the systems below are Praat-specific; they inform architecture and UX.

## Desktop overlay coaches

| System | What it does | Relevance |
|--------|--------------|-----------|
| **Lekhini** | Cross-platform annotation overlay; click-through; per-display windows | Overlay engineering reference |
| **Visor** | Goal → screenshot → LLM → step overlays | “Ask for help” mode prototype pattern |
| **PolterGuide** | Transparent overlay + ghost cursor agent | Demo of agentic guidance; caution: autonomy vs pedagogy |
| **Beacon** | Describe task → plan → highlight UI | Similar product fantasy; vision-heavy |
| **UIPin** | Pin annotations + UIA element capture | Good for **authoring** Praatao tips (capture button names) |

## In-app onboarding (different architecture)

Product tours (Intro.js, Shepherd.js, Appcues, Pendo) assume **DOM access**. Praat has no DOM → those libraries don’t apply directly, but their **content patterns** do:

- Spotlight + tooltip
- Progress stepper
- “Don’t show again”
- Role-based tours

## Phonetics / pronunciation software

| System | Relation to Praat |
|--------|-------------------|
| Praat itself | Target |
| BetterAccent Tutor (historical refs) | Specialized intonation UI; papers compare/combine with Praat |
| Various commercial CAPT systems | Closed UIs; Praatao instead teaches the open research tool |
| Web spectrogram toys | Lower fidelity; good for pre-lab warmup, not replacement |

**Strategic position:** Praatao keeps students in the **same tool researchers use**, reducing transfer gap from “toy trainer” to Praat.

## ITS & authoring frameworks

- **GIFT** (Generalized Intelligent Framework for Tutoring) — military/education ITS research; overkill for v1 but useful vocabulary for grant narratives
- Classic tutors (Andes, AutoTutor) — dialogue-heavy; Praatao is initially **GUI-procedure tutoring**

## Design patterns to borrow

1. **Click-through overlay** with hover-to-interact tips  
2. **Authoring via annotate-on-screenshot** (UIPin-like) → export YAML anchors  
3. **Deterministic tours first**, AI assist second  
4. **Side panel + optional spotlight** hybrid for reliability  
5. **Hint fading** (ITS): fewer tips as competence grows  

## Competitive / complementary landscape

| Approach | Complements Praatao? |
|----------|----------------------|
| Better PDF/video tutorials | Yes — Praatao links out for deep theory |
| Course LMS modules | Yes — embed lesson pack IDs |
| Fork Praat with simplified UI | Competing vision; higher maintenance |
| Pure Parselmouth Jupyter course | Competing for some labs; poor for GUI skills |

Praatao’s unique claim: **situated orientation on the real Praat GUI**.
