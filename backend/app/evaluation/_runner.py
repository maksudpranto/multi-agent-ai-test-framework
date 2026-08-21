"""Sandbox worker: run one entrypoint on a batch of inputs, in isolation.

Invoked as a separate, isolated interpreter (`python -I _runner.py`) by the
harness — NEVER imported into the API process, because it executes benchmark and
mutant code. It reads a JSON job from stdin and writes a JSON result to stdout:

  in : {"code", "entrypoint", "inputs": [[...], ...], "per_input_timeout": 2.0}
  out: {"results": [{"status": "ok"|"error"|"timeout", "key": "..."}, ...],
        "load_error": null | "<message>"}

Defence in depth: the process is short-lived and isolated (`-I`), memory and CPU
are capped with resource limits, file writes are forbidden (RLIMIT_FSIZE = 0),
and each individual call is bounded by a wall-clock timer (SIGALRM) so one
pathological input cannot hang the batch. The parent adds its own hard wall-clock
timeout and process-group kill as a final backstop. There is deliberately no
network-namespace isolation — acceptable here because every program and input in
the benchmark is our own, never user-supplied.
"""
import json
import reprlib
import signal
import sys

_repr = reprlib.Repr()
_repr.maxstring = 200
_repr.maxother = 200


def _apply_limits() -> None:
    """Best-effort resource caps. Wrapped because not every platform honours
    every limit; the parent's wall-clock timeout is the guaranteed backstop."""
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX
        return
    caps = [
        (resource.RLIMIT_CPU, (4, 5)),  # CPU seconds (soft, hard)
        (resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024)),  # address space
        (resource.RLIMIT_FSIZE, (0, 0)),  # forbid writing files
    ]
    for res, (soft, hard) in caps:
        try:
            resource.setrlimit(res, (soft, hard))
        except (ValueError, OSError):
            pass


class _Timeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _Timeout()


def _key(value) -> str:
    """A deterministic, bounded string identity for a return value. Two runs
    diverge iff their keys differ. Type is encoded (via repr) so a str '7' and
    an int 7 are distinct — that catches type-only bugs."""
    return _repr.repr(value)


def main() -> None:
    _apply_limits()
    try:
        job = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as exc:
        json.dump({"results": [], "load_error": f"bad job: {exc}"}, sys.stdout)
        return

    code = job.get("code", "")
    entrypoint = job.get("entrypoint", "")
    inputs = job.get("inputs", []) or []
    per_input_timeout = float(job.get("per_input_timeout", 2.0))

    namespace: dict = {}
    try:
        compiled = compile(code, "<benchmark>", "exec")
        exec(compiled, namespace)  # noqa: S102 - sandboxed, our own code
        fn = namespace[entrypoint]
    except Exception as exc:  # noqa: BLE001 - report any load failure upward
        json.dump(
            {"results": [], "load_error": f"{type(exc).__name__}: {exc}"}, sys.stdout
        )
        return

    signal.signal(signal.SIGALRM, _on_alarm)
    results = []
    for args in inputs:
        signal.setitimer(signal.ITIMER_REAL, per_input_timeout)
        try:
            value = fn(*args)
            results.append({"status": "ok", "key": _key(value)})
        except _Timeout:
            results.append({"status": "timeout", "key": ""})
        except Exception as exc:  # noqa: BLE001 - a raised exception IS an outcome
            results.append({"status": "error", "key": type(exc).__name__})
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)

    json.dump({"results": results, "load_error": None}, sys.stdout)


if __name__ == "__main__":
    main()
