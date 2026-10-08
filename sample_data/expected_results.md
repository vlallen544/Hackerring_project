# Expected Results (answer key for testing agents)

## Conflicts the Reconciler must find
1. CHECK constraints: Notes 2019 (ignored) vs Textbook 2023 (enforced since 8.0.16) → Textbook wins (newer, more specific)
2. Window functions: Notes 2019 (unsupported) vs Textbook 2023 + both JDs → Textbook wins (newer, 3 sources agree)
3. 3NF vs BCNF: Blog 2016 (same) vs Notes + Textbook (BCNF stricter) → Notes + Textbook win (authority, 2 sources agree)
4. "Subqueries always faster than joins": Blog 2016 → flagged unreliable (absolute claim, low authority, old)

## Syllabus gaps (in JDs, missing from faculty notes)
CTEs, window functions, EXPLAIN / query performance, self join

## Prerequisite chain
Relational Model → Keys → Constraints
Keys → Joins → Subqueries → CTEs → Window Functions
SELECT & WHERE → Aggregation (GROUP BY/HAVING) → Window Functions
Keys → Functional Dependencies → Normalization
SELECT & WHERE → Indexing

## Faculty voice brief (read aloud in demo)
"I'm teaching DBMS to third-year CSE, around 60 students. Four weeks before the December
placement drive. Many students aren't confident in English, some prefer Hindi.
Focus on what Data Analyst roles need."