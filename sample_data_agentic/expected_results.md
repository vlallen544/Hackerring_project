# Expected Results – Agentic AI Systems course (answer key for testing agents)

## Conflicts the Reconciler should find
1. Context window size: Notes 2023 ("about 4,000 tokens, summarise after every few steps") vs Textbook 2025 (128,000 to over a million tokens)
   -> outdated; Textbook wins (newer, more specific)
2. Tool use: Notes 2023 ("model writes tool calls as text, parsed with regular expressions") vs Textbook 2025 + Agent JD (native tool calling with JSON schemas, structured outputs)
   -> outdated; Textbook + JD win (newer, more sources agree)
3. Autonomy: Blog 2023 ("no need for a human to review") vs Notes 2023 + Textbook 2025 + Agent JD (human approval for irreversible actions)
   -> Notes + Textbook + JD win (authority, three sources agree)
4. "A model must be fine-tuned before it can use any tool": Blog 2023 -> unreliable (Textbook: native tool calling)
5. "RAG always needs a dedicated vector database": Blog 2023 -> flagged unreliable (absolute claim)
6. "AI citations are always real": Blog 2023 -> flagged unreliable (absolute claim)

## Syllabus gaps (in JDs, missing from faculty notes)
Missing: MCP (Model Context Protocol), observability / tracing of agent runs
Outdated: tool calling (text parsing vs native function calling), context window sizes / context engineering
Covered: RAG, agent loop (ReAct), multi-agent orchestration, prompt injection and human approval, evaluation

## Prerequisite chain (expected, roughly)
LLM basics (tokens, context window) -> Prompting -> Tool use -> Agent loop
LLM basics -> RAG (embeddings) ; Agent loop -> Multi-agent systems ; Agent loop -> Evaluation, Safety
