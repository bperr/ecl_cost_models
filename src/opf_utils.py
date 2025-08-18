from typing import Sequence

import numpy as np

TOL = 1e-3  # Tolerance for equality and inequality assumptions
DEMAND_PRICE = 3000
FAKE_PROD_PRICE = 4000
FAKE_CONS_PRICE = -1000


def build_equations(points, prices) -> tuple:
    """
    Find the coefficients of the trinomial representing the power/cost function on each interval.

    Parameters
    ----------
    points: List of threshold power/cost points
    prices: Corresponding prices interval.

    Returns
    -------
    A sequence of tuple with the trinomial 3 coefficients.
    """
    assert len(prices) == len(points) - 1
    equations = list()  # (a, b, c) such that cost(export=x) = ax²+bx+c
    for i in range(len(prices)):
        x0, c0 = points[i]
        x1, c1 = points[i + 1]
        p0, p1 = prices[i]
        # cost(x0<x<x1) = c0 + (x-x0)*p0 + (x-x0)²/2*(p1-p0)/(x1-x0)
        a = 0.5 * (p1 - p0) / (x1 - x0)
        b = p0 - x0 * (p1 - p0) / (x1 - x0)
        c = c0 - x0 * p0 + x0 * x0 / 2 * (p1 - p0) / (x1 - x0)
        assert_approx(a * x0 * x0 + b * x0 + c, c0)
        assert_approx(a * x1 * x1 + b * x1 + c, c1)
        assert_approx(2 * a * x0 + b, p0)
        equations.append((a, b, c))
    return tuple(equations)


class CostFunction:
    def __init__(self, points_node_scope: Sequence[tuple], prices: Sequence[tuple]):
        """
        This object represents a cost function depending on a power to export. It can correspond to a node (if used in
        node market optimisation), or a node & a line (if used in line export optimisation). If it corresponds to a
        node, to_other_lines_export must be the net power exported by the node. If it corresponds to a node & a line,
        to_other_lines_export must exclude the power exported in the line.
        The points_node_scope is a list of (power, cost), with 'power' the power exported by the node in all its lines.
        The attribute points_line_scope will be a list of (power, cost), with 'power' the power exported by the node in
        the considered line.
        The prices are a list of (price_start, price_full), each corresponding to the interval between 2 points.
        For each interval, a quadratic equation (a, b, c) such that cost(x)=ax²+bx+c, with x the export from the node
        to the considered line.

        Parameters
        ----------
        points_node_scope: List of (power, cost), with 'power' the power exported by the node in all its lines
        prices: List of (price_start, price_full) such that the node market price is between these prices if the export
        is between the associated points
        """
        assert len(points_node_scope) == len(prices) + 1  # prices[i] corresponds to [points[i], points[i+1]]
        self._points = tuple(points_node_scope)  # (export in the node, cost)
        self._prices = tuple(prices)  # (price previous export, price next export)
        self._to_other_lines_export = 0

        # equations[i] corresponds to prices[i] & [points[i], points[i+1]]
        # equations[i] = (ai, bi, ci) such that cost(points[i]<x<points[i+1]) = ai*x²+bi*x+ci
        self._equations = build_equations(points=self._points, prices=prices)

    @property
    def points(self):
        return self._points

    @property
    def prices(self):
        return self._prices

    @property
    def equations(self):
        return self._equations

    def compute_cost(self, power: float):
        """
        Compute the cost based on the net exported power.

        Parameters
        ----------
        power: Net exported power. In MW.

        Returns
        -------
        The cost in €.
        """
        i = self.equation_index(power=power)
        a, b, c = self._equations[i]
        return a * power * power + b * power + c

    def compute_price(self, power: float):
        """
        Compute the price based on the net exported power.

        Parameters
        ----------
        power: Net exported power. In MW.

        Returns
        -------
        The price in €/MWh.
        """
        i = self.equation_index(power=power)  # if 2 intervals include this power, the price is the smallest possible
        price_start, price_full = self._prices[i]
        power_min = self._points[i][0]
        power_max = self._points[i + 1][0]
        assert power_min - TOL <= power <= power_max + TOL
        power = bounded_value(value=power, min_value=power_min, max_value=power_max)
        if price_start == price_full:
            return price_start
        assert power_min < power_max
        return price_start + (price_full - price_start) * (power - power_min) / (power_max - power_min)

    def equation_index(self, power: float) -> int:
        """
        Look of the equation coefficients of the power interval corresponding to the given power.

        Parameters
        ----------
        power: Net exported power. In MW.

        Returns
        -------
        The index of an interval (the smallest if several possibilities) including the input power

        """
        assert self._points[0][0] - TOL <= power <= self._points[-1][0] + TOL
        for i in range(len(self._points) - 1):
            if self._points[i][0] - TOL <= power <= self._points[i + 1][0] + TOL:
                return i

    def update_to_other_lines_export(self, to_other_lines_export: float):
        """
        Parameters
        ----------
        to_other_lines_export: Net power exported by the node, except in the considered line.

        """
        self._to_other_lines_export = to_other_lines_export
        self._points = tuple([(export - to_other_lines_export, cost) for (export, cost) in self._points])
        self._equations = build_equations(points=self._points, prices=self._prices)


