# AI-Assisted Software Engineering – Lecture Notes, Units 1 to 5 (Prepared by Prof. N. Iyer, 2023)

## 1. AI Coding Assistants
An AI coding assistant is a tool, built on a large language model, that suggests or writes code inside the developer's editor.
AI coding assistants only complete the current line or function; they cannot edit several files or run commands.
The developer is always responsible for the code that is committed, whoever or whatever wrote it.

## 2. Prompting for Code
A good coding prompt states the goal, the language and framework, the inputs and outputs, and any constraints.
Giving the assistant a short example of the existing code style improves the result.
Large tasks should be split into small steps, and each step checked before the next one.

---page---

## 3. Reviewing AI-Generated Code
AI-generated code must be reviewed like code from an unknown contributor.
Read every line of the diff before accepting it, and ask the assistant to explain anything unclear.
Common problems in AI-generated code are wrong edge cases, outdated library APIs and invented functions that do not exist.

## 4. Testing
AI-generated code must be covered by tests before it is merged.
An assistant can draft unit tests, but a developer must check that the tests really test the intended behaviour.
Tests should be run in continuous integration (CI) on every change.

---page---

## 5. Security
Never paste passwords, API keys or customer data into a prompt.
Check that every package an assistant suggests really exists and is the official one before installing it.
AI-generated code can contain security bugs such as SQL injection, so it needs the same security review as any other code.

## 6. Version Control
Keep AI-assisted changes small, with one purpose per commit, so they are easy to review and to undo.
Write the commit message yourself so that it explains why the change was made.

---page---

## 7. Responsible Use
Follow the organisation's policy on which AI tools may be used with its code.
Check the licence of any code that looks copied from another project.
