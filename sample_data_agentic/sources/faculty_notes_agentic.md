# Agentic AI Systems – Lecture Notes, Units 1 to 5 (Prepared by Dr. K. Menon, 2023)

## 1. How Large Language Models Work
A large language model (LLM) generates text by predicting the next token, one token at a time.
A token is a piece of a word; on average one English word is about one and a third tokens.
The context window is the maximum number of tokens the model can read at once, including the prompt and its own reply.
LLM context windows are about 4,000 tokens, so an agent must summarise its history after every few steps.
Temperature controls randomness: a low temperature gives more predictable answers.

## 2. Prompting
A system prompt sets the role, rules and output format for the whole conversation.
Few-shot prompting gives the model a few worked examples of the task before the real input.
Chain-of-thought prompting asks the model to reason step by step before giving the final answer.

---page---

## 3. Tool Use
An agent becomes useful when the model can call tools such as a search engine, a calculator or a database.
Tool use is done by asking the model to write the tool name and arguments in plain text, and then parsing that text with regular expressions.
The result of each tool call is added back into the prompt so the model can use it.

## 4. The Agent Loop
An agent works in a loop: it reasons about the goal, chooses an action, observes the result, and repeats.
This reason-act-observe pattern is called ReAct.
An agent loop must have a stopping condition, such as a maximum number of steps, or it can run forever.

---page---

## 5. Memory and Retrieval-Augmented Generation (RAG)
Short-term memory is the conversation inside the context window; long-term memory is stored outside the model.
Retrieval-augmented generation (RAG) retrieves relevant documents and adds them to the prompt before the model answers.
Documents are split into chunks and turned into embeddings, which are vectors that capture meaning.
Similar chunks are found by comparing embeddings, for example with cosine similarity.

## 6. Multi-Agent Systems
In an orchestrator-worker design, one agent splits a task into parts and hands each part to a worker agent.
Each worker should have a narrow role and only the tools it needs.

---page---

## 7. Evaluation
An agent must be tested on a fixed set of example tasks with known good outcomes before it is used.
A stronger model can be used as a judge to grade answers, but its grades must be checked against human ratings.

## 8. Safety
Prompt injection is when text inside a document or web page tries to give the agent new instructions.
An agent must ask a human for approval before an action that cannot be undone, such as sending money or deleting data.
Every tool call an agent makes should be logged so that its behaviour can be audited later.
