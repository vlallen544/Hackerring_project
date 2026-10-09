# Building Agentic AI Systems, 2nd Edition (2025) – Selected Chapters

## Chapter 2: Context Windows and Context Engineering
Context windows of current models range from about 128,000 tokens to more than one million tokens.
A long context window does not remove the need to manage context, because every extra token adds cost and latency.
Context engineering means deciding exactly which instructions, documents and tool results the model sees at each step.

---page---

## Chapter 4: Tool Calling
Modern models support native tool calling, also called function calling.
In native tool calling, each tool is described with a name, a description and a JSON schema for its arguments.
The model returns a structured tool call that matches the schema, so the application no longer needs to parse free text.
Structured outputs force the model's reply to follow a given JSON schema, which makes agents far more reliable.

## Chapter 5: The Model Context Protocol (MCP)
The Model Context Protocol (MCP) is an open standard, introduced by Anthropic in November 2024, for connecting AI applications to tools and data sources.
An MCP server exposes tools, resources and prompts; any MCP-compatible client can use them without custom integration code.

---page---

## Chapter 7: Agent Loops and Reliability
The reason-act-observe loop (ReAct) remains the basic pattern of an agent.
Production agents add limits on steps, time and cost, and retry failed tool calls with backoff.

## Chapter 8: Evaluation and Observability
Agents are evaluated on fixed test sets of tasks, and the results are compared after every change to prompts, tools or models.
Tracing records every model call and tool call of an agent run, so failures can be found and debugged.

## Chapter 9: Guardrails
Prompt injection is the most common attack on agents that read untrusted content.
Irreversible or high-impact actions require explicit human approval (human-in-the-loop).
