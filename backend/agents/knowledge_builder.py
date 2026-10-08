# Knowledge Builder agent: extracts concepts, source-cited claims and the prerequisite graph
import json
from pathlib import Path

import networkx as nx

from backend.models import KnowledgeExtraction
from backend.tools.agnes_client import chat_json
from backend.tools.parsers import chunks_to_prompt, load_sources
from backend.tools.verify import find_quote_anywhere, quote_exists

OUTPUT_FILE = Path("data/knowledge_base.json")

SYSTEM_PROMPT = """You are the Knowledge Builder agent of VidyaPath, a learning platform for college faculty.
You receive ALL of a course's teaching material at once: faculty notes, textbook excerpts, web articles
and industry job descriptions. Each page starts with a header like <<SOURCE some_id | PAGE 2>>.

Your job is to extract three things.

1. CONCEPTS (8 to 15): the teachable topics in this material, e.g. keys, joins, window_functions.
   - Give each a short snake_case id.
   - Use the SAME id for the same idea in every source, so claims from different sources link together.

2. CLAIMS: every factual statement a student might learn or be tested on.
   - Include claims about software support and versions (e.g. what MySQL does or does not support).
   - Include every skill requirement from job descriptions with claim_type "requirement".
   - Include claims EVEN IF you think they are wrong, outdated or contradict another source.
     Do NOT correct them and do NOT skip them. Another agent will judge which claims to trust.
   - "quote" must be copied EXACTLY, word for word, from ONE page: 8 to 30 consecutive words.
     No paraphrasing, no "...", no joining text from two places.
   - "source_id" and "page" must come from the header of the page the quote is on.
   - Aim for 3 to 6 claims per page.

3. PREREQUISITES: which concept must be understood before another.
   - Only direct prerequisites (if A -> B and B -> C, do not add A -> C).
   - No cycles.
"""

def build_knowledge(data_dir="sample_data"):
    meta, chunks = load_sources(data_dir)
    print(f"Loaded {len(meta['sources'])} sources, {len(chunks)} pages. Calling Agnes (one large-context call)...")

    extraction = chat_json(SYSTEM_PROMPT, chunks_to_prompt(chunks), KnowledgeExtraction)

    # ---- 1. Concepts ----
    concepts = {c.id: c.model_dump() for c in extraction.concepts}

    # ---- 2. Verify every claim's quote against the real source text ----
    verified, rejected = [], []
    for n, claim in enumerate(extraction.claims, start=1):
        c = claim.model_dump()
        c["id"] = f"claim_{n}"
        if c["concept_id"] not in concepts:
            rejected.append({**c, "reject_reason": "unknown concept"})
        elif quote_exists(c["quote"], c["source_id"], c["page"], chunks):
            verified.append(c)
        elif (found := find_quote_anywhere(c["quote"], chunks)):
            c["source_id"], c["page"] = found  # model cited the wrong page: fix it
            c["page_corrected"] = True
            verified.append(c)
        else:
            rejected.append({**c, "reject_reason": "quote not found in source"})

    # ---- 3. Prerequisite graph (must be a DAG: no cycles) ----
    graph = nx.DiGraph()
    graph.add_nodes_from(concepts)
    for p in extraction.prerequisites:
        if p.before in concepts and p.after in concepts and p.before != p.after:
            graph.add_edge(p.before, p.after, reason=p.reason)

    removed_edges = []
    while not nx.is_directed_acyclic_graph(graph):
        u, v = nx.find_cycle(graph)[-1][:2]   # break the cycle by dropping one edge
        graph.remove_edge(u, v)
        removed_edges.append((u, v))

    knowledge_base = {
        "sources": meta["sources"],
        "authority_defaults": meta["authority_defaults"],
        "concepts": concepts,
        "claims": verified,
        "rejected_claims": rejected,
        "prerequisites": [
            {"before": u, "after": v, "reason": d.get("reason", "")} for u, v, d in graph.edges(data=True)
        ],
        "learning_order": list(nx.topological_sort(graph)),
        "removed_cycle_edges": removed_edges,
    }

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(knowledge_base, indent=2, ensure_ascii=False), encoding="utf-8")
    return knowledge_base