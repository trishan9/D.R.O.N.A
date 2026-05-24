# Mirrors drona.contracts.RetrievalCitation
# One document retrieved from ChromaDB to support a pathway recommendation.

string source_type       # curriculum | job_posting | career_pathway | onet
string source_id         # UUID or document identifier
string tier              # nepal | regional | international | synthetic
string excerpt           # relevant passage (max 300 chars)
float32 relevance_score  # reranker score [0, 1]