class NodeCostFunction(CostFunction):
    def __init__(self, points_node_scope: Sequence[tuple], prices: Sequence[tuple]):
        super().__init__(points_node_scope=points_node_scope, prices=prices)

    def to_line_cost_function(self, to_other_lines_export: float) -> 'LineCostFunction':
        return LineCostFunction(points_node_scope=self._points, prices=self._prices,
                                to_other_lines_export=to_other_lines_export)


class LineCostFunction(CostFunction):
    def __init__(self, points_node_scope: Sequence[tuple], prices: Sequence[tuple], to_other_lines_export: float):
        super().__init__(points_node_scope=points_node_scope, prices=prices)
        self.update_to_other_lines_export(to_other_lines_export=to_other_lines_export)


def solve_trinomial(a: float, b: float, c: float):
    """
    Returns (x1, x2) solutions of a*x² + b*x + c = 0
    """
    delta = b ** 2 - 4 * a * c
    if delta >= 0:
        return ((-b - np.sqrt(delta)) / (2 * a),
                (-b + np.sqrt(delta)) / (2 * a))
    else:
        return None


def minimise_trinomial(a: float, b: float, c: float, x_min: float, x_max: float, x_default: float) \
        -> tuple[float, float]:
    """
    Find the minimum value of a trinomial within a given interval

    Parameters:
    -----------
    a: First coefficient of the trinomial.
    b: Second coefficient of the trinomial.
    c: Third coefficient of the trinomial.
    x_min: Lower bound of the search interval.
    x_max: Upper bound of the search interval.
    x_default: Default value to use if a and b are zero.

    Returns
    -------
    The value for which the trinomial is minimized and its minimum.
    """
    if a == 0:
        if b > 0:
            x = x_min
        elif b < 0:
            x = x_max
        else:
            x = bounded_value(value=x_default, min_value=x_min, max_value=x_max)
    elif a > 0:
        x = bounded_value(value=-b / (2 * a), min_value=x_min, max_value=x_max)
    else:
        if a * x_min * x_min + b * x_min <= a * x_max * x_max + b * x_max:
            x = x_min
        else:
            x = x_max
    return x, a * x * x + b * x + c


def bounded_value(value: float, min_value: float, max_value: float):
    """
    Returns the number the closest to value which is inside [min_value, max_value]

    Parameters
    ----------
    value: The input value
    min_value: The lower bound
    max_value: The upper bound
    """
    assert max_value >= min_value
    return min(max_value, max(min_value, value))


def assert_approx(actual: float, expected: float, tol=TOL):
    assert abs(actual - expected) < tol
