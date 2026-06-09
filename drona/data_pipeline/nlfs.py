"""
NLFS 2017/18 (Nepal Labour Force Survey) PDF ingestion for D.R.O.N.A.

The NLFS is the flagship Nepal-tier labour-market source (contribution C4:
locally-grounded advising). It is published only as a PDF report, so we extract
text and chunk it into evidence snippets that the retriever can cite when
grounding claims about the Nepali job market (employment rates, sector shares,
youth unemployment, etc.).

License: Free public data, Government of Nepal (NSO / CBS).
Source:  https://data.nsonepal.gov.np/ (Labour Force Survey 2017/18 PDF)

We deliberately produce *evidence snippets*, not parsed statistics tables: PDF
table extraction is brittle, and for RAG grounding, faithful text excerpts with
page provenance are more defensible at viva than fragile numeric scrapes.
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

from drona.contracts import DataTier
from drona.data_pipeline.data_card import DataCard

NLFS_VERSION = "2017/18"
NLFS_PDF_URL = (
    "https://data.nsonepal.gov.np/dataset/a095d482-4f68-4aec-809b-ae8041d3817c/"
    "resource/9f5e1585-2af7-4257-bb6b-59073b1da34f/download/"
    "labour-force-survey-2017_18.pdf"
)

# Snippets must mention at least one labour-market term to be retained — keeps
# the dataset relevant and drops boilerplate (title pages, acknowledgements).
_RELEVANCE_TERMS = re.compile(
    r"\b(employ|unemploy|labour|labor|workforce|wage|income|sector|"
    r"informal|industry|occupation|skill|youth|migrat|economic|job)\w*",
    re.IGNORECASE,
)


class LabourSnippet(BaseModel):
    """One citable evidence snippet from the NLFS report."""

    snippet_id: str
    source: str = "NLFS 2017/18"
    tier: DataTier = DataTier.NEPAL
    page: int
    text: str = Field(min_length=40)
    is_synthetic: bool = False


def download_pdf(dest_path: Path | None = None, force: bool = False, timeout: int = 180) -> Path:
    """Download the NLFS PDF if not cached."""
    from drona.utils.settings import settings

    if dest_path is None:
        dest_path = settings.data_raw_dir / "nlfs_2017_18.pdf"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and not force:
        logger.info(f"NLFS PDF already cached at {dest_path}")
        return dest_path

    import httpx

    logger.info(f"Downloading NLFS PDF from {NLFS_PDF_URL}")
    with httpx.stream("GET", NLFS_PDF_URL, follow_redirects=True, timeout=timeout) as r:
        r.raise_for_status()
        with dest_path.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=65536):
                f.write(chunk)
    logger.success(f"NLFS PDF saved to {dest_path} ({dest_path.stat().st_size:,} bytes)")
    return dest_path


def _chunk_page(text: str, min_chars: int = 200, max_chars: int = 900) -> list[str]:
    """Split page text into sentence-packed chunks within a char budget.

    Paragraphs are detected first (blank-line separated), then sentences are
    packed greedily up to ``max_chars``. Sentences longer than ``max_chars``
    (rare, usually mangled tables) are hard-split so no chunk exceeds the budget.
    Chunks shorter than ``min_chars`` are dropped as low-value fragments.
    """
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        para = re.sub(r"\s+", " ", para).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", para):
            sent = sentence.strip()
            while len(sent) > max_chars:
                chunks.append(sent[:max_chars])
                sent = sent[max_chars:]
            if not sent:
                continue
            if len(buf) + len(sent) + 1 <= max_chars:
                buf = f"{buf} {sent}".strip()
            else:
                if buf:
                    chunks.append(buf)
                buf = sent
        # Paragraph boundary flush keeps chunks topically coherent.
        if len(buf) >= max_chars * 0.6:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= min_chars]


def extract_snippets(pdf_path: Path, max_pages: int | None = None) -> list[LabourSnippet]:
    """Extract relevant labour-market snippets from the NLFS PDF.

    Args:
        pdf_path: Path to the NLFS PDF.
        max_pages: Optional cap on pages processed (for quick tests).

    Returns:
        Validated LabourSnippet objects (Nepal tier), deduplicated.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"NLFS PDF not found: {pdf_path}. Run nlfs.download_pdf() or place it manually."
        )

    from pypdf import PdfReader

    logger.info(f"Extracting NLFS snippets from {pdf_path}")
    reader = PdfReader(str(pdf_path))
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]

    snippets: list[LabourSnippet] = []
    seen: set[str] = set()
    for page_no, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as e:  # pragma: no cover - depends on PDF internals
            logger.warning(f"  Page {page_no} extraction failed: {e}")
            continue
        for chunk in _chunk_page(text):
            if not _RELEVANCE_TERMS.search(chunk):
                continue
            key = chunk[:120].lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                snippets.append(
                    LabourSnippet(
                        snippet_id=f"nlfs_p{page_no}_{len(snippets):04d}",
                        page=page_no,
                        text=chunk,
                    )
                )
            except Exception:
                continue  # too short after validation

    logger.success(f"  Extracted {len(snippets)} labour-market snippets from NLFS")
    return snippets


def build_data_card(snippets: list[LabourSnippet], output_path: Path) -> DataCard:
    """Create and write the NLFS data card (YAML + Markdown)."""
    card = DataCard(
        name="nlfs_labour_snippets",
        version=NLFS_VERSION,
        source_name=f"Nepal Labour Force Survey {NLFS_VERSION}",
        source_url=NLFS_PDF_URL,
        license="Free public data — Government of Nepal (NSO/CBS)",
        tier="nepal",
        collection_method="automated_bulk_download",
        record_count=len(snippets),
        fields=list(LabourSnippet.model_fields.keys()),
        description=(
            f"Citable evidence snippets extracted from the NLFS {NLFS_VERSION} PDF. "
            f"These ground Nepal-tier claims about the local labour market "
            f"(employment, sectors, youth/informal work) in the advising layer (C4)."
        ),
        known_limitations=[
            "PDF text extraction can mangle tables/figures — snippets are prose-biased",
            "2017/18 is the latest full NLFS; figures predate recent shifts",
            "Relevance filter is keyword-based and may miss some context",
        ],
        contains_synthetic=False,
        output_files=[str(output_path)],
        notes="Snippets are faithful excerpts with page provenance for citation grounding.",
    )
    card.write(output_path.parent / "nlfs_labour_snippets_data_card.yaml")
    logger.info("NLFS data card written")
    return card
