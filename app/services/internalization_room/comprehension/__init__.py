"""Comprehension evidence for the internalization room.

Coverage answers "did the team encounter and engage with this element?"; this package
answers the different question "what evidence do we have about the team's understanding?".
Callers may keep both, but must never infer one from the other. Every decision that
advances the workflow — checkpoint scope, evidence method, readiness, deferral to Refine —
is made by code here; the models only phrase questions and classify semantic evidence
inside a scope the application already authorized.
"""
