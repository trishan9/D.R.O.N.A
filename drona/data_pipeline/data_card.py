"""
Data card schema and writer for D.R.O.N.A. datasets.

Every dataset produced by the pipeline gets a YAML data card. The card is the
thesis's primary evidence of responsible data engineering: provenance, license,
collection method, limitations, and synthetic labeling.

Usage:
    card = DataCard(
        name="onet_occupations",
        source_name="O*NET 30.3",
        source_url="https://www.onetcenter.org/database.html",
        license="CC BY 4.0",
        tier="international",
        collection_method="automated_bulk_download",
        ...
    )
    card.write(Path("data/processed/onet_occupations_data_card.yaml"))
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class DataCard(BaseModel):
    """Structured provenance record for one dataset artifact."""

    # Identity
    name: str = Field(description="Machine-readable dataset name (snake_case)")
    version: str = Field(default="1.0.0")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Provenance
    source_name: str = Field(description="Human-readable source name")
    source_url: str | None = Field(default=None)
    license: str = Field(description="SPDX identifier or 'custom - see notes'")
    tier: Literal["nepal", "regional", "international", "synthetic"] = Field(
        description="Data provenance tier (see contracts.DataTier)"
    )

    # Collection
    collection_method: Literal[
        "automated_bulk_download",
        "automated_scrape_public",
        "manual_user_collection",
        "api_official",
        "synthetic_llm",
        "synthetic_rule",
    ] = Field(description="How data was collected")
    collection_date: datetime = Field(default_factory=datetime.utcnow)
    collector: str = Field(default="Trisan Wagle")

    # Content
    record_count: int | None = Field(default=None, description="Row count after cleaning")
    fields: list[str] = Field(default_factory=list, description="Column/field names")
    description: str = Field(default="", description="What is in this dataset")

    # Quality
    known_limitations: list[str] = Field(default_factory=list)
    contains_synthetic: bool = Field(
        default=False,
        description="True if ANY synthetic records are present (they will also be labeled in schema)",
    )
    synthetic_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Fraction of records that are synthetic (if mixed)"
    )

    # Scraping-specific (optional)
    robots_txt_verified: bool | None = Field(
        default=None,
        description="Was robots.txt checked before automated collection?"
    )
    robots_txt_allows_crawl: bool | None = Field(default=None)
    rate_limit_applied: str | None = Field(
        default=None, description="e.g. '0.5 req/s (2s gap)'"
    )

    # Cross-references
    derived_from: list[str] = Field(
        default_factory=list,
        description="Names of upstream DataCard artifacts this depends on"
    )
    output_files: list[str] = Field(
        default_factory=list,
        description="Relative paths of files produced"
    )
    notes: str = Field(default="")

    def write(self, path: Path, also_markdown: bool = True) -> None:
        """Serialise to YAML (machine-readable). Creates parent dirs.

        Also emits a sibling ``<name>_data_card.md`` by default, because the
        build prompt mandates a Markdown ``data_card.md`` per dataset while the
        pipeline standard is YAML - we keep both, generated from one source.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json")
        # Make datetimes human-readable strings
        for key in ("created_at", "collection_date"):
            if data.get(key):
                data[key] = str(data[key])
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        if also_markdown:
            self.write_markdown(path.with_suffix(".md"))

    def write_markdown(self, path: Path) -> None:
        """Write a human-readable Markdown data card."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")

    def to_markdown(self) -> str:
        """Render the card as a Markdown document (for docs / viva evidence)."""
        def _bullets(items: list[str]) -> str:
            return "\n".join(f"- {x}" for x in items) if items else "- (none)"

        lines = [
            f"# Data Card - `{self.name}`",
            "",
            f"**Source:** {self.source_name}"
            + (f" ([link]({self.source_url}))" if self.source_url else ""),
            f"**License:** {self.license}",
            f"**Provenance tier:** `{self.tier}`",
            f"**Collection method:** `{self.collection_method}`  "
            f"**Collected:** {self.collection_date.date()}  **By:** {self.collector}",
            f"**Records:** {self.record_count if self.record_count is not None else 'n/a'}",
            f"**Version:** {self.version}  **Created:** {self.created_at.date()}",
            "",
            "## Description",
            self.description or "_(none)_",
            "",
            "## Fields",
            _bullets(self.fields),
            "",
            "## Known limitations",
            _bullets(self.known_limitations),
            "",
            "## Synthetic content",
            f"- contains_synthetic: **{self.contains_synthetic}**",
            f"- synthetic_fraction: {self.synthetic_fraction if self.synthetic_fraction is not None else 'n/a'}",
            "",
            "## Collection ethics",
            f"- robots.txt verified: {self.robots_txt_verified}",
            f"- robots.txt allows crawl: {self.robots_txt_allows_crawl}",
            f"- rate limit applied: {self.rate_limit_applied or 'n/a'}",
            "",
            "## Outputs",
            _bullets(self.output_files),
        ]
        if self.derived_from:
            lines += ["", "## Derived from", _bullets(self.derived_from)]
        if self.notes:
            lines += ["", "## Notes", self.notes]
        return "\n".join(lines) + "\n"

    @classmethod
    def read(cls, path: Path) -> DataCard:
        with path.open(encoding="utf-8") as f:
            return cls(**yaml.safe_load(f))
