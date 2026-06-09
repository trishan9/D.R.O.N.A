"""
Softwarica College curriculum parser for D.R.O.N.A.

Converts module descriptor documents (PDF / DOCX / plain text) into validated
CurriculumModule objects ready for embedding and retrieval.

Supported input formats:
  .pdf   — pypdf text extraction (works for digitally-created PDFs)
  .docx  — python-docx paragraph extraction
  .txt   — direct UTF-8 read
  .md    — same as .txt

The parser is deliberately lenient: it extracts what it can and logs warnings
for fields it cannot find. A module with only module_code + title + description
is still useful for retrieval, even if learning_outcomes is empty.

Usage (in a script):
    from drona.data_pipeline.curriculum import parse_file, parse_directory
    modules = parse_directory(Path("data/raw/curriculum/"))
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from drona.contracts import CurriculumModule

# ── Text extraction ─────────────────────────────────────────────────────────

def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            pages.append(t)
    return "\n".join(pages)


def _extract_docx(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        raise ImportError(
            "python-docx is not installed. Run: pip install python-docx"
        )
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


_EXTRACTORS: dict[str, Callable[[Path], str]] = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_txt,
    ".md": _extract_txt,
}


def extract_text(path: Path) -> str:
    """Extract raw text from any supported curriculum document."""
    ext = path.suffix.lower()
    extractor = _EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {list(_EXTRACTORS)}"
        )
    text = extractor(path)
    logger.debug(f"  Extracted {len(text):,} chars from {path.name}")
    return text


# ── Field extractors ────────────────────────────────────────────────────────

def _find_field(text: str, *labels: str, multiline: bool = False) -> str | None:
    """Search for a labelled field in the text.

    Tries each label in order. Returns the first non-empty value found.

    Labels are matched case-insensitively followed by `:` or whitespace.
    """
    for label in labels:
        # Single-line: captures everything after the label to end of line
        pattern = rf"(?i){re.escape(label)}\s*[:\-]?\s*(.+)"
        m = re.search(pattern, text)
        if m:
            value = m.group(1).strip()
            if value:
                return value
    return None


def _find_list_field(text: str, *labels: str) -> list[str]:
    """Find a bulleted/numbered list following a section header."""
    for label in labels:
        pattern = rf"(?i){re.escape(label)}\s*[:\-]?\s*\n((?:[\s\S]{{1,500}})?)(?:\n[A-Z]|\Z)"
        m = re.search(pattern, text)
        if not m:
            continue
        block = m.group(1)
        # Extract bullet/numbered items
        items = re.findall(
            r"(?:^|\n)\s*(?:[-•*]|\d+[.)]\s*)\s*(.+)", block
        )
        cleaned = [i.strip() for i in items if i.strip()]
        if cleaned:
            return cleaned[:20]
    return []


def _extract_module_code(text: str) -> str | None:
    """Extract module code (e.g. '4001COMP', 'CIS101', 'CS-301')."""
    # Coventry / Softwarica format: 4-digit number + alpha suffix
    m = re.search(r"\b(\d{4}[A-Z]{2,6})\b", text)
    if m:
        return m.group(1)
    # Alternative: alpha-digit codes like CS101, CIS-201
    m = re.search(r"\b([A-Z]{2,4}[-\s]?\d{3,4})\b", text)
    if m:
        return m.group(1).replace(" ", "-")
    return None


def _extract_year(text: str) -> int:
    """Infer year of study from text mentions like 'Year 1', 'Level 4', 'First year'."""
    year_words = {"first": 1, "second": 2, "third": 3, "fourth": 4}
    m = re.search(r"(?i)year\s*([1-4])", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(?i)level\s*([4-7])", text)
    if m:
        level = int(m.group(1))
        return level - 3  # Level 4 → Year 1, Level 5 → Year 2, etc.
    for word, yr in year_words.items():
        if re.search(rf"(?i)\b{word}\s+year\b", text):
            return yr
    return 1  # default to year 1 if not found


def _extract_credits(text: str) -> int | None:
    for label in ("credit", "credits", "credit points", "credit hours"):
        m = re.search(rf"(?i){label}\s*[:\-]?\s*(\d+)", text)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 120:
                return v
    return None


def _extract_skills(text: str, description: str, outcomes: list[str]) -> list[str]:
    """Derive skills from explicit skills sections or infer from content."""
    # Try explicit field first
    explicit = _find_list_field(text, "skills", "skills developed", "skills gained",
                                "technical skills", "key skills")
    if explicit:
        return explicit[:15]

    # Infer from description + outcomes combined text
    combined = description + " ".join(outcomes)
    _SKILL_KW = [
        "Python", "Java", "JavaScript", "C\\+\\+", "C#", "SQL", "HTML", "CSS",
        "React", "Angular", "Node", "Django", "REST", "API", "Git", "Linux",
        "Database", "Networking", "Security", "Algorithm", "Data Structure",
        "Machine Learning", "Statistics", "UX", "UI", "Agile", "OOP",
        "Functional programming", "Debugging", "Testing", "Docker",
    ]
    found = []
    for kw in _SKILL_KW:
        if re.search(rf"\b{kw}\b", combined, re.IGNORECASE):
            found.append(re.sub(r"\\", "", kw))
    return found[:10]


# ── Top-level parsers ────────────────────────────────────────────────────────

def parse_text(text: str, source_document: str | None = None) -> CurriculumModule | None:
    """Parse raw text into a CurriculumModule.

    Returns None if the text lacks both a module code and a title
    (not enough to be useful).
    """
    module_code = _extract_module_code(text)

    # Title: prefer "Module Title:", else first substantial line
    title = _find_field(text, "module title", "title", "module name", "course title")
    if not title:
        # Use first non-empty line longer than 10 chars as title fallback
        for line in text.splitlines():
            stripped = line.strip()
            if len(stripped) > 10 and not stripped.startswith(("#", "//", "/*")):
                title = stripped[:120]
                break

    if not module_code and not title:
        logger.warning("  Cannot identify module_code or title — skipping document")
        return None

    # Use filename as fallback code
    if not module_code:
        module_code = (source_document or "UNKNOWN").replace(".pdf", "").replace(".docx", "")[:20]

    description = _find_field(
        text,
        "module description", "description", "module overview",
        "overview", "synopsis", "summary",
        multiline=True,
    ) or ""

    # Multi-paragraph description fallback
    if len(description) < 50:
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        description = paras[0][:500] if paras else description

    outcomes = _find_list_field(
        text,
        "learning outcomes", "module outcomes", "intended learning outcomes",
        "ILOs", "objectives",
    )

    prerequisites = _find_list_field(
        text, "prerequisites", "pre-requisites", "pre-requisite modules"
    )
    # Prerequisites might also be module codes mentioned after the label
    if not prerequisites:
        prereq_text = _find_field(text, "prerequisite", "pre-requisite")
        if prereq_text:
            codes = re.findall(r"\b\d{4}[A-Z]{2,6}\b", prereq_text)
            prerequisites = codes

    year = _extract_year(text)
    credits = _extract_credits(text)
    skills = _extract_skills(text, description, outcomes)

    is_core = not bool(re.search(r"(?i)\b(optional|elective|choice)\b", text))

    return CurriculumModule(
        module_code=module_code,
        title=title or module_code,
        year=year,
        credits=credits,
        description=description[:1000],
        learning_outcomes=outcomes,
        prerequisites=prerequisites,
        skills_developed=skills,
        is_core=is_core,
        source_document=source_document,
    )


def parse_file(path: Path) -> CurriculumModule | None:
    """Parse a single curriculum document file into a CurriculumModule.

    Args:
        path: Path to a .pdf, .docx, .txt, or .md file.

    Returns:
        A CurriculumModule object, or None if parsing fails.
    """
    logger.info(f"Parsing curriculum document: {path.name}")
    try:
        text = extract_text(path)
        module = parse_text(text, source_document=path.name)
        if module:
            logger.success(f"  → {module.module_code}: {module.title}")
        return module
    except Exception as e:
        logger.error(f"  Failed to parse {path.name}: {e}")
        return None


def parse_directory(directory: Path) -> list[CurriculumModule]:
    """Parse all curriculum documents in a directory.

    Args:
        directory: Directory containing module descriptor files.
                   May contain subdirectories (e.g. year1/, year2/).

    Returns:
        List of successfully parsed CurriculumModule objects.
    """
    extensions = set(_EXTRACTORS.keys())
    files = [
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    ]

    if not files:
        logger.warning(f"No curriculum documents found in {directory}")
        return []

    logger.info(f"Found {len(files)} curriculum documents in {directory}")
    modules: list[CurriculumModule] = []
    for f in sorted(files):
        m = parse_file(f)
        if m:
            modules.append(m)

    logger.success(f"Parsed {len(modules)} / {len(files)} curriculum modules")
    return modules
