# Expected Results – Object-Oriented Programming with Java (answer key for testing agents)

## Conflicts the Reconciler should find
1. Interfaces: Notes 2015 ("only abstract methods, no method body") vs Textbook 2024 (default and static methods since Java 8, private since Java 9) + Backend JD
   -> outdated; Textbook wins
2. Local variable types: Notes 2015 ("every local variable must be declared with an explicit type") vs Textbook 2024 (var since Java 10) + Backend JD
   -> outdated; Textbook wins
3. Releasing resources: Notes 2015 ("override finalize()") vs Textbook 2024 (finalize deprecated, use try-with-resources) + Java Developer JD
   -> outdated; Textbook wins
4. Multiple inheritance of classes: Blog 2013 ("a class can extend two classes") vs Notes 2015 + Textbook 2024 (only one superclass)
   -> Notes + Textbook win
5. Parameter passing: Blog 2013 ("pass-by-reference for objects") vs Notes 2015 + Textbook 2024 (always pass-by-value, a copy of the reference)
   -> Notes + Textbook win
6. "Inheritance is always better than composition": Blog 2013 -> unreliable (Textbook: favour composition for has-a)
7. "Always compare strings with ==": Blog 2013 -> flagged unreliable (absolute, wrong advice)

## Syllabus gaps (in JDs, missing from faculty notes)
Missing: lambdas and the Stream API, records
Outdated: interfaces (default methods), resource management (try-with-resources), modern syntax (var)
Covered: OOP principles (encapsulation, inheritance, polymorphism), exception handling basics, collections and generics

## Prerequisite chain (expected, roughly)
Classes and Objects -> Encapsulation -> Inheritance -> Polymorphism
Inheritance -> Abstraction (abstract classes, interfaces)
Classes and Objects -> Exception Handling -> Resource Management
Classes and Objects -> Collections and Generics -> Lambdas and Streams
