# SQL and Databases Knowledge

## Joins
An INNER JOIN returns only rows with matching keys in both tables. A LEFT JOIN returns every row from the left table plus matching rows from the right, with NULL where no match exists. A RIGHT JOIN is the mirror image, and a FULL OUTER JOIN returns all rows from both sides.

## Keys and constraints
A primary key uniquely identifies each row and cannot be NULL. A foreign key references the primary key of another table and enforces referential integrity. UNIQUE, NOT NULL and CHECK constraints keep data valid.

## WHERE versus HAVING
WHERE filters individual rows before grouping and cannot use aggregate functions. HAVING filters groups after GROUP BY and can use aggregates such as COUNT, SUM and AVG. The logical order is FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY.

## Normalization
Normalization organises data into related tables to reduce redundancy and prevent update, insert and delete anomalies. 1NF removes repeating groups, 2NF removes partial dependencies on a composite key and 3NF removes transitive dependencies. Denormalization deliberately adds redundancy to speed up reads in analytics workloads.

## Indexes
An index, commonly a B-tree, allows the database to locate rows without a full table scan and speeds up WHERE, JOIN and ORDER BY. Indexes consume storage and slow down INSERT, UPDATE and DELETE because they must be maintained. Indexing low-selectivity columns, such as a boolean flag, gives little benefit.

## Transactions and ACID
Atomicity means a transaction is all or nothing. Consistency means it moves the database from one valid state to another. Isolation means concurrent transactions do not see each other's partial work. Durability means committed data survives crashes.

## Window functions
Window functions such as ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD and SUM OVER compute values across related rows defined with OVER, PARTITION BY and ORDER BY. Unlike GROUP BY they do not collapse rows, so each input row is kept in the output.

## Subqueries and CTEs
A subquery is a query nested inside another. A common table expression, written with WITH, names a temporary result set that makes complex queries readable and allows recursion.
