"""
Tests for safe calculator tool.
"""
from __future__ import annotations

import pytest

from src.tools.calculator import CalculatorTool


class TestCalculatorTool:
    def setup_method(self):
        self.calc = CalculatorTool()

    def test_add(self):
        assert self.calc.evaluate("2 + 3") == 5

    def test_subtract(self):
        assert self.calc.evaluate("10 - 4") == 6

    def test_multiply(self):
        assert self.calc.evaluate("3 * 7") == 21

    def test_divide(self):
        assert self.calc.evaluate("15 / 3") == 5.0

    def test_power(self):
        assert self.calc.evaluate("2 ** 3") == 8

    def test_floor_div(self):
        assert self.calc.evaluate("10 // 3") == 3

    def test_modulo(self):
        assert self.calc.evaluate("10 % 3") == 1

    def test_unary_negation(self):
        assert self.calc.evaluate("-5") == -5

    def test_complex_expression(self):
        assert self.calc.evaluate("(2 + 3) * 4") == 20

    def test_pi_constant(self):
        import math
        assert self.calc.evaluate("pi") == pytest.approx(math.pi)

    def test_e_constant(self):
        import math
        assert self.calc.evaluate("e") == pytest.approx(math.e)

    def test_sqrt_function(self):
        assert self.calc.evaluate("sqrt(16)") == 4.0

    def test_abs_function(self):
        assert self.calc.evaluate("abs(-10)") == 10

    def test_round_function(self):
        assert self.calc.evaluate("round(3.7)") == 4

    def test_syntax_error(self):
        result = self.calc.evaluate("2 + +")
        assert "Error" in str(result)

    def test_division_by_zero(self):
        result = self.calc.evaluate("1 / 0")
        assert "Error" in str(result)

    def test_unsupported_variable(self):
        result = self.calc.evaluate("x + 1")
        assert "Error" in str(result)

    def test_invalid_expression(self):
        result = self.calc.evaluate("abc")
        assert "Error" in str(result)

    def test_statistics_all(self):
        result = self.calc.calculate_statistics([1, 2, 3, 4, 5], "all")
        assert result["mean"] == 3.0
        assert result["median"] == 3
        assert result["min"] == 1
        assert result["max"] == 5
        assert result["range"] == 4
        assert result["sum"] == 15
        assert result["count"] == 5

    def test_statistics_mean_only(self):
        result = self.calc.calculate_statistics([10, 20, 30], "mean")
        assert result["mean"] == 20.0
        assert "median" not in result

    def test_statistics_empty(self):
        result = self.calc.calculate_statistics([], "mean")
        assert "error" in result

    def test_statistics_even_median(self):
        result = self.calc.calculate_statistics([1, 2, 3, 4], "median")
        assert result["median"] == 2.5

    def test_statistics_odd_median(self):
        result = self.calc.calculate_statistics([1, 2, 3], "median")
        assert result["median"] == 2

    def test_convert_km_to_miles(self):
        result = self.calc.convert_units(10, "km", "miles")
        assert abs(result["value"] - 6.21371) < 0.001

    def test_convert_c_to_f(self):
        result = self.calc.convert_units(0, "c", "f")
        assert result["value"] == 32.0

    def test_convert_f_to_c(self):
        result = self.calc.convert_units(32, "f", "c")
        assert result["value"] == 0.0

    def test_convert_kg_to_lbs(self):
        result = self.calc.convert_units(1, "kg", "lbs")
        assert abs(result["value"] - 2.20462) < 0.001

    def test_convert_l_to_gal(self):
        result = self.calc.convert_units(3.78541, "l", "gal")
        assert abs(result["value"] - 1.0) < 0.001

    def test_convert_unsupported(self):
        result = self.calc.convert_units(10, "celsius", "kelvin")
        assert "error" in result

    def test_call_name_not_allowed(self):
        result = self.calc.evaluate("print(1)")
        assert "Error" in str(result)

    def test_unsupported_constant_type(self):
        result = self.calc.evaluate("'string'")
        assert "Error" in str(result)


def test_get_calculator_tool():
    from src.tools.calculator import get_calculator_tool
    tool = get_calculator_tool()
    assert tool is not None
    assert isinstance(tool, CalculatorTool)
