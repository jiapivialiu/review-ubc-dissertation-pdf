# Citation verification

Use this workflow in `final` mode and whenever citation or reference checking is explicitly in scope. It verifies that cited papers exist and that their bibliographic identity is correct; it does not judge whether a paper supports the thesis or dissertation's substantive claim unless the user separately requests claim checking.

## Build the audit set

1. Extract the bibliography/reference list and the in-text citation keys or author-year strings without loading the full dissertation into the conversation.
2. Normalize whitespace and obvious PDF extraction artifacts, but retain the source text for comparison.
3. Give every bibliography entry a stable local ID. Identify papers separately from books, theses, standards, datasets, software, websites, and other source types.
4. Map each in-text citation to a bibliography entry. Flag unresolved, ambiguous, duplicate, and uncited bibliography entries; account for year suffixes such as `2024a`/`2024b`.
5. Verify every paper entry. Do not sample. Identical duplicate entries may share one lookup only when they are all retained in the mapping and reported as duplicates.
6. Group likely versions of the same work into a version family. Use DOI relations, arXiv identifiers, title similarity, author overlap, abstracts, publisher links, and explicit “published as” statements; do not merge papers from title similarity alone.
7. Record every source location for each citation key using the `.tex` path and line number. When available, also map it through the compiled PDF to the one-based PDF page and printed label.

## Search and evidence rules

Use live web search for each paper. Start with a DOI when one is printed; otherwise search the exact title plus first author and year. A DOI must resolve to matching metadata—syntactic validity or a redirect alone is not enough.

Prefer sources in this order:

1. DOI registration metadata and the publisher's article page.
2. An authoritative discipline index or primary repository, such as PubMed, IEEE Xplore, ACM Digital Library, arXiv for the identified preprint version, or an institutional repository.
3. Crossref or another established bibliographic registry.

Use Google Scholar, Semantic Scholar, ResearchGate, library discovery pages, author profiles, and search snippets for discovery or corroboration only; do not treat them as the sole authority when a primary or registry record is available. Do not use a citation copied from another paper as proof.

For each paper, record at least one authoritative evidence URL and the access date. If a source conflicts with the bibliography, consult a second authoritative source before classifying the discrepancy. Distinguish version differences—preprint, accepted manuscript, conference paper, and journal article—instead of merging them silently.

## Resolve arXiv and publication versions

For every arXiv or other preprint citation:

1. Open the authoritative arXiv abstract page and record the identifier, current title and authors, latest version number, latest revision date, DOI, and journal reference when present.
2. Follow the DOI or journal reference and independently search the exact title plus first author for a conference or journal version. Do this even when arXiv does not list a DOI or journal reference.
3. Compare the preprint and publication as a version family. Confirm whether they are the same work, a renamed version of record, a shorter conference paper, a substantially extended journal paper, or distinct papers.
4. Prefer the final peer-reviewed version of record when it represents the same work and supports the cited claim. If no formal publication exists, keep the arXiv citation but update it to the latest arXiv metadata/version. Keep a preprint alongside a publication only when the dissertation intentionally relies on content unique to that version or discusses the versions separately.
5. Do not assume that the newest date is automatically the correct citation. A later arXiv revision, conference version, and journal extension can contain materially different results; inspect the cited context and retain the version that actually supports it.

Set a version status for every member of a version family:

- `CURRENT`: the cited entry is the appropriate current or version-of-record citation.
- `PUBLISHED VERSION AVAILABLE`: a preprint is cited although a matching formal publication should normally replace it.
- `DUPLICATE VERSION`: multiple entries cite the same work in interchangeable versions without a clear contextual reason.
- `DISTINCT VERSION`: related versions differ materially and the current citation context justifies keeping them separate.
- `QUERY`: the relationship or appropriate version cannot be established reliably.

Treat `PUBLISHED VERSION AVAILABLE` and unintended `DUPLICATE VERSION` as `CONFLICT` in the main audit until resolved.

## Resolve duplicate-version citations

For each version family cited under more than one bibliography key:

