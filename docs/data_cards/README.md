# Data Cards - D.R.O.N.A.

One card per dataset used by the system. Each card records provenance, license,
tier, collection method, schema, and limitations. Machine-readable YAML cards are
emitted next to processed artefacts by `drona.data_pipeline.data_card.DataCard`;
these Markdown cards are the human-facing thesis references.

| Dataset | Tier | License | Card |
|---|---|---|---|
| O\*NET 30.3 | international | CC BY 4.0 | [onet.md](./onet.md) |
| ESCO v1.2.1 | regional/intl | CC BY 4.0 | [esco.md](./esco.md) |
| BLS OEWS May 2025 | international | US public domain | [bls_oews.md](./bls_oews.md) |
| NLFS 2017/18 | nepal | public (NSO Nepal) | [nlfs.md](./nlfs.md) |
| Nepali job postings | nepal | manual; see card | [nepali_job_postings.md](./nepali_job_postings.md) |
| Softwarica curriculum | nepal | college materials | [curriculum.md](./curriculum.md) |
| Synthetic advising Q&A | synthetic | MIT (ours) | [synthetic_qa.md](./synthetic_qa.md) |

See also [`../data_ethics.md`](../data_ethics.md) for the licensing matrix and PII policy.
