"""
Phase 1 (extended) tests — ESCO, BLS, NLFS, synthetic generator, data-card MD.

All offline: no network, no DB, no embeddings. Heavy/network paths (ESCO API,
PDF download, sentence-transformers, pgvector/pinecone upsert) are intentionally
NOT exercised here; they're integration concerns.
"""

from __future__ import annotations

from pathlib import Path

from drona.contracts import CareerPathway, DataTier, JobPosting
from drona.data_pipeline import bls, esco, nlfs, synthetic
from drona.data_pipeline.data_card import DataCard

# ── ESCO CSV loader ───────────────────────────────────────────────────────────

class TestEsco:
    def _write_csvs(self, d: Path) -> None:
        (d / "occupations_en.csv").write_text(
            "conceptUri,iscoGroup,preferredLabel,description,code\n"
            "http://esco/occ/1,2512,Software developer,Builds software.,2512.1\n"
            "http://esco/occ/2,2511,Systems analyst,Analyses systems.,2511.1\n"
            "http://esco/occ/3,7411,Electrician,Wires buildings.,7411.1\n",
            encoding="utf-8",
        )
        (d / "skills_en.csv").write_text(
            "conceptUri,preferredLabel\n"
            "http://esco/skill/py,Python\n"
            "http://esco/skill/sql,SQL\n",
            encoding="utf-8",
        )
        (d / "occupationSkillRelations_en.csv").write_text(
            "occupationUri,skillUri\n"
            "http://esco/occ/1,http://esco/skill/py\n"
            "http://esco/occ/1,http://esco/skill/sql\n",
            encoding="utf-8",
        )

    def test_parse_filters_to_ict(self, tmp_path: Path) -> None:
        self._write_csvs(tmp_path)
        pathways = esco.parse_csv_dir(tmp_path)
        titles = {p.title for p in pathways}
        assert "Software developer" in titles
        assert "Systems analyst" in titles
        assert "Electrician" not in titles  # ISCO 74xx filtered out
        assert all(p.tier == DataTier.INTERNATIONAL for p in pathways)

    def test_parse_attaches_skills(self, tmp_path: Path) -> None:
        self._write_csvs(tmp_path)
        dev = next(p for p in esco.parse_csv_dir(tmp_path) if p.title == "Software developer")
        assert "Python" in dev.typical_skills
        assert "SQL" in dev.typical_skills
        assert dev.esco_code

    def test_missing_skills_files_degrade_gracefully(self, tmp_path: Path) -> None:
        (tmp_path / "occupations_en.csv").write_text(
            "conceptUri,iscoGroup,preferredLabel,description,code\n"
            "http://esco/occ/1,2512,Software developer,Builds.,2512.1\n",
            encoding="utf-8",
        )
        pathways = esco.parse_csv_dir(tmp_path)
        assert len(pathways) == 1
        assert pathways[0].typical_skills == []

    def test_missing_occupations_raises(self, tmp_path: Path) -> None:
        import pytest

        with pytest.raises(FileNotFoundError):
            esco.parse_csv_dir(tmp_path)

    def test_data_card(self, tmp_path: Path) -> None:
        self._write_csvs(tmp_path)
        pathways = esco.parse_csv_dir(tmp_path)
        card = esco.build_data_card(pathways, tmp_path / "esco.parquet")
        assert card.tier == "international"
        assert card.license == "CC BY 4.0"
        assert (tmp_path / "esco_career_pathways_data_card.yaml").exists()
        assert (tmp_path / "esco_career_pathways_data_card.md").exists()


# ── BLS OEWS loader ───────────────────────────────────────────────────────────

class TestBls:
    def _write_oews(self, path: Path) -> None:
        path.write_text(
            "OCC_CODE,OCC_TITLE,A_PCT10,A_MEAN,A_PCT90\n"
            "15-1252,Software Developers,70000,120000,180000\n"
            "15-1211,Computer Systems Analysts,60000,99000,150000\n"
            "29-1141,Registered Nurses,55000,80000,110000\n"
            "15-1299,Computer Occupations All Other,*,90000,*\n",
            encoding="utf-8",
        )

    def test_load_filters_computing(self, tmp_path: Path) -> None:
        f = tmp_path / "oews.csv"
        self._write_oews(f)
        wages = bls.load_wage_table(f)
        assert "15-1252" in wages
        assert "29-1141" not in wages  # nursing filtered
        assert wages["15-1252"] == (70000, 180000)

    def test_capped_values_fall_back_to_mean(self, tmp_path: Path) -> None:
        f = tmp_path / "oews.csv"
        self._write_oews(f)
        wages = bls.load_wage_table(f)
        # 15-1299 pct10/pct90 are '*' → both fall back to mean 90000
        assert wages["15-1299"] == (90000, 90000)

    def test_enrich_pathways_matches_soc(self, tmp_path: Path) -> None:
        f = tmp_path / "oews.csv"
        self._write_oews(f)
        wages = bls.load_wage_table(f)
        pw = CareerPathway(
            pathway_id="onet_15_1252_00",
            title="Software Developers",
            tier=DataTier.INTERNATIONAL,
            onet_soc_code="15-1252.00",
        )
        enriched = bls.enrich_pathways([pw], wages)
        assert enriched[0].international_salary_range_usd == (70000, 180000)

    def test_enrich_no_match_unchanged(self, tmp_path: Path) -> None:
        f = tmp_path / "oews.csv"
        self._write_oews(f)
        wages = bls.load_wage_table(f)
        pw = CareerPathway(
            pathway_id="x", title="Painter", tier=DataTier.INTERNATIONAL, onet_soc_code="51-9123.00"
        )
        assert bls.enrich_pathways([pw], wages)[0].international_salary_range_usd is None


