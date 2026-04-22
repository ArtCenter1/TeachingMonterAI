# Sorting Algorithms: Sorting the World

## 1. The Importance of Sorting
Sorting is a fundamental operation in computer science. It makes data searchable ($O(\log n)$ binary search) and easier to process.

## 2. Simple Sorting (Quadratic Time)
*   **Bubble Sort:** Repeatedly swap adjacent elements if they are in the wrong order. $O(n^2)$.
*   **Selection Sort:** Find the smallest element and move it to the front. $O(n^2)$.
*   **Insertion Sort:** Build the sorted list one item at a time (like sorting playing cards). $O(n^2)$.

## 3. Efficient Sorting (Log-Linear Time)
*   **Merge Sort:** Divide and Conquer. Split the list, sort halves, and merge. $O(n \log n)$. Reliable and stable.
*   **Quick Sort:** Pick a "pivot," partition elements around it, and recurse. Average $O(n \log n)$, but worst-case $O(n^2)$. Very fast in practice.

## 4. Complexity Comparison

| Algorithm | Average Case | Worst Case | Space Complexity |
| :--- | :--- | :--- | :--- |
| Bubble Sort | $O(n^2)$ | $O(n^2)$ | $O(1)$ |
| Merge Sort | $O(n \log n)$ | $O(n \log n)$ | $O(n)$ |
| Quick Sort | $O(n \log n)$ | $O(n^2)$ | $O(\log n)$ |

## 5. Pedagogical Insights
*   **The "Why" of N log N:** Explain that $n \log n$ is the theoretical lower bound for comparison-based sorting.
*   **Stability:** Explain why maintaining the relative order of equal elements matters (e.g., sorting people by last name, then by first name).
*   **Analogy:**
    *   **Bubble Sort:** Like bubbles rising in a soda.
    *   **Merge Sort:** Like tearing a deck of cards in half until you have single cards, then rebuilding.
