# Python Interview Knowledge

## Lists and tuples
Lists are mutable ordered sequences defined with square brackets. Tuples are immutable ordered sequences defined with parentheses. Because a tuple cannot change, it is hashable when all its items are hashable and can be used as a dictionary key or set member. Use a list when the collection will change and a tuple for fixed records such as coordinates.

## Dictionaries and sets
A dictionary stores key-value pairs and offers average O(1) lookup because keys are hashed. Since Python 3.7 dictionaries preserve insertion order. A set stores unique hashable items with average O(1) membership tests, and supports union, intersection and difference.

## Functions, *args and **kwargs
*args collects extra positional arguments into a tuple. **kwargs collects extra keyword arguments into a dictionary. Functions are first-class objects: they can be passed as arguments, returned from other functions and stored in variables. Default argument values are evaluated once at definition time, so never use a mutable default such as a list; use None and create the object inside the function.

## Decorators
A decorator is a callable that takes a function and returns a replacement function, usually a wrapper that adds behaviour such as logging, timing, caching, retries or authentication. The @decorator syntax is shorthand for func = decorator(func). Use functools.wraps inside the wrapper to preserve the original function name and docstring.

## Generators and iterators
An iterator implements __iter__ and __next__. A generator function uses yield to produce values lazily, one at a time, and keeps its local state between calls. Generators save memory for large streams and can be consumed only once. Generator expressions use parentheses, for example (x*x for x in range(10)).

## Equality versus identity
The == operator compares values using __eq__. The is operator compares object identity, meaning whether both names point to the same object. Use is for singletons such as None, and == for comparing values.

## Copying objects
A shallow copy creates a new outer container but shares the inner objects. A deep copy recursively copies everything so the copy is independent. Use copy.copy for shallow and copy.deepcopy for deep copies. Slicing a list and list.copy() make shallow copies.

## Global Interpreter Lock
In CPython the GIL allows only one thread to execute Python bytecode at a time. CPU-bound multi-threaded code therefore does not run in parallel. I/O-bound programs still benefit from threads because the GIL is released during blocking I/O. For CPU-bound work use the multiprocessing module, native extensions or asyncio for concurrent I/O.

## Memory management
CPython manages a private heap. The main mechanism is reference counting: when an object's count drops to zero it is freed immediately. A cyclic garbage collector, organised in generations, finds and frees reference cycles that reference counting cannot. Small objects are handled by a pool allocator called pymalloc.

## Context managers
A context manager implements __enter__ and __exit__, or is built with the contextlib.contextmanager decorator. The with statement guarantees that __exit__ runs even if an exception is raised, so files, locks and database connections are released reliably.

## Exceptions
Use try, except, else and finally. else runs when no exception occurred and finally always runs. Catch specific exception types rather than a bare except, and raise custom exceptions to signal domain errors.

## Object oriented programming in Python
Classes support encapsulation, inheritance and polymorphism. Python uses duck typing: an object is valid if it has the needed methods. Dunder methods such as __init__, __str__, __repr__ and __len__ customise behaviour. Use dataclasses to reduce boilerplate for data holders.
