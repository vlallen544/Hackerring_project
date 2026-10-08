# Data Structures and Algorithms – Lecture Notes, Units 1 to 4 (Prepared by Prof. A. Iyer, 2016)

## 1. Arrays and Complexity
An array stores elements in contiguous memory, so any element can be accessed by index in O(1) time.
Inserting or deleting in the middle of an array takes O(n) time because elements must be shifted.
Big-O notation describes how the running time grows as the input size n grows.

## 2. Linked Lists
A singly linked list stores each element in a node that points to the next node.
Inserting at the head of a linked list takes O(1) time, but accessing the k-th element takes O(k) time.

## 3. Stacks and Queues
A stack follows Last In First Out (LIFO) order, with push and pop at the top.
A queue follows First In First Out (FIFO) order, adding at the rear and removing from the front.

---page---

## 4. Recursion
A recursive function calls itself on a smaller input and must have a base case to stop.
Each recursive call uses stack space, so very deep recursion can cause a stack overflow.

## 5. Sorting
Bubble sort and insertion sort take O(n^2) time in the worst case.
Merge sort divides the array into halves, sorts them and merges them, taking O(n log n) time in all cases.
Quicksort takes O(n log n) time on average, but O(n^2) in the worst case when the pivot is chosen badly.

## 6. Binary Search
Binary search works only on a sorted array and repeatedly halves the search range, taking O(log n) time.

---page---

## 7. Hashing
A hash table maps keys to values using a hash function to compute an index.
Python dictionaries are hash tables, and Python dictionaries do not preserve insertion order, so never rely on the order of keys when iterating.

## 8. Trees
A binary tree is a tree in which every node has at most two children.
In a binary search tree, the left subtree holds smaller keys and the right subtree holds larger keys, so an inorder traversal visits keys in sorted order.
Searching a binary search tree takes O(h) time, where h is the height of the tree.

## 9. Heaps
A binary heap is a complete binary tree used to implement a priority queue, with insert and extract-min in O(log n) time.

---page---

## 10. Graphs
A graph can be stored as an adjacency matrix or an adjacency list; adjacency lists use less memory for sparse graphs.
Breadth-first search (BFS) uses a queue and finds the shortest path in an unweighted graph.
Depth-first search (DFS) uses a stack or recursion and is used for cycle detection and topological sorting.

## 11. Shortest Paths
Dijkstra's algorithm finds shortest paths from a source but requires all edge weights to be non-negative.
When a graph has negative edge weights, use the Bellman-Ford algorithm instead.
