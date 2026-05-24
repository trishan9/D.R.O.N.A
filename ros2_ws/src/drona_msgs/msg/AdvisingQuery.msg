# Mirrors drona.contracts.AdvisingQuery
# Student query submitted to the advising engine.

string query_id              # UUID assigned by orchestrator
string query_text            # raw student question
int32  year_of_study         # 1-4 (0 = unknown)
string[] completed_modules   # e.g. ["4001COMP", "4002COMP"]
string[] declared_skills     # e.g. ["python", "sql"]
string geography_preference  # nepal | regional | international | any
int32  max_pathways          # 2-5
