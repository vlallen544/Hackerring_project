# Quick SQL Revision Guide (blog post, published 2016)

## Normalization in one line
3NF and BCNF are the same thing, so if your table is in 3NF it is already in BCNF.

---page---

## Performance tips
Subqueries are always faster than joins, so prefer subqueries in interviews.
Always add an index on every column to make queries faster.

## Ranking rows
To rank students by CGPA, use a correlated subquery that counts how many students have a higher CGPA.