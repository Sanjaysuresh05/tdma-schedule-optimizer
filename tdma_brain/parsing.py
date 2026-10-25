"""Parsing and validation of the node-coordinate JSON input.

Accepted input: a JSON object mapping node name -> [x, y] in metres, e.g.
``{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0]}``.

Strict checks: valid JSON object, no duplicate names, names without control
characters or leading/trailing whitespace, every value a list of exactly two
finite real numbers with |value| <= 1e9 m (booleans, NaN/Infinity, overflowing
numbers rejected).  Every failure raises InputError (never a traceback).

Windows PowerShell 5.1 strips the inner double quotes of an argument passed
to a native program, so ``'{"Node_01":[0,0]}'`` arrives as ``{Node_01:[0,0]}``.
If (and only if) strict parsing fails, bare keys are re-quoted and parsing is
retried; the caller is told that a repair happened.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass

Coordinates = dict[str, tuple[float, float]]

# Radios are on (or near) Earth; anything larger is a unit error, and keeping
# coordinates bounded keeps every squared distance far from float overflow.
MAX_ABS_COORD_M = 1e9


class InputError(ValueError):
    """Raised for any malformed or semantically invalid input."""


@dataclass(frozen=True)
class ParsedInput:
    coords: Coordinates
    repaired_quotes: bool  # True if PowerShell-style quote stripping was repaired


# An unquoted object key: right after '{' or ',' and followed by ':'.
_BARE_KEY = re.compile(r'([{,]\s*)([^\s"\[\]{},:]+)\s*:')


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise InputError(f"duplicate node name {key!r} in input JSON")
        obj[key] = value
    return obj


def _reject_constant(name: str) -> float:
    raise InputError(f"non-finite number {name!r} is not a valid coordinate")


def _loads(text: str) -> object:
    # Integers are parsed as floats: an integer too large for a float becomes
    # inf (rejected below) instead of raising OverflowError / the 4300-digit
    # int-conversion ValueError.
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
        parse_int=float,
    )


def _check_name(name: str) -> None:
    if not name.strip():
        raise InputError("node names must be non-empty strings")
    if name != name.strip():
        raise InputError(f"node name {name!r} has leading/trailing whitespace")
    if any(unicodedata.category(ch).startswith("C") for ch in name):
        raise InputError(f"node name {name!r} contains control/format characters")


def _repair_bare_keys(text: str) -> str:
    return _BARE_KEY.sub(lambda m: f'{m.group(1)}"{m.group(2)}":', text)


def _as_coordinate(name: str, value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise InputError(
            f"node {name!r}: expected [x, y] (two numbers), got {json.dumps(value)}"
        )
    out = []
    for axis, component in zip("xy", value):
        # bool is a subclass of int in Python; true/false are not coordinates.
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise InputError(
                f"node {name!r}: {axis}-coordinate must be a number, got {json.dumps(component)}"
            )
        fval = float(component)
        if not math.isfinite(fval):
            raise InputError(f"node {name!r}: {axis}-coordinate is not finite")
        if abs(fval) > MAX_ABS_COORD_M:
            raise InputError(f"node {name!r}: {axis}-coordinate {fval:g} m exceeds "
                             f"+/-{MAX_ABS_COORD_M:g} m (wrong units?)")
        out.append(fval)
    return out[0], out[1]


def parse_coordinates(text: str) -> ParsedInput:
    """Parse and validate the coordinate JSON text."""
    if text is None:
        raise InputError("no input given")
    text = text.lstrip("﻿").strip()
    if not text:
        raise InputError("empty input; expected a JSON object such as "
                         '{"Node_01":[0.0,0.0],"Node_02":[300.0,0.0]}')

    repaired = False
    try:
        data = _loads(text)
    except json.JSONDecodeError as strict_error:
        candidate = _repair_bare_keys(text)
        if candidate == text:
            raise InputError(f"invalid JSON: {strict_error}") from None
        try:
            data = _loads(candidate)
        except (json.JSONDecodeError, ValueError, RecursionError):
            raise InputError(f"invalid JSON: {strict_error}") from None
        repaired = True
    except RecursionError:
        raise InputError("invalid JSON: nesting too deep") from None
    except ValueError as e:  # e.g. numbers the json module cannot convert
        raise InputError(f"invalid JSON: {e}") from None

    if not isinstance(data, dict):
        raise InputError("input JSON must be an object mapping node name -> [x, y]")
    if not data:
        raise InputError("input JSON object contains no nodes")

    coords: Coordinates = {}
    for name, value in data.items():
        _check_name(name)
        coords[name] = _as_coordinate(name, value)
    return ParsedInput(coords=coords, repaired_quotes=repaired)
