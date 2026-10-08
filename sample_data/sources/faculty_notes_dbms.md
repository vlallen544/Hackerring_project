# DBMS Lecture Notes – Unit 2 & 3 (Prepared by Prof. R. Sharma, 2019)

## 1. The Relational Model
A relational database stores data in tables called relations. Each row is a tuple and each column is an attribute. The set of allowed values for an attribute is called its domain.

A relation schema is written as STUDENT(roll_no, name, dept, cgpa).

## 2. Keys
A super key is any set of attributes that uniquely identifies a tuple in a relation.
A candidate key is a minimal super key, meaning no attribute can be removed from it without losing uniqueness.
The primary key is the candidate key chosen by the database designer to identify tuples.
A foreign key is an attribute in one table that refers to the primary key of another table, and it is used to maintain referential integrity.

Example: In ENROLLMENT(roll_no, course_id, grade), roll_no is a foreign key referring to STUDENT.

---page---

## 3. Constraints
SQL supports NOT NULL, UNIQUE, PRIMARY KEY and FOREIGN KEY constraints.
Note for lab: MySQL parses CHECK constraints but ignores them, so CHECK cannot be used to validate data in MySQL. Use triggers instead.

## 4. Basic SQL Queries
SELECT chooses columns, FROM chooses tables and WHERE filters rows.
SELECT name, cgpa FROM STUDENT WHERE dept = 'CSE';

## 5. Aggregation
Aggregate functions are COUNT, SUM, AVG, MIN and MAX.
GROUP BY groups rows that have the same values in specified columns.
HAVING filters groups after aggregation, while WHERE filters individual rows before grouping.
Example: SELECT dept, AVG(cgpa) FROM STUDENT GROUP BY dept HAVING AVG(cgpa) > 8;

---page---

## 6. Joins
An INNER JOIN returns only rows that have matching values in both tables.
A LEFT JOIN returns all rows from the left table and matching rows from the right table, with NULL where no match exists.
To use joins well, students must first understand primary keys and foreign keys, because joins connect tables through these keys.

## 7. Subqueries
A subquery is a query nested inside another query.
SELECT name FROM STUDENT WHERE cgpa > (SELECT AVG(cgpa) FROM STUDENT);

## 8. Advanced Analytics in SQL
MySQL does not support window functions, so ranking and running totals must be done using subqueries or in application code.
For placement interviews, focus on joins and subqueries.

---page---

## 9. Normalization
Functional dependency: X → Y means the value of X determines the value of Y.
First Normal Form (1NF) requires atomic values.
Second Normal Form (2NF) removes partial dependency on a composite key.
Third Normal Form (3NF) removes transitive dependency.
BCNF is stricter than 3NF: for every functional dependency X → Y, X must be a super key.

## 10. Indexing
An index speeds up data retrieval at the cost of extra storage and slower writes.
B+ trees are the most common index structure in relational databases.