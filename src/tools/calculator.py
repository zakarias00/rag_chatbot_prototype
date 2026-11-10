from __future__ import annotations

import math
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field, StrictFloat, StrictInt, field_validator


def _finite(value: int | float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


class CalculatorInput(BaseModel):
    """A binary arithmetic operation and its two numeric operands."""

    operation: Literal["add", "subtract", "multiply", "divide"]
    operands: list[StrictInt | StrictFloat] = Field(min_length=2, max_length=2)

    @field_validator("operands")
    @classmethod
    def finite_operands(cls, operands: list[int | float]) -> list[int | float]:
        if not all(_finite(value) for value in operands):
            raise ValueError("operands must be finite numbers")
        return operands


@tool(args_schema=CalculatorInput)
def calculator(operation: str, operands: list[int | float]) -> dict:
    """Compute add, subtract, multiply, or divide on two numbers.

    Subtraction and division use the operands in the order provided. The tool
    rejects invalid inputs, division by zero, and non-finite results.
    """
    left, right = operands
    if operation == "add":
        result = left + right
    elif operation == "subtract":
        result = left - right
    elif operation == "multiply":
        result = left * right
    elif operation == "divide":
        if right == 0:
            raise ValueError("cannot divide by zero")
        result = left / right
    else:
        raise ValueError(f"unsupported operation: {operation}")
    if not _finite(result):
        raise ValueError("result must be a finite number")
    return {"operation": operation, "operands": operands, "result": result}
