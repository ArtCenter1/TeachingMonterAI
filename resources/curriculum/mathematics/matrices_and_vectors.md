# Matrices and Vectors: The Language of Linear Algebra

## 1. Introduction
Linear Algebra is the branch of mathematics concerning linear equations and their representations in vector spaces and through matrices. It is the backbone of modern data science and AI.

## 2. Vectors
A vector is a quantity having both magnitude and direction. In CS, it's often represented as an ordered list of numbers.

### Key Operations:
*   **Addition:** Add corresponding components.
*   **Scalar Multiplication:** Multiply every component by a single number.
*   **Dot Product:** Sum of the products of corresponding components. Measures how much two vectors "point" in the same direction.

## 3. Matrices
A matrix is a rectangular array of numbers arranged in rows and columns.

### Key Operations:
*   **Matrix Addition:** Must have the same dimensions.
*   **Matrix Multiplication:** The number of columns in the first must equal the number of rows in the second. (Not commutative! $AB \neq BA$).
*   **Determinant:** A scalar value that describes properties of a square matrix (e.g., if it's invertible).

## 4. Linear Transformations
Matrices are not just tables of numbers; they are "functions" that transform vectors.
*   **Rotation:** Turning a vector in space.
*   **Scaling:** Stretching or shrinking a vector.
*   **Shearing:** Slanting a vector.

## 5. Applications
*   **Computer Graphics:** Rotating and projecting 3D objects onto 2D screens.
*   **Machine Learning:** Weights in a neural network are matrices.
*   **Google's PageRank:** Uses Eigenvectors to rank websites.

## 6. Pedagogical Analogies
*   **Vectors as Arrows:** Drawing them on a grid to show direction and length.
*   **Matrices as "Filters":** You put a vector in, and the matrix "filters" or "changes" it into a new vector.
*   **Spreadsheet Metaphor:** A matrix is like a single sheet of data that you can perform operations on all at once.
