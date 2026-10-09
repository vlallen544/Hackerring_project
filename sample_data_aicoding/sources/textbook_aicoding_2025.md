# Software Engineering with AI Agents (2025) – Selected Chapters

## Chapter 1: From Autocomplete to Coding Agents
Coding agents go beyond autocomplete: they read a whole repository, edit many files, run commands and tests, and fix their own errors.
A coding agent works in a loop of planning, editing, running the tests and reading the results.
"Vibe coding" is a term coined by Andrej Karpathy in February 2025 for building software by describing it in natural language and accepting the AI's code without reading it closely.
Vibe coding is useful for quick prototypes and throwaway tools, but code that goes to production needs review and tests.

---page---

## Chapter 3: Context and Specifications
Agents produce better code when they are given a written specification and a plan before they start.
Many teams keep a project instruction file in the repository that tells coding agents the commands, conventions and rules of the project.

## Chapter 5: Verifying AI-Generated Code
Running the code once does not show that it is correct; automated tests and code review are still required.
Continuous integration should run tests, linters and secret scanning on every AI-assisted change.

---page---

## Chapter 6: Security Risks
Package hallucination is when an assistant suggests a package that does not exist; attackers can publish malicious packages under those names, which is called slopsquatting.
A coding agent that reads untrusted text, such as issues or web pages, can be manipulated by prompt injection.
Agents should run with the least privileges needed and must not have access to production secrets.

## Chapter 8: Measuring Productivity
Teams measure AI-assisted development with delivery metrics such as lead time, change failure rate and review time, not only with lines of code written.
