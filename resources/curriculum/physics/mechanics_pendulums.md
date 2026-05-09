# Physics Curriculum: Mechanics of Pendulums

## 1. Simple Harmonic Motion (SHM) in Pendulums
A pendulum exhibits Simple Harmonic Motion when the restoring force is proportional to the displacement. For a simple pendulum, this occurs at small angles ($\theta < 10^\circ$), where $\sin(\theta) \approx \theta$.

The restoring force $F = -mg \sin(\theta) \approx -mg\theta$.
Since $s = L\theta$, we have $F = -mg(s/L) = -(mg/L)s$.
This matches the SHM form $F = -ks$ where $k = mg/L$.

## 2. Simple Pendulum
A **simple pendulum** is an idealized model consisting of a point mass (the bob) suspended by a massless, unstretchable string.

### The Period Formula
The period $T$ of a simple pendulum is given by:
$$T = 2\pi \sqrt{\frac{L}{g}}$$
where:
- $L$ is the length of the string.
- $g$ is the acceleration due to gravity ($\approx 9.81 m/s^2$).

### Conditions and Limitations
- **Small Angle Approximation**: The formula is only accurate for small oscillations.
- **Point Mass**: The bob's size must be negligible compared to $L$.
- **Massless String**: The mass of the string is assumed to be zero.

## 3. Physical Pendulum
A **physical pendulum** (or compound pendulum) is any real-world rigid body that swings about a pivot point. Unlike the simple pendulum, its mass is distributed throughout its volume.

### The Period Formula
The period $T$ of a physical pendulum is:
$$T = 2\pi \sqrt{\frac{I}{mgd}}$$
where:
- $I$ is the **moment of inertia** of the body about the pivot point.
- $m$ is the total mass of the body.
- $g$ is gravity.
- $d$ is the distance from the pivot point to the **center of mass** (COM).

### Key Disambiguation
- **Newton's Cradle**: Often confused with physical pendulums, but typically modeled as a series of simple pendulums.
- **Moment of Inertia**: Crucial for physical pendulums; depends on the axis of rotation.

## 4. Energy Conservation
In an ideal pendulum, energy oscillates between **gravitational potential energy** ($U = mgh$) and **kinetic energy** ($K = \frac{1}{2}mv^2$ for simple, $K = \frac{1}{2}I\omega^2$ for physical).

At the highest point: $E = U_{max}$.
At the lowest point (equilibrium): $E = K_{max}$.

## 5. Damping and Real-World Effects
Real pendulums experience air resistance and friction at the pivot, causing the amplitude to decay over time. This is known as **damped harmonic motion**.
- **Underdamped**: The pendulum swings many times with decreasing amplitude.
- **Overdamped**: The pendulum returns slowly to equilibrium without oscillating.
- **Critically Damped**: The pendulum returns to equilibrium as quickly as possible without oscillating.
