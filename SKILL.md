---
name: review-ubc-dissertation-pdf
description: Review a UBC master's thesis or doctoral dissertation PDF for final post-defence submission without editing the source. Use for lightweight screening, strict final preflight, citation existence and metadata verification, page-margin or formula-overflow detection, cIRcle readiness, UBC formatting compliance, page-by-page layout triage, organization checks, or regression review of a revised thesis or dissertation PDF.
---

# Review UBC Thesis or Dissertation PDF

Audit the PDF read-only by default. Support both master's theses and doctoral dissertations at UBC Vancouver and UBC Okanagan. Treat current UBC Graduate and Postdoctoral Studies pages as authoritative; distinguish explicit requirements from recommendations and editorial preferences.

Resolve every bundled path from the directory containing this `SKILL.md`; refer to that directory as `<skill-dir>`. Do not assume the user's working directory is the skill directory.

## Choose the mode

- Use `screen` by default: run whole-file automation, inspect compact contact sheets, then open only anomalous or high-risk pages.
- Use `final` when the user asks for strict, exhaustive, submission-ready, or GO/NO-GO review: apply the full UBC checklist, complete the citation-verification workflow, and inspect every contact sheet plus every required detail page.
- Use `regression` when a prior PDF or issue list exists: compare versions and recheck changed pages, open issues, and submission-critical pages.
- Do not perform full prose proofreading or fact-check the thesis or dissertation's substantive claims unless explicitly requested. Citation existence and bibliographic metadata verification are part of `final` mode and any review that explicitly includes citations.

## Preserve scope and evidence

1. Resolve the exact candidate PDF and output directory. Record its SHA-256 before reviewing. If the user does not choose an output directory, use `<skill-dir>/.review-runs/<candidate-stem>-<short-sha>/`; this directory is ignored by the skill repository and must never be committed.
2. Do not modify, re-export, rename, or optimize the source PDF unless explicitly authorized.
3. Identify pages as both one-based PDF page numbers and visible printed labels when available.
4. Mark uncertain automated detections as `QUERY`; never present heuristics as confirmed defects.
5. Keep review artifacts outside thesis or dissertation source directories when the user sets that boundary.

## Run the token-efficient workflow

### 1. Establish the rule baseline

Read [references/ubc-requirements.md](references/ubc-requirements.md) before UBC compliance or final review. In `final` mode, revisit its official links when the snapshot is over 30 days old or a requirement may have changed.

Find `author-info.yml` in the review directory. If absent, copy [`<skill-dir>/assets/author-info.template.yml`](assets/author-info.template.yml) there as `author-info.yml`. Fill only machine-verifiable fields such as candidate path and SHA-256; leave unknown author facts as `null`.

Before issuing findings, push one concise batch of questions for all missing submission-critical fields. Use structured user input when available; otherwise use a numbered list. Group questions into identity/degree/title, final committee, revision approval/style guide, supplementary files/embargo, GenAI, and publication/copyright/privacy. Do not request a student number, credentials, or information already confirmed in the file. Continue independent checks while awaiting answers, but retain unresolved fields as `QUERY`.

For each missing group, show any value extracted from the PDF and ask the author to **confirm or correct it**. Omit fully answered groups. Use this question order:

1. Workday full name; filename family/given names; exact title; master's or doctoral level; degree/program/campus; graduation month/year; copyright year.
2. Final committee names and roles. For a doctorate, confirm both University Examiners, the External Examiner inclusion choice, and exclusion of the defence Chair. For a master's thesis, confirm all examining and supervisory committee members and label any extra defence examiner as `Additional Examiner`; do not use the doctoral-only `University Examiner` role.
3. Whether all minor revisions are complete, who approved them and when, and the approved style guide.
4. Supplementary files, embargo request/approval, and whether the cIRcle abstract exactly matches the PDF abstract.
5. GenAI use and whether the supervisor approved the Preface disclosure.
6. Published/co-authored material, contribution statements, copyright permissions, and removal of signatures/personal information/ethics certificates.

