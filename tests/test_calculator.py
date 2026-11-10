import pytest

from src.tools.calculator import calculator


@pytest.mark.parametrize(
    ("operation", "operands", "expected"),
    [
        ("add", [12, 7], 19),
        ("subtract", [12, 7], 5),
        ("multiply", [12, 7], 84),
        ("divide", [12, 7], 12 / 7),
        ("multiply", [-1.5, 2], -3),
    ],
)
def test_calculator_operations(operation, operands, expected):
    response = calculator.invoke({"operation": operation, "operands": operands})
    assert response == {"operation": operation, "operands": operands, "result": expected}


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "divide", "operands": [12, 0]},
        {"operation": "divide", "operands": [12, -0.0]},
        {"operation": "power", "operands": [2, 3]},
        {"operation": "add", "operands": [1]},
        {"operation": "add", "operands": [1, 2, 3]},
        {"operation": "add", "operands": [True, 2]},
        {"operation": "add", "operands": ["2", 3]},
        {"operation": "add", "operands": [float("nan"), 1]},
        {"operation": "add", "operands": [float("inf"), 1]},
        {"operation": "multiply", "operands": [1e308, 1e308]},
    ],
)
def test_calculator_rejects_invalid_inputs(payload):
    with pytest.raises(ValueError):
        calculator.invoke(payload)
