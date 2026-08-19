---
name: impeccable-motion
description: Guidelines for high-fidelity animations, micro-interactions, spring physics, and fluid keyframe timings.
---
# Impeccable Motion Design System

Rules and principles to follow when animating UI elements:
1. **Transition Bezier curves**: Avoid linear or simple ease-in-out animations. Use standard elastic cubic-bezier curves for premium feel:
   - `transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1)` (Ultra-premium ease-out)
2. **Spring Physics**: Use physical weight parameters for dynamic items (e.g. `stiffness: 120`, `damping: 14`, `mass: 0.8`).
3. **Micro-interactions**: Every clickable element (buttons, cards) must have active/focus states:
   - Hover: Slight raise (`translateY(-2px)`) + subtle golden drop-shadow glow.
   - Active: Pressed state (`translateY(1px)`) + dim glow.
4. **Radar & Particle Sweeps**: Use high-performance canvas loops running on `requestAnimationFrame` instead of nested CSS transitions or layout shifts.
