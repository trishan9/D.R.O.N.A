"""D.R.O.N.A. data pipeline.

Workstream 1 (WS1) — all data flows through here before hitting ChromaDB.

Sub-modules:
  curriculum    — parse Softwarica module descriptor documents
  onet          — download + parse O*NET 30.3 bulk database
  ingest        — dual-embedding ChromaDB ingestion (C1 contribution)
  data_card     — provenance records for every dataset produced
  scrapers/     — portal-specific scrapers + manual JSON loader
"""