Write confirmed answers into `author-info.yml`. Do not infer a `yes` from silence. Ask a focused follow-up only for fields that remain ambiguous; unresolved submission-critical fields prevent `GO`.

### 2. Run deterministic preflight

Use the bundled PDF-capable Python runtime when available:

```bash
python3 "<skill-dir>/scripts/pdf_preflight.py" candidate.pdf --json round/preflight.json
```

For a final filename check, add `--final-name`. For regression review, add `--compare previous.pdf`. In `final` mode, use a stricter raster geometry pass:

```bash
python3 "<skill-dir>/scripts/pdf_preflight.py" candidate.pdf --json round/preflight.json --final-name --geometry-dpi 144 --geometry-tolerance 0.5
```

The script emits one compact summary line and writes details without copying thesis or dissertation text into the report.

Treat script results as leads. Confirm blockers visually or from the PDF object structure before reporting them.

The geometry pass rasterizes each page locally and measures actual visible ink against UBC minimum margins after masking only a detected printed page number. This catches rendered formula glyphs, text, images, and table/figure strokes while avoiding false alarms from vector paths hidden by PDF clipping. It allows only the configured antialiasing tolerance and treats detected overflow as `QUERY` until visually confirmed. Never skip geometry or lower the final-mode settings in `final` mode.

### 3. Inspect progressively

Create low-resolution contact sheets for all pages and high-resolution renders only for selected pages:

```bash
python3 "<skill-dir>/scripts/render_pdf_review.py" candidate.pdf --out round/visual --findings round/preflight.json --pages 1-15 --margin-overlay
```

For every `margin-overflow` page, inspect both the original detail render and the margin-overlay render at 180 DPI or higher; use 240 DPI for ambiguous formulas, glyphs, strokes, tables, or figures. Promote a finding to `BLOCKER` only when visible thesis or dissertation content crosses the red UBC minimum-body boundary. A page number may sit outside that body boundary only if it remains at least 0.5 inch from the page edge.

In `final` mode, also inspect at 240 DPI at least one unflagged example of every equation/table/figure layout family and every unusually wide equation or full-width object. This is the human false-negative check; record it in `author-info.yml`.

Inspect at high resolution:

- title, committee, abstract, lay summary, preface, and all contents/list pages;
- first body page, every chapter opener, bibliography opener, and appendix opener;
- landscape, rotated, non-Letter, blank, image-only, low-text, or otherwise flagged pages;
- representative instances of each table, figure, equation, footnote, and heading layout;
- every page with a suspected clipping, overlap, margin, legibility, or pagination defect.

In `final` mode, view every contact sheet. Escalate any ambiguous thumbnail to a detail render. Do not claim that extraction proves visual correctness.

#### Audit figure lettering at final placement size

Review figure text in the compiled thesis or dissertation PDF, not only in the standalone source image. The UBC reference states that text in tables and figures should be at least 2 mm high. Apply that threshold to the visible result after `\includegraphics` scaling; a source-code point size, PDF bounding box, or apparently sharp vector file does not by itself establish compliance. At 240 DPI, 2 mm is about 19 rendered pixels, which is useful for screening but still requires visual or geometric confirmation. Treat a merely suspected undersized label as `QUERY`, and distinguish current official requirements from recommendations before assigning severity. Unreadable or clipped content is a `BLOCKER` regardless of nominal font size.

Inspect axis titles; numeric and categorical ticks, including superscripts; legend titles, labels, and numeric keys; facet or strip titles; and panel annotations separately because one can fail while the rest is acceptable.

Before recommending a fix, locate both the figure's source script and its LaTeX placement, and record the output filename and `\includegraphics` width. Use this triage:

1. If all lettering is uniformly too small and the page has safe unused space, increasing the LaTeX placement size may be sufficient. Recompile before deciding; do not enlarge through the minimum margins or into the caption.
2. If only ticks, legends, facet titles, superscripts, or one dense panel are too small, the source plot needs targeted font or layout changes. Do not enlarge already-acceptable elements unnecessarily.
3. LaTeX scaling does not repair clipping, overlapping ticks, truncated facets, or baked-in crowding. Fix these in the source by reducing tick density, enlarging the relevant panel or row, or shortening/wrapping labels. Captions may define abbreviations but cannot replace readable embedded text. For raster figures, also check effective resolution after final scaling.

