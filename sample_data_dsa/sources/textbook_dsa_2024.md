# Algorithms and Data Structures in Practice, 2nd Edition (2024) – Selected Excerpts

## Chapter 2: Complexity and Dynamic Arrays
Appending to a dynamic array takes amortized O(1) time, because the array occasionally doubles its capacity.
A hash table gives O(1) lookup on average, but the worst case is O(n) when many keys collide into the same bucket.
Since Python 3.7, dictionaries are guaranteed to preserve insertion order as part of the language specification.

## Chapter 4: Sorting in Practice
Python's built-in sort uses Timsort, which is stable and runs in O(n log n) time in the worst case.
Quicksort degrades to O(n^2) on already sorted input when the first element is always chosen as the pivot; a random pivot avoids this in practice.
Merge sort is stable and guarantees O(n log n), while quicksort is often faster in practice because of cache behaviour, so neither is always faster.

---page---

## Chapter 7: Graph Algorithms
Dijkstra's algorithm with a binary heap runs in O((V + E) log V) time and is only correct when every edge weight is non-negative.
The Bellman-Ford algorithm handles negative edge weights in O(V * E) time and can also detect negative cycles.

## Chapter 9: Dynamic Programming
Dynamic programming solves problems that have overlapping subproblems and optimal substructure.
Memoization stores the results of recursive calls top-down, while tabulation fills a table bottom-up.
The 0/1 knapsack problem and the longest common subsequence problem are classic dynamic programming examples.

## Chapter 10: Array Techniques
The sliding window technique keeps a moving range over an array to solve subarray problems in O(n) time instead of O(n^2).
The two pointers technique moves two indices through a sorted array, for example to find a pair with a given sum in O(n) time.
