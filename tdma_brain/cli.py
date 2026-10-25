"""Command-line interface of the TDMA Schedule Optimizer (Part 1 deliverable)."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from . import DEFAULT_RANGE_M, __version__
from .optimizer import optimize
from .parsing import InputError, parse_coordinates
from .report import dumps, render_report, to_json
from .simulator import baseline_schedules, simulate
from .topology import Topology
from .verify import verify_matrix

EXIT_OK, EXIT_INPUT, EXIT_VERIFY, EXIT_IO = 0, 1, 2, 3

EXAMPLE = ('{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0],"Node_03":[600.0,0.0],'
           '"Node_04":[900.0,0.0],...,"Node_16":[900.0,900.0]}')


class _Parser(argparse.ArgumentParser):
    """argparse exits with 2 on usage errors; here 2 means 'verification failed'."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INPUT)


def _safe_console() -> None:
    """Never crash on node names the console code page cannot encode (escape them)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="tdma_scheduler.py",
        description="Distance-2 graph-colouring TDMA schedule optimizer. Reads node "
                    "coordinates (metres), links radios within --range, and prints a "
                    "conflict-free Node->Slot mapping and Slot x Node matrix.",
        epilog="Input forms: a JSON string argument, e.g. " + EXAMPLE +
               "  |  @path/to/file.json  |  --file path.json  |  - (read stdin). "
               "Exit status: 0 = verified conflict-free, 1 = invalid input or usage, "
               "2 = verification failed, 3 = output file could not be written.",
    )
    p.add_argument("json", nargs="*", help="node coordinates as a JSON object string "
                   "(several tokens are joined, which tolerates shells that split the argument)")
    p.add_argument("-f", "--file", type=Path, help="read the JSON object from this file")
    p.add_argument("-r", "--range", type=float, default=DEFAULT_RANGE_M, dest="radio_range",
                   help=f"radio range in metres (default {DEFAULT_RANGE_M})")
    p.add_argument("-o", "--json-out", type=Path, help="also write the schedule as JSON (for the EMANE bridge)")
    p.add_argument("--max-reuse", action="store_true",
                   help="additionally grant nodes extra non-conflicting slots in the same frame")
    p.add_argument("--simulate", type=int, metavar="FRAMES", default=0,
                   help="run the slot-level simulator for FRAMES frames and compare with baselines")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="print topology, heuristic portfolio and per-slot spatial reuse")
    p.add_argument("--seed", type=int, default=0, help="seed for randomised heuristics (default 0)")
    p.add_argument("--time-limit", type=float, default=5.0,
                   help="wall-clock limit (s) for the exact certificate (default 5)")
    p.add_argument("--no-exact", action="store_true", help="skip the exact branch-and-bound step")
    p.add_argument("--sample-format", action="store_true",
                   help="reproduce the problem statement's sample layout exactly "
                        "(no extra header lines, sample matrix spacing)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def read_input(args: argparse.Namespace) -> str:
    if args.file is not None:
        if args.json:
            raise InputError("give either a JSON argument or --file, not both")
        return _read_file(args.file)
    if args.json:
        if len(args.json) == 1 and args.json[0] == "-":
            return _read_stdin()
        if len(args.json) == 1 and args.json[0].startswith("@"):
            return _read_file(Path(args.json[0][1:]))
        return " ".join(args.json)
    if not sys.stdin.isatty():
        return _read_stdin()
    raise InputError("no input; pass node coordinates as a JSON string, e.g. " + EXAMPLE)


def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except UnicodeDecodeError:
        raise InputError("standard input is not valid text in the console encoding; "
                         "use --file with a UTF-8 file") from None


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror}") from None
    except UnicodeDecodeError:
        raise InputError(f"{path} is not UTF-8 text") from None


def main(argv: list[str] | None = None) -> int:
    _safe_console()
    args = build_parser().parse_args(argv)
    try:
        if not (math.isfinite(args.radio_range) and args.radio_range > 0):
            raise InputError("--range must be a positive finite number of metres")
        if not (math.isfinite(args.time_limit) and args.time_limit > 0):
            raise InputError("--time-limit must be a positive finite number of seconds")
        if args.simulate < 0:
            raise InputError("--simulate must be >= 0")
        parsed = parse_coordinates(read_input(args))
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT

    if parsed.repaired_quotes:
        print("note: input had unquoted keys (Windows PowerShell strips double quotes from "
              "arguments); they were re-quoted. Use --file or @file.json to avoid this.",
              file=sys.stderr)
    if len(parsed.coords) != 16:
        count = len(parsed.coords)
        print(f"note: {count} node{'s' if count != 1 else ''} given (the problem statement "
              "specifies 16); proceeding.", file=sys.stderr)

    topo = Topology(parsed.coords, args.radio_range)
    sched = optimize(topo, seed=args.seed, use_exact=not args.no_exact,
                     time_limit=args.time_limit, max_reuse=args.max_reuse)

    ver = verify_matrix(parsed.coords, args.radio_range, sched.names, sched.matrix(), sched.slot_of)
    ver_reuse = None
    if args.max_reuse:
        ver_reuse = verify_matrix(parsed.coords, args.radio_range, sched.names,
                                  sched.matrix(include_extra=True), sched.slot_of)

    sims = None
    if args.simulate:
        sims = [simulate(topo.G, sched.transmitters(), args.simulate,
                         label="Optimized distance-2 schedule (this tool)")]
        if args.max_reuse:
            sims.append(simulate(topo.G, sched.transmitters(include_extra=True), args.simulate,
                                 label="Optimized + max-reuse"))
        for label, tx in baseline_schedules(topo.G, sched.names).items():
            sims.append(simulate(topo.G, tx, args.simulate, label=label))

    print(render_report(topo, sched, ver, ver_reuse=ver_reuse, verbose=args.verbose, sims=sims,
                        sample_format=args.sample_format))

    if args.json_out is not None:
        try:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(dumps(to_json(topo, sched, ver)) + "\n", encoding="utf-8")
        except OSError as e:
            print(f"error: cannot write {args.json_out}: {e.strerror}", file=sys.stderr)
            return EXIT_IO

    ok = ver.ok and (ver_reuse is None or ver_reuse.ok)
    return EXIT_OK if ok else EXIT_VERIFY