For a planning or regression report, state explicitly which figures can be repaired by LaTeX scaling alone and which require source-code regeneration. If source edits are authorized, generate candidates without replacing approved originals until the user accepts them.

After any figure revision, regenerate the compiled PDF and inspect the modified page and its neighbours at 240 DPI or higher. Confirm final-size lettering, overlaps/clipping, orientation, margins, captions, numbering, nearby floats, and raster sharpness.

### 4. Check organization without loading the whole thesis

Extract only the table of contents, heading/caption index, front matter, chapter openings and closings, and targeted passages first. Check:

- required component order and clear heading hierarchy;
- TOC/list entries against actual headings, captions, numbers, and pages;
- chapter-level purpose, transitions, synthesis, and conclusion coverage;
- numbering, terminology, abbreviations, units, cross-references, and bibliography consistency.

Load full chapter text only when these signals expose a problem or the user requests prose-level review.

### 5. Verify citations against online records

In `final` mode, or whenever citation/reference checking is requested, read and follow [references/citation-verification.md](references/citation-verification.md). It defines the complete audit set, authoritative-source hierarchy, preprint/version handling, classifications, artifact schema, and location-specific recommendations. Do not sample, rely on DOI syntax alone, or silently edit `.tex`/`.bib`. Keep the audit artifact in the ignored per-run directory.

### 6. Report concise, auditable findings

Use one row per issue:

| ID | Severity | PDF page / label | Evidence or rule | Finding | Minimal action |
|---|---|---|---|---|---|

Use these severities:

- `BLOCKER`: explicit submission requirement, confirmed content beyond a minimum margin, unreadable content, invalid PDF, or serious privacy/copyright issue.
- `MAJOR`: material navigation, organization, consistency, or legibility defect.
- `MINOR`: polish issue unlikely to block acceptance.
- `QUERY`: requires author, supervisor, program, or visual confirmation.

Lead with counts and unresolved `BLOCKER`/`MAJOR` items. Avoid narrating passes page by page. Give `GO` only when no confirmed blockers or majors remain, all submission-critical `author-info.yml` and `QUERY` fields are resolved, required human sign-offs in the UBC reference are complete, every geometry flag is visually closed, every paper citation is `VERIFIED`, no obsolete or unintended duplicate-version citation remains, and the final candidate has passed a fresh preflight. If live online verification was unavailable or incomplete, state that limitation and do not issue `GO` for a `final` review.

#### Final response format

Return ordinary Markdown only. Never expose host-specific colon-prefixed actions, file-citation commands, XML-like directives, or other internal UI syntax. Keep author confirmations as a normal numbered list. If optional next steps are useful, present them as ordinary Markdown bullets or sentences.

## Control context and token use

- Never paste the full extracted PDF text, full page-image set, or full JSON into the conversation.
- Read JSON keys or filtered findings instead of opening the entire artifact when it is large.
- Use contact sheets for macro-layout triage and detail renders only on demand.
- Reuse hashes and regression results; do not reread unchanged pages in later rounds.
- Write evidence and issue tables to the review directory, then return only the decision and highest-priority items.
- Keep temporary page images outside the repository or remove them after contact sheets are built.

## Guardrails

- UBC, the program, and the supervisor remain the authorities; this skill cannot guarantee institutional acceptance.
- Never copy candidate PDFs, page renders, extracted text, completed `author-info.yml` files, names, absolute paths, hashes, or candidate-specific findings into the skill's tracked source files. Keep them in the ignored per-run directory.
- Flag GenAI use/disclosure for author confirmation. Do not invent or silently insert disclosure language.
- Do not validate factual claims, permissions, signatures, committee membership, or Workday metadata from appearance alone.
- Do not upload to cIRcle, accept a licence, or use credentials without separate explicit authorization.
