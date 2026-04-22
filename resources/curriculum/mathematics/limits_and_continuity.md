# Limits and Continuity

Calculus is the study of change, and its foundation is the concept of a **Limit**. Limits allow us to talk about what happens to a function as it gets "infinitely close" to a point, even if the function doesn't exist at that exact point.

## What is a Limit?

We write **lim (x→c) f(x) = L** to mean: "As x gets closer and closer to c, the value of the function f(x) gets closer and closer to L."
Crucially, x never actually has to reach c.
- **One-Sided Limits**: We can approach from the left (x→c⁻) or the right (x→c⁺). For a general limit to exist, the left-hand limit and right-hand limit must be equal.

## Evaluating Limits

1. **Direct Substitution**: Just plug the number in. If you get a real number, you're done!
2. **Indeterminate Forms (0/0)**: If direct substitution gives 0/0, it doesn't mean the limit doesn't exist. It means you have more work to do. You can often factor and cancel terms, or use L'Hôpital's Rule.
3. **Limits at Infinity**: As x gets huge, what happens to the function? For rational functions, we look at the highest power of x in the top and bottom.

## Continuity: The "No Lifts" Rule

A function is **continuous** at a point *c* if three conditions are met:
1. The function exists at *c* (f(c) is defined).
2. The limit exists as x approaches *c*.
3. The limit is exactly equal to the function's value: **lim (x→c) f(x) = f(c)**.

If a function is continuous everywhere in its domain, its graph can be drawn without lifting your pen from the paper.

## Types of Discontinuity

- **Removable (Hole)**: The limit exists, but the function value is different or missing.
- **Jump**: The left and right limits are different (common in piecewise functions).
- **Infinite (Asymptote)**: The function shoots off to infinity or negative infinity.

## Common Misconceptions

A frequent mistake is thinking that if a function is undefined at a point, the limit can't exist. This is the whole point of limits! For example, (x²-1)/(x-1) is undefined at x=1, but the limit as x approaches 1 is exactly 2. Another error is confusing "infinite limit" (the answer is infinity) with "limit at infinity" (x is approaching infinity). Finally, students often think that if a function is continuous, it must be differentiable (smooth). Not true! The absolute value function y=|x| is continuous everywhere but has a sharp "corner" at x=0 where it cannot be differentiated.

## Analogy: The Grand Canyon Bridge

Imagine you are walking toward a bridge over the Grand Canyon.
- **Continuity**: The bridge is solid. You walk toward the middle, and the road is exactly where you expect it to be.
- **Removable Discontinuity**: There is a tiny hole in the bridge. You can see where you *should* be (the limit), but if you step there, you fall through.
- **Jump Discontinuity**: The bridge was built by two different teams who didn't talk. One side is 5 meters higher than the other. You can't cross.

## Vocabulary Checklist

Limit · Continuity · Approach · One-sided limit · Indeterminate form · Asymptote · Removable discontinuity · Jump discontinuity · Infinity · Rational function · Substitution · Piecewise function
