#: The four names GATE-01 D1 left undecided, waiting for the Gestor to decide them.
#:
#: PRD v1.1 §3 named five funds and the client kept one — *Shema Línguas* — answering that
#: the other four *"serão decididos depois"*. They are **not** retired and **not** approved,
#: so they are not rows: a fund row is an assertion about someone's money, and that is the
#: assertion the client declined to make. They are not a seed for the same reason, and the
#: DoD says so in as many words.
#:
#: What they are is a register the fund administration screen can offer, so the Gestor
#: creating the next fund sees the four names the project already spoke of instead of
#: recalling them. Choosing one is still an act of creation — the row is minted by
#: ``create_fund`` with its own opaque id, and nothing here reserves the name in the
#: database. A name already taken by a fund is refused by ``uq_rr_funds_name`` like any
#: other, which is why this list is offered and never checked against.
#:
#: In prototype order, which is also PRD v1.1 §3's.
RESERVED_FUND_NAMES: tuple[str, ...] = (
    "Shema BTAT",
    "Tripod",
    "OBT-Lab",
    "Ora-Bridge",
)
