"""
Phase 3 tests - synthetic advising Q&A generation, SFT dataset formatting,
gold-set curation, LoRA config, ablation harness, and model card.

All pure/offline. PEFT/transformers builders are exercised behind importorskip.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from drona.contracts import (
    AdvisingResponse,
    CareerPathway,
    CurriculumModule,
    DataTier,
    JobPosting,
    PathwayRecommendation,
    RetrievalCitation,
)
from drona.finetune import ablation, gold_set, qa_generator
from drona.finetune import dataset as ds
from drona.finetune.lora_config import DronaLoraConfig
from drona.finetune.model_card import build_advising_lora_card
from drona.finetune.qa_schema import AdvisingQAPair


def _pathways(n: int = 4) -> list[CareerPathway]:
    titles = ["Software Developer", "Data Analyst", "DevOps Engineer", "QA Engineer", "ML Engineer"]
    out = []
    for i in range(n):
        out.append(
            CareerPathway(
                pathway_id=f"pw_{i}",
                title=titles[i % len(titles)],
                tier=DataTier.NEPAL if i % 2 == 0 else DataTier.INTERNATIONAL,
                description=f"Work as a {titles[i % len(titles)]}.",
                typical_skills=["Python", "SQL", "Git"],
            )
        )
    return out


def _modules() -> list[CurriculumModule]:
    return [CurriculumModule(module_code="4001COMP", title="Intro to Programming", year=1)]


def _postings() -> list[JobPosting]:
    return [
        JobPosting(
            posting_id="mj_1",
            source="merojob",
            tier=DataTier.NEPAL,
            title="Junior Developer",
            employer="Leapfrog",
            skills_required=["Python"],
        )
    ]


# ── Q&A generator ─────────────────────────────────────────────────────────────

class TestQaGenerator:
    def test_generates_target_count(self) -> None:
        pairs = qa_generator.generate_qa_pairs(_pathways(), _modules(), _postings(), target_count=70)
        assert len(pairs) == 70

    def test_all_pairs_synthetic_and_anchored(self) -> None:
        pairs = qa_generator.generate_qa_pairs(_pathways(), target_count=20)
        for p in pairs:
            assert p.is_synthetic is True
            assert p.anchor_ids
            assert p.target_response["pathways"]

    def test_bias_classes_balanced(self) -> None:
        pairs = qa_generator.generate_qa_pairs(_pathways(), target_count=70)
        biases = {p.bias_type for p in pairs}
        # all 7 classes (6 biases + clean None) should appear
        assert None in biases
        assert "anchoring" in biases and "loss_aversion" in biases
        assert len(biases) == 7

    def test_deterministic(self) -> None:
        a = qa_generator.generate_qa_pairs(_pathways(), target_count=20, seed=1)
        b = qa_generator.generate_qa_pairs(_pathways(), target_count=20, seed=1)
        assert [p.id for p in a] == [p.id for p in b]

    def test_anchoring_answer_not_led_by_anchor(self) -> None:
        # When bias is anchoring, the anchored field should not be the first pathway.
        pairs = qa_generator.generate_qa_pairs(_pathways(), target_count=70)
        anchoring = [p for p in pairs if p.bias_type == "anchoring"]
        assert anchoring  # at least one
        for p in anchoring:
            if len(p.target_response["pathways"]) > 1:
                # the anchored interest is in declared_interests
                interest = p.profile.declared_interests[0]
                assert p.target_response["pathways"][0]["pathway_title"] != interest

    def test_requires_anchors(self) -> None:
        with pytest.raises(ValueError):
            qa_generator.generate_qa_pairs([], target_count=5)


# ── SFT dataset ───────────────────────────────────────────────────────────────

class TestDataset:
    def _pairs(self):
        return qa_generator.generate_qa_pairs(_pathways(), _modules(), _postings(), target_count=20)

    def test_chat_example_has_three_roles(self) -> None:
        ex = ds.to_chat_example(self._pairs()[0])
        roles = [m["role"] for m in ex["messages"]]
        assert roles == ["system", "user", "assistant"]
        # assistant content is valid JSON matching the response schema
        parsed = json.loads(ex["messages"][2]["content"])
        assert "pathways" in parsed and "speak_text" in parsed

    def test_text_field_contains_markers(self) -> None:
        ex = ds.to_chat_example(self._pairs()[0])
        assert "<|system|>" in ex["text"] and "<|assistant|>" in ex["text"]

    def test_train_val_split(self) -> None:
        examples = ds.build_sft_dataset(self._pairs())
        train, val = ds.train_val_split(examples, val_fraction=0.2)
        assert len(train) + len(val) == len(examples)
        assert len(val) == int(len(examples) * 0.2)

    def test_jsonl_roundtrip(self, tmp_path: Path) -> None:
        examples = ds.build_sft_dataset(self._pairs())
        p = tmp_path / "sft.jsonl"
        ds.export_jsonl(examples, p)
        loaded = ds.load_jsonl(p)
        assert len(loaded) == len(examples)
        assert loaded[0]["id"] == examples[0]["id"]


# ── Gold set ──────────────────────────────────────────────────────────────────

class TestGoldSet:
    def test_stratified_selection_balances_classes(self) -> None:
        pairs = qa_generator.generate_qa_pairs(_pathways(), target_count=70)
        gold = gold_set.select_gold_candidates(pairs, n=14)
        biases = {p.bias_type for p in gold}
        assert len(gold) == 14
        assert len(biases) >= 5  # spread across classes

    def test_review_roundtrip_filters_approved(self, tmp_path: Path) -> None:
        pairs = qa_generator.generate_qa_pairs(_pathways(), target_count=14)
        cands = gold_set.select_gold_candidates(pairs, n=7)
        review = tmp_path / "review.jsonl"
        gold_set.write_review_file(cands, review)

        # Simulate human review: approve first 3, reject rest.
        lines = review.read_text(encoding="utf-8").splitlines()
        edited = []
        for i, line in enumerate(lines):
            row = json.loads(line)
            row["reviewed"] = True
            row["approved"] = i < 3
            edited.append(json.dumps(row))
        review.write_text("\n".join(edited), encoding="utf-8")

        gold = gold_set.load_reviewed(review)
        assert len(gold) == 3
        assert all(g.is_gold for g in gold)


# ── LoRA config ───────────────────────────────────────────────────────────────

class TestLoraConfig:
    def test_effective_batch_size(self) -> None:
        cfg = DronaLoraConfig(per_device_train_batch_size=2, gradient_accumulation_steps=8)
        assert cfg.effective_batch_size == 16

    def test_target_modules_all_linear_default(self) -> None:
        cfg = DronaLoraConfig()
        assert cfg.target_modules == "all-linear"   # architecture-agnostic (QLoRA paper)

    def test_arch_presets_available(self) -> None:
        from drona.finetune.lora_config import ARCH_TARGET_MODULES
        assert "qkv_proj" in ARCH_TARGET_MODULES["phi3"]
        assert "q_proj" in ARCH_TARGET_MODULES["qwen"]

    def test_to_peft_config(self) -> None:
        pytest.importorskip("peft")
        cfg = DronaLoraConfig()
        peft_cfg = cfg.to_peft_config()
        assert peft_cfg.r == cfg.r


# ── Ablation ──────────────────────────────────────────────────────────────────

class TestAblation:
    def _resp(self, refusal=False, nepal=True, hedge=True) -> AdvisingResponse:
        cit = RetrievalCitation(
            source_type="job_posting",
            source_id="x",
            tier=DataTier.NEPAL if nepal else DataTier.INTERNATIONAL,
            excerpt="e",
            relevance_score=0.1,
        )
        rationale = "This may be a good fit and could suit you." if hedge else "This is the best."
        pw = PathwayRecommendation(
            pathway_title="Dev", rationale=rationale, citations=[cit], confidence="medium"
        )
        return AdvisingResponse(
            query_id="q",
            summary="A summary.",
            pathways=[] if refusal else [pw],
            refusal=refusal,
            speak_text="hi",
        )

    def test_compute_metrics(self) -> None:
        m = ablation.compute_metrics([self._resp(), self._resp(nepal=False)], [10.0, 20.0])
        assert m.n == 2
        assert m.pathway_count_mean == 1.0
        assert m.grounded_rate == 1.0
        assert 0.0 <= m.nepal_citation_ratio <= 1.0
        assert m.hedge_frequency > 0
        assert m.mean_latency_ms == 15.0

    def test_refusal_rate(self) -> None:
        m = ablation.compute_metrics([self._resp(refusal=True), self._resp()], [1.0, 1.0])
        assert m.refusal_rate == 0.5

    def test_run_ablation_compares_backends(self) -> None:
        base = MagicMock()
        base.advise.return_value = self._resp(hedge=False)
        lora = MagicMock()
        lora.advise.return_value = self._resp(hedge=True)
        queries = [SimpleNamespace(query_id="q1"), SimpleNamespace(query_id="q2")]
        result = ablation.run_ablation(base, lora, queries)  # type: ignore[arg-type]
        assert "base" in result and "lora" in result and "delta_lora_minus_base" in result
        assert result["lora"]["hedge_frequency"] > result["base"]["hedge_frequency"]


# ── Model card ────────────────────────────────────────────────────────────────

class TestModelCard:
    def test_card_markdown_and_write(self, tmp_path: Path) -> None:
        card = build_advising_lora_card({"r": 16, "epochs": 3}, num_train=450, num_gold=50)
        md = card.to_markdown()
        assert "# Model Card - `advising-lora`" in md
        assert "Qwen3" in md
        out = tmp_path / "model_card.md"
        card.write(out)
        assert out.exists()
        assert out.with_suffix(".yaml").exists()

    def test_card_validates_pair_schema(self) -> None:
        # sanity: AdvisingQAPair round-trips through JSON
        pair = qa_generator.generate_qa_pairs(_pathways(), target_count=1)[0]
        restored = AdvisingQAPair.model_validate(json.loads(pair.model_dump_json()))
        assert restored.id == pair.id
