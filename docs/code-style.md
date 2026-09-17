# Code style

This file carries only what is particular to this repository. Everything else follows the
conventions the code around you already shows.

## Docstrings, not inline comments

A `#` comment explaining why something is the way it is belongs in the module or function
docstring instead, where it is found by somebody reading the API rather than only by somebody
already inside the body. Sphinx attribute docstrings — the `#:` form above a column or a
constant — are documentation, not inline comments, and are welcome.

The docstrings in this repository carry the argument, not a restatement of the signature. A
docstring that says what the reader can already see is worse than none; one that says which
alternative was rejected, and why, is the reason the next person does not undo it.

## Typing

Public functions carry types on their parameters and their return. Services stay
function-oriented and composable rather than gathered into classes for the sake of it.
