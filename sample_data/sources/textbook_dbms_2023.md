# Database Systems: Concepts and Practice (3rd Edition, 2023) – Selected Excerpts

## Chapter 4: Integrity Constraints
Relational systems enforce domain, entity and referential integrity.
Since MySQL 8.0.16, CHECK constraints are enforced, so a row that violates a CHECK condition is rejected.
Older MySQL versions parsed CHECK constraints but silently ignored them.

Example:
CREATE TABLE STUDENT (roll_no INT PRIMARY KEY, cgpa DECIMAL(3,1) CHECK (cgpa BETWEEN 0 AND 10));

---page---

## Chapter 6: Aggregation and Grouping
WHERE filters individual rows before any grouping happens.
HAVING filters groups after aggregate functions are computed.
A common mistake is to use an aggregate function such as AVG inside a WHERE clause, which is not allowed.

## Chapter 7: Joins
Joins combine rows from two or more tables based on a related column, usually a foreign key matching a primary key.
A self join joins a table to itself, for example to find employees and their managers.

---page---

## Chapter 8: Common Table Expressions
A Common Table Expression (CTE) is a named temporary result defined with the WITH keyword.
CTEs make complex queries easier to read than deeply nested subqueries.
WITH dept_avg AS (SELECT dept, AVG(cgpa) AS avg_cgpa FROM STUDENT GROUP BY dept)
SELECT * FROM dept_avg WHERE avg_cgpa > 8;

## Chapter 9: Window Functions
Window functions perform calculations across a set of rows related to the current row without collapsing them into groups.
MySQL supports window functions from version 8.0 onwards, and PostgreSQL has supported them for many years.
Common window functions include ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD and running SUM.
SELECT name, dept, cgpa, RANK() OVER (PARTITION BY dept ORDER BY cgpa DESC) AS dept_rank FROM STUDENT;
Window functions require a solid understanding of aggregation and GROUP BY.

---page---

## Chapter 10: Normalization
BCNF is a stronger form of 3NF. A relation in BCNF is always in 3NF, but a relation in 3NF is not necessarily in BCNF.

## Chapter 12: Query Performance
An index on a column used in WHERE or JOIN conditions can greatly reduce query time.
Use EXPLAIN to see how the database executes a query.