# ── NLFS PDF helpers ──────────────────────────────────────────────────────────

class TestNlfs:
    def test_chunk_page_respects_bounds(self) -> None:
        text = "Employment in Nepal is largely informal. " * 30
        chunks = nlfs._chunk_page(text, min_chars=100, max_chars=400)
        assert chunks
        assert all(len(c) <= 400 for c in chunks)

    def test_relevance_filter(self) -> None:
        assert nlfs._RELEVANCE_TERMS.search("youth unemployment rose")
        assert not nlfs._RELEVANCE_TERMS.search("the weather was pleasant today")

    def test_labour_snippet_min_length(self) -> None:
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            nlfs.LabourSnippet(snippet_id="x", page=1, text="too short")

    def test_data_card(self, tmp_path: Path) -> None:
        snips = [
            nlfs.LabourSnippet(
                snippet_id="nlfs_p1_0001",
                page=1,
                text="Informal sector employment accounts for a large labour share in Nepal.",
            )
        ]
        card = nlfs.build_data_card(snips, tmp_path / "nlfs.parquet")
        assert card.tier == "nepal"
        assert card.record_count == 1


# ── Synthetic generator ───────────────────────────────────────────────────────

class TestSynthetic:
    def _anchor(self, pid: str = "mj_001") -> JobPosting:
        return JobPosting(
            posting_id=pid,
            source="merojob",
            tier=DataTier.NEPAL,
            title="Junior Python Developer",
            employer="Leapfrog Technology",
            location="Kathmandu",
            skills_required=["Python", "Django", "SQL", "REST"],
            salary_min_npr=30000,
            salary_max_npr=50000,
        )

    def test_generation_is_labelled_and_anchored(self) -> None:
        out = synthetic.generate_from_anchors([self._anchor()], n_per_anchor=3)
        assert len(out) == 3
        for p in out:
            assert p.is_synthetic is True
            assert p.tier == DataTier.SYNTHETIC
            assert p.synthetic_anchor_ids == ["mj_001"]
            assert p.description.startswith("[SYNTHETIC]")
            assert p.source == "synthetic_rule"

    def test_generation_is_deterministic(self) -> None:
        a = synthetic.generate_from_anchors([self._anchor()], n_per_anchor=2, seed=42)
        b = synthetic.generate_from_anchors([self._anchor()], n_per_anchor=2, seed=42)
        assert [p.posting_id for p in a] == [p.posting_id for p in b]

    def test_real_anchors_ignored_if_synthetic(self) -> None:
        syn_input = self._anchor()
        syn_input = syn_input.model_copy(update={"is_synthetic": True})
        assert synthetic.generate_from_anchors([syn_input]) == []

    def test_salary_jitter_bounded(self) -> None:
        out = synthetic.generate_from_anchors([self._anchor()], n_per_anchor=5)
        for p in out:
            assert p.salary_min_npr is not None
            # within ±20% of 30000
            assert 24000 <= p.salary_min_npr <= 36000

    def test_data_card_marks_synthetic(self, tmp_path: Path) -> None:
        out = synthetic.generate_from_anchors([self._anchor()], n_per_anchor=2)
        card = synthetic.build_data_card(out, tmp_path / "syn.parquet")
        assert card.contains_synthetic is True
        assert card.synthetic_fraction == 1.0
        assert card.tier == "synthetic"


# ── DataCard markdown ─────────────────────────────────────────────────────────

class TestDataCardMarkdown:
    def test_to_markdown_contains_key_sections(self) -> None:
        card = DataCard(
            name="demo",
            source_name="DemoSource",
            license="MIT",
            tier="nepal",
            collection_method="manual_user_collection",
            record_count=10,
            fields=["a", "b"],
            known_limitations=["small"],
            description="A demo.",
        )
        md = card.to_markdown()
        assert "# Data Card — `demo`" in md
        assert "## Fields" in md
        assert "## Known limitations" in md
        assert "DemoSource" in md

    def test_write_emits_yaml_and_md(self, tmp_path: Path) -> None:
        card = DataCard(
            name="demo",
            source_name="S",
            license="MIT",
            tier="nepal",
            collection_method="manual_user_collection",
        )
        out = tmp_path / "demo_data_card.yaml"
        card.write(out)
        assert out.exists()
        assert out.with_suffix(".md").exists()
