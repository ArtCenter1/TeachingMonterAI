# Linear Algebra Basics

Linear algebra is the study of vectors, matrices, and linear transformations. It is the mathematical "engine" behind almost everything in modern computing, including 3D graphics, search engines (Google), and Artificial Intelligence.

## Vectors: Direction and Magnitude

A vector is a quantity that has both a size (magnitude) and a direction. We can represent a vector as an arrow or as a list of numbers (coordinates).
- **Addition**: Add the corresponding components.
- **Scalar Multiplication**: Multiplying a vector by a number (a scalar) changes its length but usually not its direction.
- **Dot Product**: A way to multiply two vectors that results in a single number. It tells us how much two vectors "point in the same direction." If the dot product is zero, the vectors are perpendicular (90 degrees apart).

## Matrices: Arrays of Numbers

A matrix is a rectangular grid of numbers. We describe them by their dimensions (rows × columns).
- **Matrix Multiplication**: This is not just multiplying each entry. It involves a "row-by-column" dot product process. It is used to combine multiple transformations into one.
- **Identity Matrix**: The "number 1" of matrices. It has 1s on the diagonal and 0s elsewhere. Multiplying any matrix by the identity matrix leaves it unchanged.

## Linear Transformations

This is the most important concept in linear algebra. A matrix can be thought of as a function that takes an input vector and "transforms" it into an output vector. These transformations can include:
- **Scaling**: Making things bigger or smaller.
- **Rotation**: Turning an object around an axis.
- **Shearing**: Tilting or distorting an object.

In computer games, every time a character moves or the camera turns, billions of matrix-vector multiplications are happening every second.

## Determinants and Inverses

- **Determinant**: A single number calculated from a square matrix. It tells you the "scale factor" of the transformation. If the determinant is 0, the matrix collapses space into a flat line or point and cannot be reversed.
- **Inverse Matrix**: The "opposite" of a matrix. If a matrix A performs a rotation, the inverse matrix A⁻¹ performs the same rotation in the opposite direction.

## Common Misconceptions

A major misconception is that matrix multiplication is commutative (meaning A × B = B × A). It isn't! The order of operations matters. If you rotate a cube and then slide it, it ends up in a different place than if you slid it first and then rotated it. Another error is thinking that vectors are only for physics. In data science, every row in a spreadsheet (age, height, income) is treated as a "vector" in high-dimensional space. Finally, students often see matrices as just "grids of numbers" and miss the geometric intuition of how they move and stretch space.

## Analogy: The Photoshop Filter

Imagine you have a digital photo.
- The **Vectors** are the positions and colours of every pixel.
- The **Matrix** is a filter (like "Stretch" or "Rotate").
- When you apply the filter, the computer performs linear algebra on every pixel's vector to calculate its new position. If you apply two filters, that's matrix multiplication!

## Vocabulary Checklist

Vector · Matrix · Scalar · Dot Product · Linear Transformation · Identity Matrix · Determinant · Inverse · Dimension · Row · Column · Commutative · Eigenvalue · Eigenvector · Space
