"""Parse the few arithmetic question forms supported by the calculator tool."""
from __future__ import annotations

import math
import re

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
EXPRESSION = re.compile(rf"(?<![\w.])({NUMBER})\s*([+*×/\-])\s*({NUMBER})(?![\w.])")
PER_DAY = re.compile(rf"({NUMBER})\s*(KB|MB|GB)\s+per\s+day\b.*?\b(?:for|after|over|in)\s+({NUMBER})\s+days?\b", re.I)
WORDS_OP = re.compile(rf"\b(multiply|divide|add|subtract)\s+({NUMBER})\s+(by|and|from)\s+({NUMBER})\b", re.I)

def number(text: str) -> int | float:
    if "." not in text:
        return int(text)
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Number must be finite")
    return int(value) if value.is_integer() else value


def parse_calculation(question: str) -> tuple[dict | None, tuple[int, int] | None]:
    """Recognize a single arithmetic expression; never evaluate arbitrary code."""
    match = PER_DAY.search(question)
    if match:
        return {
            "operation": "multiply", "operands": [number(match[1]), number(match[3])],
            "unit": match[2].upper(),
        }, match.span()

    match = WORDS_OP.search(question)
    if match:
        operation, left, connector, right = (part.lower() for part in match.groups())
        if connector != {"multiply": "by", "divide": "by", "add": "and", "subtract": "from"}[operation]:
            return None, None
        operands = [number(left), number(right)]
        if operation == "subtract":
            operands.reverse()  # "subtract 2 from 9" -> 9 - 2
        return {"operation": operation, "operands": operands}, match.span()

    match = EXPRESSION.search(question)
    if match:
        operation = {"+": "add", "-": "subtract", "*": "multiply", "×": "multiply", "/": "divide"}[match[2]]
        return {"operation": operation, "operands": [number(match[1]), number(match[3])]}, match.span()
    return None, None


