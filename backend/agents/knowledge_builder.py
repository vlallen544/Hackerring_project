# Knowledge Builder agent: extracts concepts, source-cited claims and the prerequisite graph
import json
from datetime import datetime
from pathlib import Path

import networkx as nx

from backend import courses
from backend.models import KnowledgeExtraction, PrerequisiteMap
from backend.tools import llm
from backend.tools.llm import heavy_json, heavy_model, heavy_provider
from backend.tools.parsers import chunks_to_prompt, file_sha256, load_sources
from backend.tools.verify import find_quote_anywhere, quote_exists

# Everything goes into ONE extraction call, so the input is capped (larger books need a page range).
# Claude reads much more per call than Agnes.
MAX_BUILD_WORDS = {"claude": 80000, "agnes": 20000}

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

PREREQ_PROMPT = """You are the curriculum designer of VidyaPath. You get the list of concepts in one course,
in the order the course material presents them, with a description and a few facts about each.

For EVERY concept, list its DIRECT prerequisites: the other concepts from this list that a student must
already understand to learn it properly. Go through the concepts one by one; do not skip any.
- Use only ids from the list. Never list a concept as its own prerequisite.
- Direct only: if A is needed for B and B for C, list A under B and B under C, not A under C.
- Think about what each concept is BUILT ON (e.g. a structure built from another structure, an algorithm that
  uses a structure, a technique that applies an earlier technique).
- Only the truly foundational concepts should have an empty list; in a typical course most concepts need 1-2.
- Never create a cycle.
"""


def _map_prerequisites(concepts, claims):
    """Second, focused call: one prerequisite entry per concept (much more complete than the extraction pass)."""
    facts = {}
    for c in claims:
        facts.setdefault(c["concept_id"], [])
        if len(facts[c["concept_id"]]) < 3:
            facts[c["concept_id"]].append(c["statement"])
    payload = [{"id": cid, "name": c["name"], "description": c["description"], "facts": facts.get(cid, [])}
               for cid, c in concepts.items()]
    return heavy_json(PREREQ_PROMPT, "CONCEPTS:\n" + json.dumps(payload, ensure_ascii=False, indent=1), PrerequisiteMap)


def build_knowledge(data_dir="sample_data"):
    meta, chunks = load_sources(data_dir)
    total_words = sum(len(c.text.split()) for c in chunks)
    limit = MAX_BUILD_WORDS[heavy_provider()]
    if total_words > limit:
        sizes = {}
        for c in chunks:
            sizes[c.source_id] = sizes.get(c.source_id, 0) + len(c.text.split())
        biggest = max(sizes, key=sizes.get)
        raise ValueError(f"The sources contain {total_words:,} words; the limit is {limit:,}. "
                         f"Set a page range on the largest source ({biggest}: {sizes[biggest]:,} words) "
                         f"so only the chapters you teach are used.")
    print(f"Loaded {len(meta['sources'])} sources, {len(chunks)} pages. Calling {heavy_model()} (one large-context call)...")  # may fall back to Agnes

    extraction = heavy_json(SYSTEM_PROMPT, chunks_to_prompt(chunks), KnowledgeExtraction)
    extracted_with = llm.last_model  # may be Agnes if Claude was unavailable
    print(f"Extraction answered by {extracted_with}.")

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
    # Edges from the focused prerequisite pass, plus any extra ones the extraction pass found
    print("Mapping prerequisites for every concept (focused call)...")
    prereq_map = _map_prerequisites(concepts, verified)
    candidates = [(n, c.concept_id, c.reason) for c in prereq_map.concepts for n in c.needs]
    candidates += [(p.before, p.after, p.reason) for p in extraction.prerequisites]
    graph = nx.DiGraph()
    graph.add_nodes_from(concepts)
    for before, after, reason in candidates:
        if before in concepts and after in concepts and before != after and not graph.has_edge(before, after):
            graph.add_edge(before, after, reason=reason)

    removed_edges = []
    while not nx.is_directed_acyclic_graph(graph):
        u, v = nx.find_cycle(graph)[-1][:2]   # break the cycle by dropping one edge
        graph.remove_edge(u, v)
        removed_edges.append((u, v))

    # Keep only DIRECT prerequisites: drop A->C when A->B->C already exists
    reduced = nx.transitive_reduction(graph)
    reduced.add_nodes_from(graph.nodes)
    reduced.add_edges_from((u, v, graph.edges[u, v]) for u, v in reduced.edges)
    graph = reduced

    # Learning order: prerequisites first; otherwise follow the order the course material introduces concepts
    # (claims are in reading order: sources in order, pages in order), falling back to the extraction order
    first_seen = {cid: len(verified) + i for i, cid in enumerate(concepts)}
    for i, c in enumerate(verified):
        first_seen[c["concept_id"]] = min(first_seen[c["concept_id"]], i)
    learning_order = list(nx.lexicographical_topological_sort(graph, key=lambda c: first_seen[c]))

    knowledge_base = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "extracted_with": extracted_with,
        # file fingerprints, so the platform can tell which sources are new or changed since this build
        "built_from": {src["id"]: file_sha256(Path(data_dir) / src["file"]) for src in meta["sources"]},
        "sources": meta["sources"],
        "authority_defaults": meta["authority_defaults"],
        "concepts": concepts,
        "claims": verified,
        "rejected_claims": rejected,
        "prerequisites": [
            {"before": u, "after": v, "reason": d.get("reason", "")} for u, v, d in graph.edges(data=True)
        ],
        "learning_order": learning_order,
        "removed_cycle_edges": removed_edges,
    }

    output = courses.course_file("knowledge_base.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(knowledge_base, indent=2, ensure_ascii=False), encoding="utf-8")
    return knowledge_base