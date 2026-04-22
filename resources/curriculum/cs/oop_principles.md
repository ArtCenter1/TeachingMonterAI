# Object-Oriented Programming (OOP) Principles

## 1. What is OOP?
Object-Oriented Programming is a paradigm based on the concept of "objects," which can contain data (attributes) and code (methods).

## 2. The Four Pillars of OOP
1.  **Encapsulation:** Bundling data and methods together and restricting direct access to some components (using `private` vs `public`). It protects the object's internal state.
2.  **Abstraction:** Hiding complex implementation details and showing only the necessary features of an object. (e.g., you know how to drive a car without knowing how the engine works).
3.  **Inheritance:** Allowing a new class (subclass) to acquire properties and methods of an existing class (superclass). Promotes code reuse.
4.  **Polymorphism:** The ability of different classes to be treated as instances of the same class through a common interface. (e.g., a `Shape` class with a `draw()` method that works differently for `Circle` and `Square`).

## 3. Classes vs. Objects
*   **Class:** A blueprint or template for creating objects (e.g., "Car" blueprint).
*   **Object:** A specific instance of a class (e.g., "My Red Tesla").

## 4. Key Concepts
*   **Constructor:** A special method called when an object is instantiated.
*   **Method Overloading:** Multiple methods with the same name but different parameters.
*   **Method Overriding:** A subclass providing a specific implementation of a method already defined in its superclass.

## 5. Pedagogical Analogies
*   **The Blueprint:** A class is the architectural drawing; the object is the actual house built from it.
*   **Remote Control:** A class interface is like the buttons on a remote; you don't need to know the circuit board (encapsulation) to change the channel.

## 6. Common Student Mistakes
*   **Confusion between Class and Object:** Thinking they are the same thing.
*   **Over-inheritance:** Trying to force an "is-a" relationship when a "has-a" relationship (composition) is better.
