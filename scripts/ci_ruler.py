"""Measure the runner, not the suite (ENG-556).

The `test` job takes between 6 and 56 minutes for the same suite. Measured from the outside
it has no culprit: on two independent pairs of runs, **every one of ten deciles** was slower
and 12-17% of individual cases were *faster* in the slow run. That is the signature of a
machine, not of code — but which part of the machine is not in any log, because nothing in
the job measures the machine at all.

Two things happen here and they answer different questions.

`ruler` does a **fixed amount of known work** — hashing, then writing and reading a file —
and reports how long it took. Run before and after the suite it says how fast this machine
is, on a scale that does not depend on the suite at all. Locally it costs 0.30 s with 2%
spread across five runs, which is what makes it usable as a ruler.

`sample` answers the other half: whether a slow machine is slow *throughout* or in bursts,
which decides whether the fix is choosing machines or spacing runs. It reads `/proc` and
computes nothing, so it competes with the suite for almost nothing — the cost it must not
have, since a sampler that stole CPU would be measuring its own interference.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time

CPU_BLOCKS = 200_000
DISK_BLOCKS = 10_000


def cpu_seconds() -> float:
    started = time.perf_counter()
    digest = hashlib.sha256()
    block = b"x" * 4096
    for _ in range(CPU_BLOCKS):
        digest.update(block)
    return time.perf_counter() - started


def disk_seconds() -> float:
    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        name = handle.name
        for _ in range(DISK_BLOCKS):
            handle.write(b"y" * 8192)
        handle.flush()
        os.fsync(handle.fileno())
    with open(name, "rb") as handle:
        while handle.read(65536):
            pass
    os.unlink(name)
    return time.perf_counter() - started


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def cpu_facts() -> str:
    model = next(
        (
            line.split(":", 1)[1].strip()
            for line in _read("/proc/cpuinfo").splitlines()
            if line.startswith("model name")
        ),
        "?",
    )
    return f"nproc={os.cpu_count()} model={model!r}"


def stat_fields() -> dict[str, float]:
    """user/system/idle/iowait/steal, in jiffies, off the aggregate `cpu` line."""
    for line in _read("/proc/stat").splitlines():
        if line.startswith("cpu "):
            n = [float(v) for v in line.split()[1:]]
            names = ["user", "nice", "system", "idle", "iowait", "irq", "softirq", "steal"]
            return dict(zip(names, n + [0.0] * len(names), strict=False))
    return {}


def pressure(resource: str) -> str:
    """PSI: the share of time work was stalled waiting for this resource."""
    for line in _read(f"/proc/pressure/{resource}").splitlines():
        if line.startswith("some"):
            return line.split("total=")[-1]
    return "?"


def ruler(label: str) -> None:
    started = time.perf_counter()
    cpu, disk = cpu_seconds(), disk_seconds()
    print(
        f"RULER {label} cpu={cpu:.3f}s disk={disk:.3f}s cost={time.perf_counter() - started:.3f}s "
        f"{cpu_facts()} load={_read('/proc/loadavg')}"
    )


def sample(seconds: float) -> None:
    """One line per tick: the counters, so the shape over time is recoverable."""
    print(f"SAMPLE start {cpu_facts()}", flush=True)
    started = time.monotonic()
    while True:
        fields = stat_fields()
        print(
            f"SAMPLE t={time.monotonic() - started:8.1f} "
            f"user={fields.get('user', 0):.0f} system={fields.get('system', 0):.0f} "
            f"idle={fields.get('idle', 0):.0f} iowait={fields.get('iowait', 0):.0f} "
            f"steal={fields.get('steal', 0):.0f} "
            f"psi_cpu={pressure('cpu')} psi_io={pressure('io')} "
            f"load={_read('/proc/loadavg').split(' ')[0]}",
            flush=True,
        )
        time.sleep(seconds)


if __name__ == "__main__":
    if sys.argv[1] == "ruler":
        ruler(sys.argv[2])
    elif sys.argv[1] == "sample":
        sample(float(sys.argv[2]))
    else:
        raise SystemExit(f"unknown mode {sys.argv[1]!r}")
