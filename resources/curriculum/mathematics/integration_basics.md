# Integral Calculus: Area Under the Curve

## 1. Introduction
If the derivative measures the rate of change, the integral measures the "accumulation" of change. It is the reverse process of differentiation.

## 2. The Definite Integral
The definite integral $\int_{a}^{b} f(x) dx$ represents the signed area between the graph of $f(x)$ and the x-axis from $x=a$ to $x=b$.

## 3. The Fundamental Theorem of Calculus
This theorem connects derivatives and integrals:
**Part 1:** If $F(x) = \int_{a}^{x} f(t) dt$, then $F'(x) = f(x)$.
**Part 2:** $\int_{a}^{b} f(x) dx = F(b) - F(a)$, where $F$ is any antiderivative of $f$.

## 4. Antiderivatives (Indefinite Integrals)
The indefinite integral $\int f(x) dx = F(x) + C$ represents the family of all functions whose derivative is $f(x)$. The $+C$ is the constant of integration.

### Basic Integration Rules:
*   **Power Rule:** $\int x^n dx = \frac{x^{n+1}}{n+1} + C$ (for $n \neq -1$).
*   **Natural Log:** $\int \frac{1}{x} dx = \ln|x| + C$.
*   **Exponentials:** $\int e^x dx = e^x + C$.

## 5. Applications
*   **Physics:** Finding displacement from velocity, or velocity from acceleration.
*   **Geometry:** Finding volumes of solids of revolution.
*   **Economics:** Calculating total profit from marginal profit.

## 6. Pedagogical Tips
*   **Riemann Sums:** Start by approximating area with rectangles. As the number of rectangles goes to infinity, the approximation becomes the exact integral.
*   **The Reverse Metaphor:** If differentiation is "taking things apart" to see how they change, integration is "putting things back together" to see the whole.
*   **The Odometer:** The odometer in a car "integrates" the speed over time to give the total distance.
