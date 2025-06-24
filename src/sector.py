import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.optimize import minimize


class Sector:
    """
        Represents an energy producing sector (among main sectors defined in the User Inputs) within a zone, some
        sectors are also "consuming" power (storages that store energy).

        This class handles the historical power data of the sector, models its availability,
        and builds a price model based on historical energy prices and power usage.
    """

    def __init__(self, sector_name: str, historical_powers: pd.Series, is_controllable: bool, is_load: bool = False):
        """
            Initializes a new Sector instance.
            :param sector_name: Name of the sector.
            :param historical_powers: Historical power consumption (negative) or production (positive) in MW
            :param is_controllable: Whether the sector's power usage is controllable.
            :param is_load: Whether the sector is a consumer (True) or producer (False).
        """
        self._name: str = sector_name
        self._historical_powers: pd.Series = historical_powers  # in MW

        self._price_model = tuple()  # (price_no_power, price_full_power) in €/MWh
        self._is_controllable = is_controllable
        self._is_load = is_load

        self._powers_out = pd.Series()  # in MW
        self._availabilities = pd.Series()  # in MW

    @property
    def name(self):
        """Returns the name of the sector."""
        return self._name

    @property
    def is_load(self):
        """Returns True if the sector is a consumer (load), otherwise False."""
        return self._is_load

    def _compute_use_ratio(self, price: float, price_no_power: float, price_full_power: float):
        """
        Computes the use ratio for a given electricity price and given model prices

        :param price: Electricity price (€/MWh)
        :param price_no_power: Price where power usage starts (threshold) in €/MWh
        :param price_full_power: Price where full power usage is reached in €/MWh

        :return:
            float : The use ratio (between 0 and 1 for production, 0 and -1 for consumption)
        """

        if price_no_power == price_full_power:
            if self.is_load:
                return -1 if price <= price_no_power else 0
            else:
                return 1 if price >= price_no_power else 0

        if self.is_load:
            if price >= price_no_power:
                return 0
            if price <= price_full_power:
                return -1
            return - (price - price_no_power) / (price_full_power - price_no_power)
        else:  # production mode
            if price <= price_no_power:
                return 0
            if price >= price_full_power:
                return 1
            return (price - price_no_power) / (price_full_power - price_no_power)

    def build_price_model(self, historical_prices: pd.Series, prices_init: tuple, zone_name: str):
        """
            Builds a price model based on historical prices and power use.
            Updates the attribute _price_model = (price_no_power, price_full_power)
            These prices are set as (None,None) if there is no data available for the zone or sector

            The model is optimized to minimize the difference between real and modelled mean and standard deviation
            of the use ratio. Use ratio is calculated as historical_power / availability at each time step
            (not considered when there is no available power)

            The initialisation of the prices is made by finding the minimum loss with the
            initialisation bounds and step (prices_init).

            :param historical_prices: Historical energy prices for the zone concerned
            :param prices_init: Tuple of bounds and step size for price search
            :param zone_name: Name of the zone (for warning messages and output labeling).
        """

        powers_check = self._historical_powers.replace(0, pd.NA).dropna()
        prices_check = historical_prices.replace(0, pd.NA).dropna()

        if prices_check.empty:
            self._price_model = (None, None)
            return

        if powers_check.empty:
            self._price_model = (None, None)
            warnings.warn(f"No data available or no production for {self.name} in {zone_name}, "
                          f"skipping plot.", RuntimeWarning)
            return

        def error_function(x: np.array):
            """
            Compute error between the modeled and historical use ratios distributions,
            using statistical moments (mean and std) of power.

            :param x: [price_no_power, price_full_power]
            :return: error based on difference in moments
            """

            modelled_use_ratios = []

            for price in historical_prices:
                use_ratio = self._compute_use_ratio(
                    price=price,
                    price_no_power=x[0],
                    price_full_power=x[1]
                )

                modelled_use_ratios.append(use_ratio)

            modelled_use_ratios = np.array(modelled_use_ratios)
            mu_model, sigma_model = np.mean(modelled_use_ratios), np.std(modelled_use_ratios)

            # Extract historical values (mean and standard deviation) - avoid division by 0
            historical_use_ratios = (self._historical_powers[self._availabilities != 0]
                                     / self._availabilities[self._availabilities != 0])

            mu_hist, sigma_hist = np.mean(historical_use_ratios), np.std(historical_use_ratios)

            # Objective function is the MSE between mean and std of powers in the year (modelled / historical)
            mean_error = (mu_model - mu_hist) ** 2
            std_error = (sigma_model - sigma_hist) ** 2

            total_error = np.sqrt(mean_error + std_error)
            return total_error

        # Definition of constraints
        if self.is_load:
            constraints = {'type': "ineq", 'fun': lambda x: x[0] - x[1]}  # max_price-min_price must be positive
        else:
            constraints = {'type': "ineq", 'fun': lambda x: x[1] - x[0]}  # max_price-min_price must be positive

        # Prices initialisation
        if self.is_load:  # consumption mode
            (min_price_full_power, max_price_full_power, min_price_no_power,
             max_price_no_power, step_prices_init) = prices_init
            prices_in_order = lambda x, y: y <= x  # noqa
            label = "c"

        else:  # production mode
            (min_price_no_power, max_price_no_power, min_price_full_power,
             max_price_full_power, step_prices_init) = prices_init
            prices_in_order = lambda x, y: x <= y  # noqa
            label = "p"

        potential_prices_init = []

        # evaluate all valid combinations - defined above in prices_in_order - of (price_no_power, price_full_power)
        # within the defined bounds and step size to find the one that minimizes the error function. This value is
        # used as initial value for the optimisation
        for price_no_power in range(min_price_no_power, max_price_no_power + step_prices_init, step_prices_init):
            for price_full_power in range(min_price_full_power, max_price_full_power + step_prices_init,
                                          step_prices_init):
                if prices_in_order(price_no_power, price_full_power):
                    loss = error_function([price_no_power, price_full_power])
                    potential_prices_init.append((loss, price_no_power, price_full_power))

        prices_init = min(potential_prices_init, key=lambda item: item[0])
        print("\n"
              f"Prices for initialisation {self.name}: "
              f"{label}0={prices_init[1]}, {label}100={prices_init[2]}, loss={prices_init[0]}")

        # Optimisation of the prices - minimization of the error function
        res = minimize(error_function, x0=np.array([prices_init[1], prices_init[2]]), tol=1e-8,
                       options={'disp': True}, constraints=constraints)

        self._price_model = round(float(res.x[0]), 0), round(float(res.x[1]), 0)

    def build_availabilities(self):
        """
            Builds the availability series for the sector based on historical power data.

            - For nuclear, availability is the max of ±2 weeks window.
            - For controllable fossil/storage, it's a fixed power rating.
            - For renewables, it's equal to the historical production at each time.

            :return:
                pd.Series: Availability time series.
        """
        expected_nuclear_sector_name = "nuclear"
        half_window_days = 15
        hours_in_day = 24

        # nuclear availability modelling = max power on the current period (+/- 2 weeks)
        if self.name.lower() == expected_nuclear_sector_name:
            availabilities = []
            timestamps = self._historical_powers.index
            total_len = len(timestamps)
            for i, ts in enumerate(timestamps):
                if i < half_window_days * hours_in_day:
                    # First half-month availability data = max of production during the first month
                    start = ts
                    end = ts + pd.Timedelta(days=2 * half_window_days)
                elif i > total_len - half_window_days * hours_in_day:
                    # Last half-month availability data = max of production during the last month
                    start = ts - pd.Timedelta(days=2 * half_window_days)
                    end = ts
                else:
                    # Nominal period : max on +/- 2 weeks
                    start = ts - pd.Timedelta(days=half_window_days)
                    end = ts + pd.Timedelta(days=half_window_days)

                window = self._historical_powers[start:end]
                availabilities.append(window.max())

            self._availabilities = pd.Series(availabilities, index=timestamps)

        else:
            # fossil & storage : availability is supposed to be the maximum power called during the year
            if self._is_controllable:
                if self.is_load:
                    power_rating = self._historical_powers.min()
                else:
                    power_rating = self._historical_powers.max()

                self._availabilities = pd.Series(data=[abs(power_rating)] * len(self._historical_powers),
                                                 index=self._historical_powers.index)
            else:  # Renewable : produced power is supposed to be equal to the available power at any time
                self._availabilities = self._historical_powers

    @property
    def price_model(self):
        """Returns the estimated price model as a tuple (price_no_power, price_full_power)."""
        return self._price_model

    def plot_result(self, zone_name: str, historical_prices: pd.Series, path: Path):
        """
            Plots the historical use ratios vs. price and the resulting piecewise linear model.

            :param zone_name: Name of the zone for plot labeling.
            :param historical_prices: Historical price data.
            :param path: Path where the figure will be saved as a PNG.
        """

        if self._price_model != (None, None):
            fig = plt.figure()
            x_min: float = -50.
            x_max: float = 200.

            prices = historical_prices
            use_ratios = (self._historical_powers[self._availabilities != 0]
                          / self._availabilities[self._availabilities != 0])

            # Get mean of duplicate time steps (clocks change)
            prices = prices.groupby(prices.index).mean()
            use_ratios = use_ratios.groupby(use_ratios.index).mean()

            aligned = pd.concat([prices.rename("price"), use_ratios.rename("use_ratio")], axis=1).dropna()
            plt.scatter(aligned["price"], aligned["use_ratio"], s=7)

            if self.is_load:
                model_y = [-1, -1, 0, 0]
                price_min = self._price_model[1]  # consumption_price_full_power
                price_max = self._price_model[0]  # consumption_price_no_power
                title = f"{zone_name} - {self.name} - Consumption"

            else:
                model_y = [0, 0, 1, 1]
                price_min = self._price_model[0]  # production_price_no_power
                price_max = self._price_model[1]  # production_price_full_power
                title = f"{zone_name} - {self.name} - Production"

            model_x = [min(x_min, price_min), price_min, price_max, max(x_max, price_max)]

            plt.plot(model_x, model_y, c='red')
            plt.xlim(x_min, x_max)
            plt.xlabel("Price (€)")
            plt.ylabel("use ratio")
            fig.suptitle(title, fontsize=10)
            plt.savefig(path)
            plt.close()
