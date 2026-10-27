# Rejected controller experiments

These headers preserve the attempted geometric support-step and floating-base
contact controller for research. They are **not built or used by the game**.
Their walking/standing trials failed. Do not restore them as a gameplay fix.

The isolated tangent-space mass/bias model did match Bullet acceleration tests;
that smaller verified component is retained as `body_dynamics.hpp` in the native
humanoid code. Passing that numerical check did not validate the contact
controller. In particular, a feasible model wrench did not produce reliable
measured contact and balance in the finite-foot Bullet simulation.

The supported native reference and the fully dynamic motor remain separate.
The new PPO environment uses the latter directly, with 148 observations and
20 residual action channels, without these rejected controllers.
