# Data Sources
Raw source documents are not committed to this repository (size + licensing).
To reproduce the corpus, place PDFs in `data/raw/` sourced from:
- FAO soil databases — https://www.fao.org/soils-portal/
- USDA NRCS regenerative agriculture technical guides
- Peer-reviewed soil science papers via the Semantic Scholar API
- Published carbon credit registry methodologies (e.g. Verra VM0042-style docs)
Each file's origin should be recorded in `data/manifest.json` (added in a later step)
so every graph triple's `source_citation` can be traced back to a retrievable document.
