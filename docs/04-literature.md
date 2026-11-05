# Literature & evidence notes

Collected for Praatao concept development (2026-08). Prefer reading abstracts/methods, not titles alone.  
Links use DOI where available: `https://doi.org/{doi}`.

## Takeaways for Praatao

1. **Praat is widely used in teaching**, especially pronunciation and phonetics labs, but instructors repeatedly report **usability friction** (file formats, interpreting contours, multi-step GUI).
2. **Visual acoustic feedback helps** when scaffolding is present; raw Praat displays can overwhelm learners (classic concern in CALL/pronunciation tech reviews).
3. **Parselmouth** legitimizes a Python ecosystem beside Praat—useful for Praatao’s content/testing track, not as a GUI overlay.
4. **Coach marks / instructional overlays** are studied in HCI (mostly mobile/web); desktop-on-desktop coaching is rarer in academic literature but common in industry (onboarding SDKs) and hackathon overlay agents.
5. **Intelligent Tutoring Systems (ITS)** supply a conceptual frame (domain / student / pedagogical / interface modules)—Praatao v1 can be a lightweight pedagogical+interface layer without full student modeling.

## Core technical / tooling papers

### Jadoul, Thompson, & de Boer (2018) — Parselmouth

- **APA:** Jadoul, Y., Thompson, B., & de Boer, B. (2018). Introducing Parselmouth: A Python interface to Praat. *Journal of Phonetics, 71*, 1–15. https://doi.org/10.1016/j.wocn.2018.07.001
- **Why it matters:** Official-quality bridge to Praat algorithms in Python; examples for visualization, batch processing, PsychoPy integration.
- **Praatao use:** Lesson media generation, automated checks, research demos—not live GUI sensing.
- **Access:** Publisher / institutional; manuscript often available from authors’ pages.

### Boersma & Weenink — Praat itself

- Cite the version used in any empirical evaluation of Praatao.
- Manual FAQ: how to cite Praat — https://www.fon.hum.uva.nl/praat/manual/FAQ__How_to_cite_Praat.html

## Praat in teaching & pronunciation

### Osatananda & Thinchan (2021)

- Osatananda, V., & Thinchan, W. (2021). Using Praat for English pronunciation self-practice outside the classroom: Strengths, weaknesses, and its application. (ERIC PDF: https://files.eric.ed.gov/fulltext/EJ1310704.pdf)
- **Methods angle:** Out-of-class Praat practice; learners compare waveforms/contours to models.
- **Design implication:** Reduce procedural friction (file conversion, multi-step compare). Praatao can scaffold exactly these procedures.

### Setter & Jenkins (2005) — pronunciation teaching survey

- Setter, J., & Jenkins, J. (2005). State-of-the-art review article. *Language Teaching, 38*(1), 1–17. https://doi.org/10.1017/S026144480500251X
- Broad review; discusses technology potential/limits in pronunciation teaching—useful background when pitching Praatao to applied linguistics audiences.

### Classroom / EFL Praat studies (sample from scite search)

These are useful for **needs evidence** and related-work tables; quality varies—read methods carefully.

| Theme | Example titles (verify DOI before citing in papers) |
|-------|-----------------------------------------------------|
| Praat for monophthongs / diphthongs / intonation in EFL | “Using PRAAT in Teaching the Monophthongs…”, “Enhancing EFL Learners Diphthong Pronunciation…”, “Using Praat to Develop … Intonation Production” |
| Teacher training / phonetics courses | “Teaching teachers phonetics…”, “Comparing Instructional Reinforcements in Phonetics Pedagogy” |
| Vocational / curriculum reform | “Empirical Study on English Phonetic Teaching Reform Based on Praat…” |
| Evaluation tooling | “Evaluating English Teachers’ Pronunciation Skills … Using Praat…” |

When writing academically, re-fetch each item via scite/DOI and check `editorialNotices`.

### Brett (2004) — Praat complexity for learners (cited in secondary sources)

Secondary literature (e.g. discussions of BetterAccent Tutor + Praat) cites Brett’s ReCALL work concluding that **formant plot interpretation via Praat can be too complex for learners** without additional structure. Track down the primary ReCALL article before formal citation:

- Search: Brett + Praat + ReCALL + vowels

**Praatao implication:** Expandable explanations should teach *interpretation*, not only button locations.

## Pedagogical / HCI frames

### Coach marks

- Noriega, P., Carvalho, D. P. de S. R. P., & Correia, I. M. T. (2019). Effectiveness of Coach Marks or Instructional Overlay in Smartphone Apps Interfaces. In HCI volume (Springer). https://doi.org/10.1007/978-3-030-20227-9_7
- **Transfer:** Mobile coach-mark findings (attention, annoyance, retention) inform tip frequency and dismissibility on desktop overlays.

### Intelligent Tutoring Systems (conceptual)

Classic ITS components (domain, student, pedagogical, interface) appear across surveys, e.g. overview discussions in educational AI literature (Graesser et al., chapter-length reviews). For Praatao:

| ITS module | Praatao v1 mapping |
|------------|--------------------|
| Domain | Phonetics + Praat procedures knowledge base |
| Interface | Overlay + side panel |
| Pedagogical | Lesson graphs / next-step rules |
| Student | Optional later (skill estimates, hint fading) |

### Tutorial usability

Scite hits such as “Student preference for tutorial design: a usability study” and “Evaluating accessibility features of tutorial creation software” are relevant when choosing **animated overlay vs video vs static PDF** for labs—retrieve full texts before relying on them.

## Corpus phonetics / advanced users

- “Corpus Phonetics Tutorial” style materials show another Praatao lane: guiding researchers from GUI toward reproducible pipelines (Praat scripts / Parselmouth)—secondary persona (P1/P3).

## Gaps (research opportunities)

| Gap | Opportunity |
|-----|-------------|
| Few systems overlay **guidance on live Praat** | Praatao as design-based research / CHI + phonetics education |
| Limited controlled studies of **situated vs separate** Praat tutorials | Lab RCT: worksheet-only vs Praatao overlay |
| Accessibility of Praat GUI for screen-reader users | Separate track; UIA improvements vs companion narration |

## Reading list priority

1. Jadoul et al. (2018) Parselmouth  
2. Official Praat Intro + Scripting 6.9 & 8  
3. Osatananda & Thinchan (2021) + one EFL Praat classroom paper in your target language context  
4. Noriega et al. (2019) coach marks  
5. One ITS overview chapter (Graesser or similar)  
6. Styler guidebook (practical, not a paper)—see `05-learning-resources.md`

## References (APA)

Boersma, P., & Weenink, D. (n.d.). *Praat: doing phonetics by computer* [Computer program]. https://praat.org/

Jadoul, Y., Thompson, B., & de Boer, B. (2018). Introducing Parselmouth: A Python interface to Praat. *Journal of Phonetics, 71*, 1–15. https://doi.org/10.1016/j.wocn.2018.07.001

Noriega, P., Carvalho, D. P. de S. R. P., & Correia, I. M. T. (2019). Effectiveness of coach marks or instructional overlay in smartphone apps interfaces. In *Human-Computer Interaction* (pp. 68–78). Springer. https://doi.org/10.1007/978-3-030-20227-9_7

Osatananda, V., & Thinchan, W. (2021). Using Praat for English pronunciation self-practice outside the classroom: Strengths, weaknesses, and its application. https://files.eric.ed.gov/fulltext/EJ1310704.pdf

Setter, J., & Jenkins, J. (2005). State-of-the-art review article. *Language Teaching, 38*(1), 1–17. https://doi.org/10.1017/S026144480500251X
