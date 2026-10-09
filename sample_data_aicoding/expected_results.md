# Expected Results – AI-Assisted Software Engineering course (answer key for testing agents)

## Conflicts the Reconciler should find
1. What assistants can do: Notes 2023 ("only complete the current line or function; cannot edit several files or run commands") vs Textbook 2025 + AI-Native SWE JD (coding agents edit many files, run commands and tests)
   -> outdated; Textbook + JD win (newer, more sources agree)
2. Testing: Blog 2025 ("if the app runs, the code is correct; tests are a waste of time") vs Notes 2023 + Textbook 2025 + both JDs (tests and CI required)
   -> Notes + Textbook + JDs win (authority, several sources agree)
3. Reviewing: Blog 2025 ("always accept every change") vs Notes 2023 + Textbook 2025 + SWE JD (review every diff)
   -> Notes + Textbook + JD win
4. "Pasting API keys into the chat is safe": Blog 2025 -> unreliable (Notes: never paste secrets; DevProd JD: secret scanning)
5. "A suggested package always exists and is safe": Blog 2025 -> unreliable (Notes + Textbook: package hallucination / slopsquatting)

## Syllabus gaps (in JDs, missing from faculty notes)
Missing: spec-driven agent workflows and project instruction files, measuring productivity (lead time, change failure rate), least-privilege agents
Outdated: what AI coding tools can do (autocomplete only vs coding agents)
Covered: reviewing AI code, testing in CI, secrets and package checks, small commits, responsible use

## Prerequisite chain (expected, roughly)
AI coding assistants -> Prompting for code -> Reviewing AI-generated code -> Testing
Reviewing -> Security ; Testing -> Version control ; all -> Responsible use
