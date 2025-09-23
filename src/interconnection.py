from __future__ import annotations  # Postpones annotation checking

from typing import TYPE_CHECKING

from src.opf_utils import LineCostFunction, TOL, bounded_value, minimise_trinomial
from src.tmp import plot_line_cost_function

if TYPE_CHECKING:  # False at runtime
    from zone import Zone  # Import zone only during type checking, not at runtime

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


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

    def __str__(self):
        return f"{self._zone_from.name} -> {self._zone_to.name}"

    @property
    def zone_from(self):
        return self._zone_from

    @property
    def zone_to(self):
        return self._zone_to

    @property
    def power_rating(self):
        return self._power_rating

    @property
    def historical_powers(self):
        return self._historical_powers.copy()

    def historical_power(self, timestep: pd.Timestamp):
        return self._historical_powers[timestep]

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

        cost_change = best_cost - current_cost

        if cost_change > TOL:  # >0
            print("!!!!!!!!!!!!!!!!!!!!!!! Error: cost has increased !!!!!!!!!!!!!!!!!!!!!!!")
            print(f"current: {self._current_power}MW --> {current_cost}€")
            print(f"best: {best_export}MW --> {best_cost}€")
            print(f"{self._zone_from.name}-{self.zone_to.name}")
            print(f"Power rating: {self._power_rating}")
            print(f"from prices: {from_cost_function.prices}")
            print(f"from costs: {from_cost_function.points}")
            print(f"to prices: {to_cost_function.prices}")
            print(f"to costs: {to_cost_function.points}")
            plot_line_cost_function(self, from_cost_function=from_cost_function,to_cost_function=to_cost_function)
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

        # Test all threshold points within [x0 ; x2]
        threshold_points_cost_list = [(x0, cost0), (x2, cost2)]
        for x_from, from_cost in from_points:
            if x0 < x_from < x2:
                threshold_points_cost_list.append((x_from, from_cost + to_cost_function.compute_cost(power=-x_from)))
        for x_to, to_cost in to_points:
            x_from = -x_to
            if x0 < x_from < x2:
                threshold_points_cost_list.append((x_from, from_cost_function.compute_cost(power=x_from) + to_cost))

        # Sort by power
        threshold_points_cost = np.array(threshold_points_cost_list)
        threshold_points_cost = threshold_points_cost[threshold_points_cost[:, 0].argsort()]

        # Remove duplicate/close points
        power_diff = np.concatenate(([np.inf], np.diff(threshold_points_cost[:, 0])))
        threshold_points_cost = threshold_points_cost[power_diff > TOL]

        # Find minimum cost
        min_cost = threshold_points_cost[:, 1].min()
        min_cost_indexes = np.where(abs(threshold_points_cost[:, 1] - min_cost) <= TOL)[0]

        if len(min_cost_indexes) > 2:
            # There are more than two threshold powers with minimum cost. The cost function is constant between them!
            # As the total cost function is convex, their index in threshold_points_cost should be consecutive.
            sorted_min_cost_indexes = sorted(min_cost_indexes)
            assert all(value - idx == sorted_min_cost_indexes[0] for idx, value in enumerate(sorted_min_cost_indexes))
            # Any value on all intervals gives minimum cost. Thus, we return the closest one to zero
            power_min = threshold_points_cost[sorted_min_cost_indexes[0]][0]
            power_max = threshold_points_cost[sorted_min_cost_indexes[-1]][0]
            return bounded_value(value=0, min_value=power_min, max_value=power_max), min_cost

        elif len(min_cost_indexes) == 2:
            # Minimum cost is between these two powers. Their index should be consecutive.
            sorted_min_cost_indexes = sorted(min_cost_indexes)
            assert sorted_min_cost_indexes[0] + 1 == sorted_min_cost_indexes[1]
            power_min = threshold_points_cost[sorted_min_cost_indexes[0]][0]
            power_max = threshold_points_cost[sorted_min_cost_indexes[1]][0]
            # Find minimum of polynomial function
            a_from, b_from, c_from = from_equations[from_cost_function.equation_index(power=(power_min + power_max) / 2)]
            a_to, b_to, c_to = to_equations[to_cost_function.equation_index(power=-(power_min + power_max) / 2)]
            a = a_from + a_to
            b = b_from - b_to
            c = c_from + c_to
            return minimise_trinomial(a=a, b=b, c=c, x_min=power_min, x_max=power_max, x_default=0)

        else:
            min_cost_index = min_cost_indexes[0]
            # We can look for the minimum price in the two power intervals around min_cost_index
            if min_cost_index == 0:
                x0 = threshold_points_cost[min_cost_index][0]
                x1 = threshold_points_cost[min_cost_index][0]
                x2 = threshold_points_cost[min_cost_index + 1][0]
            elif min_cost_index == len(threshold_points_cost) - 1:
                x0 = threshold_points_cost[min_cost_index - 1][0]
                x1 = threshold_points_cost[min_cost_index][0]
                x2 = threshold_points_cost[min_cost_index][0]
            else:
                x0 = threshold_points_cost[min_cost_index - 1][0]
                x1 = threshold_points_cost[min_cost_index][0]
                x2 = threshold_points_cost[min_cost_index + 1][0]

            # The polynomial coefficients on [x0 ; x1] and [x1; x2] will not change for both cost function
            # We can minimise the overall cost function on both intervals
            # cost(x) = (a1 + a2) * x² + (b1 - b2) * x + (c1 + c2)

            # - On [x0 ; x1]
            if x0 == x1:
                x01, cost01 = x0, from_cost_function.compute_cost(power=x0) + to_cost_function.compute_cost(power=-x0)
            else:
                a01f, b01f, c01f = from_equations[from_cost_function.equation_index(power=(x0 + x1) / 2)]
                a01t, b01t, c01t = to_equations[to_cost_function.equation_index(power=-(x0 + x1) / 2)]
                a01 = a01f + a01t
                b01 = b01f - b01t
                c01 = c01f + c01t
                x01, cost01 = minimise_trinomial(a=a01, b=b01, c=c01, x_min=x0, x_max=x1, x_default=0)

            # - On [x1 ; x2]
            if x2 == x1:
                x12, cost12 = x2, from_cost_function.compute_cost(power=x2) + to_cost_function.compute_cost(power=-x2)
            else:
                a12f, b12f, c12f = from_equations[from_cost_function.equation_index(power=(x1 + x2) / 2)]
                a12t, b12t, c12t = to_equations[to_cost_function.equation_index(power=-(x1 + x2) / 2)]
                a12 = a12f + a12t
                b12 = b12f - b12t
                c12 = c12f + c12t
                x12, cost12 = minimise_trinomial(a=a12, b=b12, c=c12, x_min=x1, x_max=x2, x_default=0)

            # Return the minimum cost
            if cost01 < cost12:
                x, cost = x01, cost01
            elif cost12 < cost01:
                x, cost = x12, cost12
            else:  # cost01 = cost12
                # Choose the smallest export (in absolute value)
                x, cost = min(x01, x12, key=lambda value: abs(value)), cost01

            return x, cost

    def compare_power_series(self, path):
        """
        Generate and save plots comparing simulated vs historical powers for the interconnection,
        and compute error metrics quantifying the differences

        Parameters
        ----------
        path:Path: Directory path where the generated comparison plots will be saved

        :return zone_error_data: Dictionary containing error metrics for the interconnection
        """
        historical_energy = self._historical_powers.sum()  # MWh
        simulated_energy = self._simulated_powers.sum()  # MWh
        # If linear interpolation between power values :
        # historical_energy = np.trapezoid(self._historical_powers.values, dx=1)  # dx=1h
        # simulated_energy = np.trapezoid(self._historical_powers.values, dx=1)  # dx=1h

        power_error_series = self.historical_powers - self._simulated_powers  # MW
        energy_error = historical_energy - simulated_energy  # MWh

        # Relative Energy error - difference of simulated & historical energy (sum of powers) - (value - MWh)
        relative_total_energy_difference = energy_error / abs(historical_energy) if historical_energy != 0 else (
            0 if simulated_energy == 0 else np.nan)
        # Relative Energy of the power error - energy (sum) of differences of powers - (value - MWh)
        cumulative_relative_energy_error = abs(power_error_series).sum() / abs(historical_energy) if (
                historical_energy != 0) else (0 if (power_error_series == 0).all() else np.nan)

        # Mean absolute error of powers - (value - MW)
        power_MAE = np.mean(abs(power_error_series))
        # Relative error of powers - (time series - MW)
        relative_power_error_series = (
            pd.Series(0, index=self._historical_powers.index)
            if (self._historical_powers == 0).all() and (self._simulated_powers == 0).all()
            else (abs(power_error_series) / abs(self._historical_powers).replace(0, np.nan)).dropna()
        )

        # Maximum and mean relative error of powers (value - MW)
        max_relative_power_error = relative_power_error_series.max()
        mean_relative_power_error = relative_power_error_series.mean()

        line_errors_data = {
            "line": f"{self._zone_from.name}-{self._zone_to.name}",
            "relative_total_energy_error": round(float(relative_total_energy_difference), 3),
            "cumulative_relative_energy_error": round(float(cumulative_relative_energy_error), 3),
            "max_relative_power_error": round(float(max_relative_power_error), 3),
            "mean_relative_power_error": round(float(mean_relative_power_error), 3),
            "mean_absolute_error_MW": round(float(power_MAE), 3),
        }

        self.plot_power_errors(line_errors_data, path)
        return line_errors_data

    def plot_power_errors(self, line_errors_data, path):
        """
        Plot and save a comparison graph of simulated vs historical powers for the interconnection

        Parameters
        ----------
        path:Path: Directory path where the generated comparison plot is saved

        line_errors_data : Dictionary containing error metrics for the interconnection
        """
        path.mkdir(parents=True, exist_ok=True)

        max_relative_power_error = line_errors_data["max_relative_power_error"]
        mean_relative_power_error = line_errors_data["mean_relative_power_error"]
        relative_total_energy_error = line_errors_data["relative_total_energy_error"]
        cumulative_relative_energy_error = line_errors_data["cumulative_relative_energy_error"]

        plt.figure(figsize=(10, 6))
        self._historical_powers.plot(label='Historical', linewidth=0.5, drawstyle='steps-post')
        self._simulated_powers.plot(label='Simulation', linewidth=0.5, linestyle='--', drawstyle='steps-post')
        plt.axhline(0, color='red', linestyle='-', linewidth=1.5, alpha=0.7)

        plt.legend()
        plt.title(f"interconnection {self._zone_from.name}-{self._zone_to.name}")
        plt.xlabel("Timestep")
        plt.ylabel("Power (MW)")

        if self.historical_powers.min() > 0 and self._simulated_powers.min() > 0:
            plt.ylim(bottom=0)

        error_text = (f"Max error : {max_relative_power_error:.2%}\n"
                      f"Mean error : {mean_relative_power_error:.2%}\n"
                      f"Cumulative energy error : {cumulative_relative_energy_error:.2%}\n"
                      f"Total energy error : {relative_total_energy_error:.2%}"
                      )
        plt.text(0.05, 0.95, error_text, transform=plt.gca().transAxes,
                 fontsize=10, verticalalignment='top', bbox=dict(facecolor='white', alpha=0.6))

        # Saving
        file_name = f"{self._zone_from.name}-{self._zone_to.name}_interconnection_comparison.png".replace(" ", "_")
        file_path = path / f"{file_name}"
        plt.tight_layout()
        plt.savefig(file_path)
        plt.close()

OUT_ZONE_NAME = "OUTSIDE"


class ExteriorInterconnection(Interconnection):
    """
    This class allows to represent a connection with zones that are not modelled.
    The net export of this connection is fixed.
    """

    def __init__(self, zone_from: Zone, zone_to: Zone, historical_power_flows: pd.Series):
        power_rating = 1e9
        assert zone_to.name == OUT_ZONE_NAME
        super().__init__(zone_from, zone_to, power_rating, historical_power_flows)

    def optimise_export(self, timestep: pd.Timestamp) -> float:
        """
        For an :class:`ExteriorInterconnection`, there is nothing to optimise: the export remains the same as the
        historical one. Thus, set_power is not called and the cost benefit is zero because nothing has changed.

        Parameters
        ----------
        timestep: (unused) Timestamp currently simulated.

        Returns
        -------
        Zero, as nothing is optimised here.
        """
        return 0
