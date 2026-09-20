import unittest

from calculator import clamp, divide


class CalculatorTests(unittest.TestCase):
    def test_divide_keeps_fraction(self):
        self.assertEqual(divide(7, 2), 3.5)

    def test_divide_by_zero_raises(self):
        with self.assertRaises(ZeroDivisionError):
            divide(1, 0)

    def test_clamp_keeps_value_inside_bounds(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_clamp_limits_low_value(self):
        self.assertEqual(clamp(-2, 0, 10), 0)

    def test_clamp_limits_high_value(self):
        self.assertEqual(clamp(12, 0, 10), 10)


if __name__ == "__main__":
    unittest.main()
