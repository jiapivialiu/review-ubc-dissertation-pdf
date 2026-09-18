# Review UBC Thesis or Dissertation PDF

A read-only Codex skill for checking a University of British Columbia master's thesis or doctoral dissertation PDF before final submission to cIRcle.

It supports UBC Vancouver and UBC Okanagan, degree-specific committee checks, PDF and margin preflight, page-by-page visual review, figure-legibility screening, citation metadata verification, and regression review after revisions.

## Install

Clone the repository so that `SKILL.md` is directly inside the skill directory:

```bash
git clone https://github.com/jiapivialiu/review-ubc-dissertation-pdf.git \
  "$HOME/.codex/skills/review-ubc-dissertation-pdf"
```

Install the Python dependencies and Poppler (`pdftoppm`):

```bash
python3 -m pip install -r requirements.txt
```

On macOS, install Poppler with `brew install poppler`. On Debian or Ubuntu, use `sudo apt-get install poppler-utils`.

## Use

Invoke `$review-ubc-dissertation-pdf` and provide the candidate PDF. Ask for:

- a quick screening review;
- a strict final preflight;
- a comparison with an earlier PDF; or
- a citation and bibliography audit.

The skill does not edit, rename, upload, or optimize the candidate PDF unless separately authorized. UBC Graduate and Postdoctoral Studies, the student's graduate program, and the supervisor remain authoritative.

## Privacy

Review artifacts can contain names, extracted text, page images, local paths, and file hashes. The default per-run directories and common PDF-review outputs are excluded by `.gitignore`. Before committing changes to this repository, still run `git status --ignored` and confirm that no candidate-specific material is present.

The bundled scripts process PDFs locally. Citation verification uses public authoritative bibliographic records but should not upload dissertation text.

## License

MIT. See `LICENSE`.
