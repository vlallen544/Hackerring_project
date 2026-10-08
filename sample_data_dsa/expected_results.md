# Expected Results – DSA course (answer key for testing agents)

## Conflicts the Reconciler should find
1. Python dict order: Notes 2016 ("do not preserve insertion order") vs Textbook 2024 ("guaranteed since Python 3.7") + Fintech JD
   -> outdated; Textbook wins (newer, more specific, more sources agree)
2. Hash table lookup: Blog 2015 ("always O(1), no matter what") vs Textbook 2024 ("O(1) average, O(n) worst case")
   -> Textbook wins / Blog flagged (absolute claim, low authority, old)
3. Dijkstra and negative weights: Blog 2015 ("works with negative weights") vs Notes 2016 + Textbook 2024 ("requires non-negative")
   -> Notes + Textbook win (authority, two sources agree)
4. "Quicksort is always faster than merge sort": Blog 2015 -> unreliable (Textbook: "neither is always faster")
5. "Recursion is always slower than iteration": Blog 2015 -> flagged unreliable (absolute claim)

## Syllabus gaps (in JDs, missing from faculty notes)
Missing: dynamic programming, sliding window / two pointers
Outdated: Python dictionary ordering
Covered: hashing, trees, graphs (BFS, DFS, shortest paths), heaps / priority queues, complexity

## Prerequisite chain (expected, roughly)
Arrays -> Linked lists ; Arrays -> Sorting -> Binary search ; Arrays -> Sliding window / Two pointers
Recursion -> Trees -> Binary search trees ; Trees -> Heaps
Recursion -> Dynamic programming
Stacks and queues -> Graphs (BFS/DFS) -> Shortest paths ; Heaps -> Shortest paths (Dijkstra)
