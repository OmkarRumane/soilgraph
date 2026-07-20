"""
rag/ingestion.py

Stage 1 of the dual-representation pipeline (Section 4.1).
Parses raw source documents (PDF) into structured elements using
Unstructured.io's table-aware partitioning. This module has ONE job:
turn a file on disk into a list of typed, ordered elements. It does not
chunk for vectors (rag/chunking.py) and does not extract graph triples
(graph/extraction_pipeline.py) — those are separate stages that both
consume this module's output, per the dual-representation design.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Element, Table, NarrativeText, Title


class ElementKind(str, Enum):
    NARRATIVE = "narrative"
    TABLE = "table"
    TITLE = "title"
    OTHER = "other"


@dataclass
class ParsedElement:
    kind: ElementKind
    text: str                 # plain text (or HTML for tables — see note below)
    source_document: str       # filename, for provenance tracing
    page_number: int | None


def _classify(el: Element) -> ElementKind:
    if isinstance(el, Table):
        return ElementKind.TABLE
    if isinstance(el, Title):
        return ElementKind.TITLE
    if isinstance(el, NarrativeText):
        return ElementKind.NARRATIVE
    return ElementKind.OTHER


def parse_document(filepath: str | Path) -> list[ParsedElement]:
    """
    Parses a single PDF into a list of ParsedElement.

    Tables are kept as HTML (via Unstructured's `infer_table_structure`)
    rather than flattened to text — this preserves row/column relationships
    for nutrient thresholds and sequestration-rate tables, which is the
    specific failure mode this pipeline exists to avoid.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"No such file: {filepath}")

    raw_elements = partition_pdf(
        filename=str(filepath),
        strategy="hi_res",            # needed for reliable table detection
        infer_table_structure=True,   # produces el.metadata.text_as_html for tables
    )

    parsed: list[ParsedElement] = []
    for el in raw_elements:
        kind = _classify(el)
        text = (
            el.metadata.text_as_html
            if kind == ElementKind.TABLE and el.metadata.text_as_html
            else str(el)
        )
        parsed.append(
            ParsedElement(
                kind=kind,
                text=text,
                source_document=filepath.name,
                page_number=getattr(el.metadata, "page_number", None),
            )
        )
    return parsed


def parse_corpus(raw_dir: str | Path = "data/raw") -> dict[str, list[ParsedElement]]:
    """Parses every PDF in raw_dir. Returns {filename: [ParsedElement, ...]}."""
    raw_dir = Path(raw_dir)
    pdfs = sorted(raw_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {raw_dir}. Add source documents and re-run.")
        return {}

    results = {}
    for pdf in pdfs:
        print(f"Parsing {pdf.name} ...")
        results[pdf.name] = parse_document(pdf)
    return results


if __name__ == "__main__":
    corpus = parse_corpus()
    for filename, elements in corpus.items():
        n_narrative = sum(1 for e in elements if e.kind == ElementKind.NARRATIVE)
        n_tables = sum(1 for e in elements if e.kind == ElementKind.TABLE)
        n_titles = sum(1 for e in elements if e.kind == ElementKind.TITLE)
        print(
            f"  {filename}: {len(elements)} elements "
            f"({n_narrative} narrative, {n_tables} tables, {n_titles} titles)"
        )