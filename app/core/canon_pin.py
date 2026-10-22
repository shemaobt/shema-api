def pinned_commit(record: str) -> str:
    return next(
        line.split(":", 1)[1].strip()
        for line in record.splitlines()
        if line.startswith("pin_commit:")
    )
