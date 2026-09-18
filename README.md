# UBC Thesis & Dissertation PDF Reviewer — Agent Skill

`review-ubc-dissertation-pdf` is an open-source, portable Agent Skill that audits a University of British Columbia master's thesis or doctoral dissertation PDF before final post-defence submission to cIRcle. It checks UBC thesis formatting, PDF margins and page numbering, front matter and committee pages, figure and table legibility, citation metadata, and regressions after revision. Reviews are read-only by default and run locally except for public citation lookups.

The skill follows the open [Agent Skills specification](https://agentskills.io/specification), so it is not tied to one model vendor or agent product. Any Agent Skills-compatible client can discover it from `SKILL.md`; clients with a different skill directory can install the same repository without rewriting its instructions. It supports both UBC Vancouver and UBC Okanagan and distinguishes master's-thesis rules from doctoral-dissertation rules.

## Agent compatibility

The portable skill consists of `SKILL.md`, `scripts/`, `references/`, and `assets/`. The `agents/openai.yaml` file only supplies optional OpenAI-client interface metadata; it is not required by the workflow, and other clients may ignore it.

To use the complete workflow, an agent needs:

- support for the Agent Skills `SKILL.md` format, or an equivalent way to load a folder of instructions and resources;
- local command execution with Python 3 and Poppler (`pdftoppm`);
- the Python packages listed in `requirements.txt`;
- web access for current UBC-rule checks and final citation verification.

## What does this UBC dissertation review skill check?

- UBC Graduate and Postdoctoral Studies (G+PS) formatting requirements and component order
- US Letter page size, one-sided layout, margins, page-number placement, blank pages, and rotation
- title, committee, abstract, lay summary, preface, table of contents, bibliography, and appendices
- degree-specific committee roles for UBC master's theses and doctoral dissertations
- final cIRcle filename, PDF validity, security settings, and submission readiness
- clipped or undersized text in figures, tables, equations, captions, legends, and axes
- bibliography-to-text mappings and paper metadata against authoritative online records
- changes and unresolved findings between an earlier PDF and a revised PDF

The automated checks produce leads, not unsupported verdicts. Suspected geometry or layout problems are visually confirmed before they become blockers.

## Review modes

| Mode | Best for | Coverage |
| --- | --- | --- |
| `screen` | Early or routine checks | Whole-file automation, contact-sheet review, and targeted inspection |
| `final` | Submission-ready GO/NO-GO review | Full UBC checklist, strict geometry, citation verification, and exhaustive visual triage |
| `regression` | A revised thesis or dissertation | Comparison with an earlier PDF or issue list and focused rechecking |

## Install the Agent Skill

The Agent Skills specification defines the contents of a skill, while each client decides where installed skills live. For the cross-client `.agents/skills` convention, install it at user scope with:

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/jiapivialiu/review-ubc-dissertation-pdf.git \
  "$HOME/.agents/skills/review-ubc-dissertation-pdf"
```

For one repository or project only, clone it under that project's `.agents/skills/` directory instead. If your agent uses a product-specific skills directory, clone the same repository there; `SKILL.md` must remain directly inside the `review-ubc-dissertation-pdf` directory.

Then install the Python dependencies and Poppler (`pdftoppm`):

```bash
cd "$HOME/.agents/skills/review-ubc-dissertation-pdf"
python3 -m pip install -r requirements.txt
```

On macOS, install Poppler with `brew install poppler`. On Debian or Ubuntu, use `sudo apt-get install poppler-utils`.

Reload or restart the agent client if it does not detect the new skill automatically.

## Example prompts

Ask naturally for a UBC thesis or dissertation review, or explicitly invoke `review-ubc-dissertation-pdf` using your client's skill syntax. For clients that support `$` mentions, for example:

```text
Use $review-ubc-dissertation-pdf to check my UBC PhD dissertation PDF for final cIRcle submission.
```

```text
Review this UBC master's thesis for margins, page numbering, front matter, committee-page roles, and filename compliance.
```

```text
Run a strict final UBC thesis preflight, including figure legibility and verification of every paper citation.
```

```text
Compare this revised dissertation PDF with the previous version and recheck every unresolved issue.
```

## What does the report contain?

The report leads with the number of unresolved blockers and major issues. Each finding includes severity, PDF page and printed page label, evidence or UBC rule, a concise diagnosis, and the smallest practical action. A strict final review issues `GO` only after submission-critical author confirmations, citation checks, geometry review, visual checks, and a fresh final-file preflight are complete.

The skill does not promise institutional acceptance. [UBC Graduate and Postdoctoral Studies thesis-preparation guidance](https://www.grad.ubc.ca/current-students/dissertation-thesis-preparation), the student's graduate program, and the supervisor remain authoritative.

## How it works

1. Establishes a current UBC requirement baseline and collects only missing submission-critical facts.
2. Runs deterministic PDF preflight checks without changing the candidate.
3. Reviews low-resolution contact sheets and high-resolution renders of risky pages.
4. Checks organization and, in final mode, verifies every paper citation against authoritative records.
5. Returns a concise, auditable issue list and keeps review artifacts outside the thesis source tree by default.

## Frequently asked questions

### Can it check whether a UBC thesis meets margin requirements?

Yes. The final-mode geometry pass measures visible rendered content against UBC minimum margins, then requires visual confirmation of every flagged page. It separately applies UBC's page-number distance rule.

### Does it work for both UBC master's theses and PhD dissertations?

Yes. It supports UBC Vancouver and UBC Okanagan and applies degree-specific committee-page rules rather than treating master's and doctoral requirements as interchangeable.

### Can it review citations and the bibliography?

Yes. Final mode verifies every paper's existence and material bibliographic metadata, maps in-text citations to bibliography entries, and distinguishes preprints from later conference or journal versions. It does not claim that a cited paper supports a substantive argument unless claim checking is separately requested.

### Will it edit or upload my dissertation?

No. The default workflow does not edit, rename, optimize, or upload the source PDF. Any source change or cIRcle action requires separate explicit authorization.

## Privacy

Review artifacts can contain names, extracted text, page images, local paths, and file hashes. The default per-run directories and common PDF-review outputs are excluded by `.gitignore`. Before committing changes to this repository, still run `git status --ignored` and confirm that no candidate-specific material is present.

The bundled scripts process PDFs locally. Citation verification uses public authoritative bibliographic records but should not upload dissertation text.

## License

MIT. See [`LICENSE`](LICENSE).
