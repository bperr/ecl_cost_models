from __future__ import annotations  # Postpones annotation checking

from typing import TYPE_CHECKING

import numpy as np
from matplotlib import pyplot as plt

from src.opf_utils import LineCostFunction, TOL, minimise_trinomial

if TYPE_CHECKING:  # False at runtime
    from zone import Zone  # Import zone only during type checking, not at runtime

import pandas as pd


class Interconnection:
    """
    Represents an electrical interconnection between two countries.

    This class models an interconnection from a source zone (`zone_from`)
    to a destination zone (`zone_to`) with a maximum power capacity (`power_rating`).
    It stores incoming and outgoing power values at different time steps.

    Attributes:
        _zone_from (Zone): The source zone of the interconnection.
        _zone_to (Zone): The destination zone of the interconnection.
        _power_rating (float): The maximum power capacity of the interconnection (in MW).
        _historical_powers (pd Series): stores incoming power values (in MW) by time step.
        _simulated_powers (pd Series): stores outgoing power values (in MW) by time step.
    """

    def __init__(self, zone_from: Zone, zone_to: Zone, power_rating: float, historical_power_flows: pd.Series):
        self._zone_from = zone_from  # Zone object
        self._zone_to = zone_to  # Zone_object
        self._power_rating = power_rating  # MW
        self._historical_powers = historical_power_flows  # MW
        self._simulated_powers = pd.Series()  # MW

        # -- "Variable" attribute for OPF computation
        self._current_power = 0

    @property
    def zone_from(self):
        return self._zone_from

    @property
    def zone_to(self):
        return self._zone_to

    @property
    def historical_powers(self):
        return self._historical_powers.copy()

    def store_simulated_power(self, timestep: pd.Timestamp):
        """
        Updates the simulated powers series (transferred in the connection) by storing the current power stored in
        self._current_power and calculated during the OPF at the specified timestep and then resets the current
        power to zero (so that the next timesteps data can be saved)

        :param timestep: The timestep at which the current power should be recorded
        """
        self._simulated_powers[timestep] = self._current_power
        self._current_power = 0

    # -- Methods for OPF resolution -- #
    def get_export(self, zone: Zone) -> float:
        """
        Parameters
        ----------
        zone: from node or to node

        Returns
        -------
        Net power exported from the node to the line
        """
        if zone == self._zone_from:
            return self._current_power
        else:
            assert zone == self._zone_to
            return -self._current_power

    def set_export(self, power: float):
        """
        Modify export in the line, and update current export of both connected nodes

        Parameters
        ----------
        power: Net power entering the line at the to node
        """
        self._current_power = power
        for zone in (self._zone_from, self._zone_to):
            zone.update_current_export()

    def optimise_export(self, timestep: pd.Timestamp) -> float:
        """
        Optimise the export in the line to minimise the system cost

        Returns
        -------
        Cost change (<= 0) due to the optimisation
        """
        # Export of from_node not using this line
        from_node_to_other_lines_export = self._zone_from.get_current_export() - self._current_power
        # Export of to_node not using this line
        to_node_to_other_lines_export = self._zone_to.get_current_export() + self._current_power

        from_cost_function = self._zone_from.get_cost_function(timestep).to_line_cost_function(
            to_other_lines_export=from_node_to_other_lines_export)
        to_cost_function = self._zone_to.get_cost_function(timestep).to_line_cost_function(
            to_other_lines_export=to_node_to_other_lines_export)

        current_cost = (from_cost_function.compute_cost(power=self._current_power)
                        + to_cost_function.compute_cost(power=-self._current_power))
        best_export, best_cost = self._optimise_export(from_cost_function=from_cost_function,
                                                       to_cost_function=to_cost_function)

        # ------  Uncomment his for debugging purposes ------- #
        # # Plot the total cost function with threshold powers points in blue and "normal" powers in orange
        # #
        # threshold_powers = sorted(filter(
        #     lambda pw: abs(pw) <= self._power_rating,
        #     list(np.array(from_cost_function.points)[:, 0])
        #     + list(map(lambda pw: -pw, np.array(to_cost_function.points)[:, 0]))
        # ))
        # # Compute total cost on threshold powers
        # power_total_cost_points = []
        # for power in threshold_powers:
        #     try:
        #         cost = from_cost_function.compute_cost(power) + to_cost_function.compute_cost(-power)
        #         power_total_cost_points.append((power, cost))
        #     except AssertionError:
        #         pass
        # # Compute total cost on any power
        # power_total_cost_curve = []
        # for power in np.linspace(-self._power_rating, self._power_rating, 200):
        #     try:
        #         cost = from_cost_function.compute_cost(power) + to_cost_function.compute_cost(-power)
        #         power_total_cost_curve.append((power, cost))
        #     except AssertionError:
        #         pass
        # # Convert to numpy array
        # power_total_cost_points = np.array(power_total_cost_points)
        # power_total_cost_curve = np.array(power_total_cost_curve)
        #
        # print(f"Old: {self._current_power} MW --> {current_cost} €")
        # print(f"New: {best_export} MW --> {best_cost} €")
        #
        # # Plot
        # plt.figure()
        # plt.scatter(power_total_cost_points[:, 0], power_total_cost_points[:, 1])
        # plt.scatter(power_total_cost_curve[:, 0], power_total_cost_curve[:, 1], s=5)
        # plt.xlabel("Power (MW)")
        # plt.ylabel("Cost (€)")
        # plt.title(f"Total cost depending on {self._zone_from.name} net export to {self._zone_to.name}")
        # plt.show()

        cost_change = best_cost - current_cost

        if cost_change > TOL:  # >0
            print("!!!!!!!!!!!!!!!!!!!!!!! Error: cost has increased !!!!!!!!!!!!!!!!!!!!!!!")
        self.set_export(power=best_export)
        return cost_change

    def _optimise_export(self, from_cost_function: LineCostFunction, to_cost_function: LineCostFunction) \
            -> (float, float):

        # Let x be the net export in the line, cf the 'from' cost function and ct the 'to' cost function
        # cost(x) = cf(x) + ct(-x)
        #  - cf(x) = a1*x² + b1*x + c1 with a1,b1,c1 constant on a given interval of x
        #  - ct(-x) = a2*x² - b2*x + c2 with a2,b2,c2 constant on a given interval of -x
        # Thus, on a given interval where the two cost function do not change their polynomial parameters, we have
        # cost(x) = (a1+a2)*x² + (b1-b2)*x + (c1+c2)
        #
        # The idea of this algorithm implemented in this method is to find such an interval by evaluating the two cost
        # functions on the threshold powers x (when the cost function polynomial parameters change).
        # To be more precise, the evaluation of the total cost on these threshold powers lead to the delimitation of
        # two neighbors intervals [x0 ; x1] and [x1 ; x2] inside which the polynomial parameters are constant.
        # We can then minimise the cost function on these two intervals and return the global minimum of the total cost
        # function.
        #

        x_default = 0

        from_points = from_cost_function.points  # points at the line scope
        to_points = to_cost_function.points
        from_equations = from_cost_function.equations
        to_equations = to_cost_function.equations

        # -- Base case
        if len(from_points) == 1:
            best_export, cost1 = from_points[0]
            best_import = -best_export  # injected by the from_node to the line
            assert max(best_export, best_import) <= self._power_rating
            assert to_points[0][0] <= best_import <= to_points[-1][0]
            cost2 = to_cost_function.compute_cost(power=best_import)
            return best_export, cost1 + cost2

        # -- Classic resolution:
        # Look for x0 <= x1 <= x2 such that cost(x0) >= cost(x1) <= cost(x2)
        # and both from/to cost functions are defined in [x0, x2]
        # and neither from/to equation change in [x0, x1] nor in [x1, x2]

        # Initialise x0 & x2 to ensure both from/to cost functions are defined on [x0, x2]
        x0 = max(from_points[0][0], -to_points[-1][0], -self._power_rating)
        x2 = min(from_points[-1][0], -to_points[0][0], self._power_rating)
        assert x0 <= x2  # else there is no common interval on which both from/to cost functions are defined

        cost0 = from_cost_function.compute_cost(power=x0) + to_cost_function.compute_cost(power=-x0)
        cost2 = from_cost_function.compute_cost(power=x2) + to_cost_function.compute_cost(power=-x2)
        if x0 == x2:
            return x0, cost0
        if cost0 <= cost2:
            x1 = x0
            cost1 = cost0
        else:
            x1 = x2
            cost1 = cost2

        # Using threshold powers of 'from' cost function, reduce the search intervals [x0 ; x1] and [x1 ; x2]
        for x3, from_cost3 in from_points:
            if x0 < x3 < x2:
                cost3 = from_cost3 + to_cost_function.compute_cost(power=-x3)
                if x3 < x1:
                    if cost3 < cost1:
                        x2, cost2 = x1, cost1
                        x1, cost1 = x3, cost3
                    else:
                        x0, cost0 = x3, cost3
                elif x3 > x1:
                    if cost3 < cost1:
                        x0, cost0 = x1, cost1
                        x1, cost1 = x3, cost3
                    else:
                        x2, cost2 = x3, cost3

        # Using threshold powers of 'to' cost function, reduce the search intervals [x0 ; x1] and [x1 ; x2]
        for x3_to, to_cost3 in to_points:
            x3 = -x3_to  # Threshold net export of to_cost_function becomes the opposite at the 'from' side of the line
            if x0 < x3 < x2:
                cost3 = from_cost_function.compute_cost(power=x3) + to_cost3
                if x3 < x1:
                    if cost3 < cost1:
                        x2, cost2 = x1, cost1
                        x1, cost1 = x3, cost3
                    else:
                        x0, cost0 = x3, cost3
                elif x3 > x1:
                    if cost3 < cost1:
                        x0, cost0 = x1, cost1
                        x1, cost1 = x3, cost3
                    else:
                        x2, cost2 = x3, cost3

        # The polynomial coefficients on the new [x0 ; x1] and [x1; x2] will not change for both cost function
        # We can minimise the overall cost function on both intervals
        # cost(x) = (a1 + a2) * x² + (b1 - b2) * x + (c1 + c2)

        # - On [x0 ; x1]
        a01f, b01f, c01f = from_equations[from_cost_function.equation_index(power=(x0 + x1) / 2)]
        a01t, b01t, c01t = to_equations[to_cost_function.equation_index(power=-(x0 + x1) / 2)]
        a01 = a01f + a01t
        b01 = b01f - b01t
        c01 = c01f + c01t
        x01, cost01 = minimise_trinomial(a=a01, b=b01, c=c01, x_min=x0, x_max=x1, x_default=x_default)

        # - On [x1 ; x2]
        a12f, b12f, c12f = from_equations[from_cost_function.equation_index(power=(x1 + x2) / 2)]
        a12t, b12t, c12t = to_equations[to_cost_function.equation_index(power=-(x1 + x2) / 2)]
        a12 = a12f + a12t
        b12 = b12f - b12t
        c12 = c12f + c12t
        x12, cost12 = minimise_trinomial(a=a12, b=b12, c=c12, x_min=x1, x_max=x2, x_default=x_default)

        # Return the minimum cost
        if cost01 < cost12:
            x, cost = x01, cost01
        elif cost12 < cost01:
            x, cost = x12, cost12
        else:  # cost01 = cost12
            if x_default <= x01:
                x, cost = x01, cost01
            elif x_default <= x1:
                x, cost = x_default, a01 * x_default * x_default + b01 * x_default + c01
            elif x_default <= x12:
                x, cost = x_default, a12 * x_default * x_default + b12 * x_default + c12
            else:
                x, cost = x12, cost12
        return x, cost

    def reset_power(self):
        """
        The export in the line is reset to 0
        """
        self._current_power = 0
