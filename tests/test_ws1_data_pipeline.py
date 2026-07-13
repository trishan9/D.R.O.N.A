"""
WS1 smoke tests - data pipeline layer.

These tests do NOT hit the network, download files, or write to ChromaDB.
They verify the logic and schema validation using in-memory fixtures only.

Run with:  pytest tests/test_ws1_data_pipeline.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

from drona.contracts import CareerPathway, CurriculumModule, DataTier, JobPosting
from drona.data_pipeline.curriculum import _extract_module_code, _extract_year, parse_text
from drona.data_pipeline.data_card import DataCard
from drona.data_pipeline.scrapers.manual_loader import load_file

# ── DataCard ─────────────────────────────────────────────────────────────────

class TestDataCard:
    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        card = DataCard(
            name="test_dataset",
            source_name="TestSource",
            license="CC BY 4.0",
            tier="nepal",
            collection_method="manual_user_collection",
            record_count=42,
            description="A test dataset",
        )
        out = tmp_path / "card.yaml"
        card.write(out)
        assert out.exists()
        loaded = DataCard.read(out)
        assert loaded.name == "test_dataset"
        assert loaded.record_count == 42
        assert loaded.tier == "nepal"

    def test_synthetic_flagging(self) -> None:
        card = DataCard(
            name="synth",
            source_name="Generator",
            license="N/A",
            tier="synthetic",
            collection_method="synthetic_llm",
            contains_synthetic=True,
            synthetic_fraction=1.0,
        )
        assert card.contains_synthetic
        assert card.synthetic_fraction == 1.0

    def test_robots_txt_fields(self) -> None:
        card = DataCard(
            name="scraped",
            source_name="TestPortal",
            license="custom",
            tier="nepal",
            collection_method="automated_scrape_public",
            robots_txt_verified=True,
            robots_txt_allows_crawl=True,
            rate_limit_applied="0.5 req/s",
        )
        assert card.robots_txt_verified
        assert card.rate_limit_applied == "0.5 req/s"


# ── Curriculum parser ─────────────────────────────────────────────────────────

class TestCurriculumParser:
    _SAMPLE_TEXT = """
    Module Title: Introduction to Programming
    Module Code: 4001COMP
    Year 1, Semester 1
    Credits: 20

    Module Description:
    This module introduces fundamental programming concepts using Python.
    Students will learn variables, control flow, functions, and basic data structures.

    Learning Outcomes:
    - Understand and apply variables and data types
    - Write Python functions and use control flow structures
    - Debug simple programs using systematic techniques
    - Apply basic object-oriented programming concepts

    Prerequisites: None

    Skills Developed: Python, problem-solving, debugging, OOP
    """

    def test_module_code_extraction(self) -> None:
        assert _extract_module_code("Module Code: 4001COMP") == "4001COMP"
        assert _extract_module_code("Module: CS101 Introduction") == "CS101"
        assert _extract_module_code("no code here") is None

    def test_year_extraction(self) -> None:
        assert _extract_year("Year 1, Semester 1") == 1
        assert _extract_year("Level 4 module") == 1
        assert _extract_year("second year elective") == 2
        assert _extract_year("Level 5 advanced") == 2

    def test_parse_text_full(self) -> None:
        m = parse_text(self._SAMPLE_TEXT, source_document="4001COMP.pdf")
        assert m is not None
        assert m.module_code == "4001COMP"
        assert "Programming" in m.title
        assert m.year == 1
        assert m.credits == 20
        assert len(m.learning_outcomes) >= 3
        assert m.source_document == "4001COMP.pdf"

    def test_parse_text_minimal(self) -> None:
        m = parse_text("Module: Database Systems\n4002COMP\nYear 2\nSQL and relational design.")
        assert m is not None
        assert m.year == 2

    def test_parse_text_empty_returns_none(self) -> None:
        result = parse_text("")
        assert result is None

    def test_parse_file_pdf(self, tmp_path: Path) -> None:
        """Verify parse_file handles a .txt file (PDF requires pypdf integration test)."""
        txt_file = tmp_path / "5001COMP.txt"
        txt_file.write_text(
            "Module Title: Software Engineering\n"
            "Module Code: 5001COMP\n"
            "Year 2\n"
            "Credits: 20\n"
            "This module covers software development lifecycle, Agile, Git.\n"
            "Learning Outcomes:\n"
            "- Apply Agile methodologies\n"
            "- Use Git for version control\n",
            encoding="utf-8",
        )
        from drona.data_pipeline.curriculum import parse_file
        m = parse_file(txt_file)
        assert m is not None
        assert m.module_code == "5001COMP"


# ── Manual loader ─────────────────────────────────────────────────────────────

class TestManualLoader:
    def _make_json(self, path: Path, records: list[dict]) -> None:
        path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    def test_load_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        self._make_json(f, [
            {
                "posting_id": "mj_001",
                "source": "merojob",
                "tier": "nepal",
                "title": "Junior Python Developer",
                "employer": "Leapfrog",
                "location": "Kathmandu",
                "skills_required": ["Python", "Django"],
                "description": "Build web apps.",
                "is_synthetic": False,
            }
        ])
        posts = load_file(f)
        assert len(posts) == 1
        assert posts[0].posting_id == "mj_001"
        assert posts[0].tier == DataTier.NEPAL

    def test_load_skips_invalid_entry(self, tmp_path: Path) -> None:
        f = tmp_path / "mixed.json"
        self._make_json(f, [
            {
                "posting_id": "mj_001",
                "source": "merojob",
                "tier": "nepal",
                "title": "Valid Job",
                "is_synthetic": False,
            },
            {
                "posting_id": "mj_002",
                "source": "merojob",
                # missing required 'tier' field
                "title": "Invalid Job",
                "is_synthetic": False,
            },
        ])
        posts = load_file(f)
        assert len(posts) == 1  # invalid entry skipped
        assert posts[0].posting_id == "mj_001"

    def test_load_empty_json(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.json"
        f.write_text("[]", encoding="utf-8")
        posts = load_file(f)
        assert posts == []


# ── Ingestor (unit tests - no real ChromaDB) ─────────────────────────────────

class TestIngestorDocBuilders:
    """Test the document text builders without initialising ChromaDB."""

    def test_curriculum_doc(self) -> None:
        from drona.data_pipeline.ingest import _curriculum_doc
        m = CurriculumModule(
            module_code="4001COMP",
            title="Intro to Programming",
            year=1,
            skills_developed=["Python", "OOP"],
            learning_outcomes=["Understand variables"],
        )
        doc = _curriculum_doc(m)
        assert "4001COMP" in doc
        assert "Python" in doc
        assert "Year 1" in doc

    def test_job_doc(self) -> None:
        from drona.data_pipeline.ingest import _job_doc
        p = JobPosting(
            posting_id="jn_001",
            source="jobsnepal",
            tier=DataTier.NEPAL,
            title="Backend Developer",
            employer="Cotiviti",
            location="Kathmandu",
            skills_required=["Python", "Django"],
            salary_min_npr=60000,
            salary_max_npr=90000,
        )
        doc = _job_doc(p)
        assert "Backend Developer" in doc
        assert "Cotiviti" in doc
        assert "60,000" in doc

    def test_pathway_doc(self) -> None:
        from drona.data_pipeline.ingest import _pathway_doc
        pw = CareerPathway(
            pathway_id="onet_15_1252_00",
            title="Software Developer",
            tier=DataTier.INTERNATIONAL,
            onet_soc_code="15-1252.00",
            typical_skills=["Python", "Java", "SQL"],
        )
        doc = _pathway_doc(pw)
        assert "Software Developer" in doc
        assert "Python" in doc


# ── Settings ─────────────────────────────────────────────────────────────────

class TestSettings:
    def test_tier_boost_values(self) -> None:
        from drona.utils.settings import settings
        assert settings.tier_boost("nepal") >= 1.0
        assert settings.tier_boost("international") == 1.0
        assert settings.tier_boost("synthetic") < 1.0
        assert settings.tier_boost("nepal") > settings.tier_boost("international")

    def test_settings_load_without_dotenv(self) -> None:
        from drona.utils.settings import DronaSettings
        s = DronaSettings()
        assert s.ollama_model
        assert s.retrieval_top_k > 0
