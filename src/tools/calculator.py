"""
Safe calculator tool for mathematical expressions.
"""
from __future__ import annotations

import ast
import operator
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


# Allowed operators
ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class CalculatorTool:
    """Safe calculator for evaluating mathematical expressions."""

    def __init__(self):
        self.allowed_names = {
            "pi": 3.141592653589793,
            "e": 2.718281828459045,
            "sqrt": lambda x: x ** 0.5,
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
        }

    def evaluate(self, expression: str) -> float | int | str:
        """Safely evaluate a mathematical expression."""
        try:
            tree = ast.parse(expression.strip(), mode="eval")
            result = self._eval(tree.body)
            return result
        except SyntaxError:
            return f"Error: Invalid syntax in expression: {expression}"
        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error: {e}"

    def _eval(self, node) -> float | int:
        """Evaluate an AST node safely."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant: {type(node.value)}")

        if isinstance(node, ast.Name):
            if node.id in self.allowed_names:
                return self.allowed_names[node.id]
            raise NameError(f"Variable '{node.id}' not allowed")

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPS:
                raise ValueError(f"Operator {type(node.op).__name__} not allowed")
            left = self._eval(node.left)
            right = self._eval(node.right)
            return ALLOWED_OPS[op_type](left, right)

        if isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in ALLOWED_OPS:
                raise ValueError(f"Unary operator {type(node.op).__name__} not allowed")
            operand = self._eval(node.operand)
            return ALLOWED_OPS[op_type](operand)

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls allowed")
            func_name = node.func.id
            if func_name not in self.allowed_names:
                raise NameError(f"Function '{func_name}' not allowed")
            args = [self._eval(arg) for arg in node.args]
            return self.allowed_names[func_name](*args)

        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    def calculate_statistics(self, numbers: list[float], operation: str = "mean") -> dict[str, float]:
        """Calculate statistical measures."""
        if not numbers:
            return {"error": "Empty list"}

        result = {}
        if operation in ("mean", "all"):
            result["mean"] = sum(numbers) / len(numbers)
        if operation in ("median", "all"):
            sorted_nums = sorted(numbers)
            n = len(sorted_nums)
            if n % 2 == 0:
                result["median"] = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
            else:
                result["median"] = sorted_nums[n // 2]
        if operation in ("min", "all"):
            result["min"] = min(numbers)
        if operation in ("max", "all"):
            result["max"] = max(numbers)
        if operation in ("range", "all"):
            result["range"] = max(numbers) - min(numbers)
        if operation in ("sum", "all"):
            result["sum"] = sum(numbers)
        if operation in ("count", "all"):
            result["count"] = len(numbers)

        return result

    def convert_units(self, value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
        """Simple unit conversions."""
        conversions = {
            # Length
            ("km", "miles"): lambda x: x * 0.621371,
            ("miles", "km"): lambda x: x / 0.621371,
            ("m", "ft"): lambda x: x * 3.28084,
            ("ft", "m"): lambda x: x / 3.28084,
            ("cm", "inches"): lambda x: x / 2.54,
            ("inches", "cm"): lambda x: x * 2.54,
            # Weight
            ("kg", "lbs"): lambda x: x * 2.20462,
            ("lbs", "kg"): lambda x: x / 2.20462,
            ("g", "oz"): lambda x: x / 28.3495,
            ("oz", "g"): lambda x: x * 28.3495,
            # Temperature
            ("c", "f"): lambda x: x * 9/5 + 32,
            ("f", "c"): lambda x: (x - 32) * 5/9,
            # Volume
            ("l", "gal"): lambda x: x / 3.78541,
            ("gal", "l"): lambda x: x * 3.78541,
            ("ml", "fl_oz"): lambda x: x / 29.5735,
            ("fl_oz", "ml"): lambda x: x * 29.5735,
        }

        key = (from_unit.lower(), to_unit.lower())
        if key in conversions:
            result = conversions[key](value)
            return {"value": result, "from": from_unit, "to": to_unit, "original": value}

        return {"error": f"Conversion from {from_unit} to {to_unit} not supported"}


_calculator_tool: CalculatorTool | None = None


def get_calculator_tool() -> CalculatorTool:
    global _calculator_tool
    if _calculator_tool is None:
        _calculator_tool = CalculatorTool()
    return _calculator_tool
