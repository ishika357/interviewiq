# Data Structures and Algorithms Knowledge

## Big-O notation
Big-O describes how running time or memory grows with input size in the worst case, ignoring constant factors. Common classes in increasing cost are O(1), O(log n), O(n), O(n log n), O(n squared) and O(2 to the n). It lets you compare algorithms and predict how they scale.

## Arrays and linked lists
Arrays store elements contiguously, which gives O(1) access by index but O(n) insertion or deletion in the middle. A linked list stores nodes with pointers to the next node, so insertion or deletion is O(1) once the node is located, but access by index is O(n).

## Stacks and queues
A stack is last-in first-out with push and pop on one end; it is used for undo, expression evaluation and recursion. A queue is first-in first-out with enqueue at the rear and dequeue at the front; it is used for scheduling and breadth-first search.

## Hash tables
A hash function maps a key to a bucket index, giving average O(1) insert, lookup and delete. A collision happens when two keys map to the same bucket. Chaining stores colliding items in a list per bucket; open addressing probes for another free slot. Resizing when the load factor grows keeps operations fast.

## Binary search
Binary search works on sorted data with random access. It compares the target with the middle element and discards half of the range each step, giving O(log n) time and O(1) extra space.

## Trees and graphs
A binary search tree keeps smaller keys on the left and larger keys on the right, giving O(log n) operations when balanced. A graph has vertices and edges and is stored as an adjacency list or matrix.

## BFS and DFS
Breadth-first search visits a graph level by level using a queue and finds shortest paths in unweighted graphs. Depth-first search goes as deep as possible using a stack or recursion and is used for cycle detection, topological sorting and backtracking. Both run in O(V+E) with an adjacency list.

## Sorting
Merge sort and heap sort run in O(n log n) in the worst case. Quick sort averages O(n log n) but is O(n squared) in the worst case. Merge sort is stable and needs O(n) extra space.

## Dynamic programming
Dynamic programming applies to problems with overlapping subproblems and optimal substructure. Store sub-results with memoization (top-down) or tabulation (bottom-up) to avoid recomputation. Examples include Fibonacci numbers, the knapsack problem and the longest common subsequence.

## Two pointers and sliding window
Two pointers walk through a sorted or linear structure from one or both ends to solve pair problems in O(n). A sliding window maintains a running value over a moving range, which avoids recomputing sums for each window.
