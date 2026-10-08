# Modern Java: Objects and Beyond, 2nd Edition (2024) – Selected Excerpts

## Chapter 4: Interfaces in Modern Java
Since Java 8, interfaces can contain default methods and static methods with a body, in addition to abstract methods.
Since Java 9, interfaces can also contain private methods that share code between default methods.

## Chapter 5: Local Variable Type Inference
Since Java 10, the var keyword lets the compiler infer the type of a local variable, as in var names = new ArrayList<String>();
The variable is still statically typed: var only removes the need to write the type, not the type itself.

---page---

## Chapter 7: Resource Management
The finalize() method was deprecated in Java 9 and deprecated for removal in Java 18, because finalizers are unpredictable and slow.
Use try-with-resources so that any AutoCloseable resource is closed automatically when the block ends.

## Chapter 8: Inheritance and Composition
A Java class can extend only one superclass but can implement many interfaces.
Favour composition over inheritance when classes have a has-a relationship rather than an is-a relationship.
Java is always pass-by-value: when an object is passed to a method, the method receives a copy of the reference.

---page---

## Chapter 10: Functional Java
Lambda expressions, introduced in Java 8, let you pass behaviour as an argument, for example list.forEach(x -> System.out.println(x)).
The Stream API processes collections declaratively with operations such as filter, map and collect.

## Chapter 11: Records and Sealed Classes
Records, standard since Java 16, are concise immutable data classes that generate the constructor, accessors, equals, hashCode and toString.
Sealed classes, standard since Java 17, restrict which classes may extend or implement them.
