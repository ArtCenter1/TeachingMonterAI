# Probability Theory: Understanding Uncertainty

## 1. Introduction
Probability is the branch of mathematics concerning numerical descriptions of how likely an event is to occur. It ranges from 0 (impossible) to 1 (certain).

## 2. Basic Concepts
*   **Sample Space ($S$):** The set of all possible outcomes.
*   **Event ($E$):** A subset of the sample space.
*   **Formula:** $P(E) = \frac{\text{Number of favorable outcomes}}{\text{Total number of possible outcomes}}$ (for equally likely outcomes).

## 3. Probability Rules
*   **Complement Rule:** $P(\text{not } E) = 1 - P(E)$.
*   **Addition Rule:** $P(A \text{ or } B) = P(A) + P(B) - P(A \text{ and } B)$.
*   **Multiplication Rule:** $P(A \text{ and } B) = P(A) \times P(B|A)$.

## 4. Independence and Conditional Probability
*   **Independent Events:** The occurrence of one doesn't affect the other. $P(A \text{ and } B) = P(A) \times P(B)$.
*   **Conditional Probability:** The probability of an event given that another has occurred. $P(B|A) = \frac{P(A \text{ and } B)}{P(A)}$.

## 5. Bayes' Theorem
A powerful formula for updating probabilities based on new evidence:
$$ P(A|B) = \frac{P(B|A)P(A)}{P(B)} $$

## 6. Pedagogical Insights
*   **Misconception: Gambler's Fallacy.** Students think if a coin lands heads 5 times in a row, the next one is "due" to be tails. Explain that independent events have no memory.
*   **Law of Large Numbers:** Explain that probability is a long-term frequency. You might get 4 heads in 5 flips, but in 5,000 flips, you'll be very close to 50%.
*   **Analogy: The Weather.** A "30% chance of rain" doesn't mean it will definitely rain in 30% of the city; it means in historical conditions like today's, it rained 3 out of 10 times.
