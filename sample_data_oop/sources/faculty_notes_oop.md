# Object-Oriented Programming with Java – Lecture Notes, Units 1 to 5 (Prepared by Prof. K. Menon, 2015)

## 1. Classes and Objects
A class is a blueprint that defines the fields and methods of its objects, and an object is an instance of a class created with the new keyword.
A constructor has the same name as the class and runs automatically when an object is created.
In Java, every local variable must be declared with an explicit type, such as int count = 0 or String name = "Asha".

## 2. Encapsulation
Encapsulation hides the internal state of an object by making fields private and exposing public getter and setter methods.
Access modifiers in Java are public, protected, default (package-private) and private.

---page---

## 3. Inheritance
A subclass inherits the fields and methods of its superclass using the extends keyword.
A Java class can extend only one class, so Java does not support multiple inheritance of classes.
The super keyword calls the constructor or methods of the parent class.

## 4. Polymorphism
Method overloading means several methods in the same class share a name but have different parameter lists, and it is resolved at compile time.
Method overriding means a subclass gives its own version of a superclass method, and the call is resolved at runtime.
Java passes arguments by value; for objects, the value passed is a copy of the reference.

---page---

## 5. Abstraction
An abstract class can have both abstract methods and concrete methods, and it cannot be instantiated.
An interface in Java can contain only abstract methods and constants; it cannot contain any method body.
A class can implement several interfaces, which is how Java achieves a form of multiple inheritance.

## 6. Exception Handling
Checked exceptions must be either caught or declared with throws, while unchecked exceptions extend RuntimeException.
The finally block runs whether or not an exception is thrown.
To release resources such as files, override the finalize() method so the garbage collector closes them.

---page---

## 7. Collections
ArrayList stores elements in a resizable array and gives fast access by index.
HashMap stores key-value pairs and gives average constant-time lookup by key.
Generics such as List<String> let the compiler check element types and avoid casts.