1. List all keys and every `.tex` citation location.
2. Read the surrounding sentence or paragraph at each location to determine whether it cites a shared result, version-specific result, historical chronology, or a comparison between versions.
3. If the citations are interchangeable, select one canonical key—normally the verified version of record—repoint every affected `\cite...{}` occurrence to it, and recommend deleting the obsolete `.bib` entry.
4. If the versions support different claims, keep both and explain the distinction at the relevant citation locations; recommend clarifying the prose when the reason for citing both is not evident.
5. Never delete a bibliography entry before confirming that no source file still cites its key. In read-only review mode, provide the exact edit plan without changing source files. When source editing is explicitly authorized, update all `.tex` keys first, remove the obsolete `.bib` entry, rebuild, and require zero undefined citations or references.

## Compare bibliographic identity

Compare the thesis or dissertation entry with the verified record field by field:

- complete author surnames, initials or given names as required by the selected style, and author order;
- title and subtitle;
- publication year, including online-first versus issue year when the style guide distinguishes them;
- journal or proceedings title;
- volume, issue, page range or article number;
- DOI or other persistent identifier;
- publication type and version.

Treat accent marks, hyphens, particles, transliteration, group authors, and compound surnames carefully. Do not infer an author's identity from initials or a familiar-looking name. Formatting normalization may explain punctuation or capitalization differences, but it cannot explain a different person, author order, title, venue, or identifier.

Then perform a separate style pass against the author-confirmed style guide. Check consistent in-text author display, `et al.`, year suffixes, bibliography ordering, capitalization, punctuation, journal naming, DOI presentation, and required fields. Record style defects independently from metadata conflicts.

## Classify and save results

Create `citation-audit.csv` or `citation-audit.md` in the review directory with one row per bibliography entry and these fields:

| Field | Meaning |
|---|---|
| Local ID | Stable bibliography-entry identifier |
| Source citation | Compact extracted citation text |
| In-text mapping | Matching citation locations or unresolved status |
| Type | Paper, book, thesis, dataset, software, web, or other |
| Status | `VERIFIED`, `CONFLICT`, `NOT FOUND`, or `QUERY` |
| Compared fields | Author, title, year, venue, volume/issue/pages, identifier |
| Version family | Related preprint, conference, journal, and accepted-manuscript keys |
| Version status | `CURRENT`, `PUBLISHED VERSION AVAILABLE`, `DUPLICATE VERSION`, `DISTINCT VERSION`, or `QUERY` |
| Citation locations | `.tex` path and line; PDF page/printed label when available |
| Evidence | Authoritative URL(s) and access date |
| Finding | Exact mismatch or uncertainty |
| Minimal action | Exact key replacement, metadata correction, deletion, prose clarification, or author check |

Status meanings:

- `VERIFIED`: an authoritative online record confirms the paper's identity and all material metadata fields match, allowing only style-level differences.
- `CONFLICT`: an authoritative record exists but one or more material metadata fields differ.
- `NOT FOUND`: targeted searches did not locate an authoritative record for the claimed paper.
- `QUERY`: extraction, source disagreement, version ambiguity, or access limitations prevent a reliable decision.

## Give location-specific edit recommendations

For every `CONFLICT`, outdated version, or unintended duplicate version, provide a compact edit row:

| Source location | Current citation/key | Verified replacement | Recommended edit | Reason/evidence |
|---|---|---|---|---|

Use source locations that remain actionable: `.tex` path plus one-based line number, and the PDF page/printed label when available. State whether to replace a key in place, merge several keys into one citation, update `.bib` metadata, delete an obsolete entry after repointing its uses, or retain both versions with clarified prose. When a single key occurs at many locations, list all locations or provide a complete machine-readable location list and summarize the repeated change.

Report the exact conflicting fields; do not replace them from memory. Re-run affected entries after the author revises the thesis or dissertation. A `final` review cannot receive `GO` while any paper remains `CONFLICT`, `NOT FOUND`, or `QUERY`, while an obsolete or unintended duplicate-version citation remains, or while live online search was unavailable.
