import numpy as np
import pandas as pd
from scipy.optimize import minimize
from matplotlib import pyplot as plt
from pathlib import Path

class Sector:
    def __init__(self, sector_name: str, historical_powers: pd.Series, is_load: bool = False):
        self.name = sector_name
        self.historical_powers = historical_powers

        # consumption_price_full_power,consumption_price_no_power,production_price_no_power,production_price_full_power :
        self._price_model = tuple()
        self.is_controllable = False
        self.is_load = is_load

        self.powers_out = list()
        self.availabilities = pd.Series()

    def _compute_load_factor(self, price: float, price_no_power: float, price_full_power: float):
        """
        Compute the load factor associated to the input price, for the input price model
        :param price: Electricity price (€/MWh)
        :param price_no_power: Price from which production is possible
        :param price_full_power: Price from which full power is possible
        :return: Offered power (between 0 and 1) for the input price
        """
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

    def build_price_model(self, historical_prices: pd.Series, prices_init: tuple):
        # Error function + Optimisation
        # Load factor : self.historical_power / self.availabilities (check si self.availabilities non vide)
        # self._price_model = (Cons_max, Cons_min, Prod_min, Prod_max)


        def error_function(x: np.array):
            """
            Compute error between the modeled and historical load factors distributions,
            using statistical moments (mean and std) of power.

            :param x: [price_no_power, price_full_power]
            :return: error based on difference in moments
            """

            modelled_load_factors = []

            for price in historical_prices:
                load_factor = self._compute_load_factor(
                    price=price,
                    price_no_power=x[0],
                    price_full_power=x[1]
                )

                modelled_load_factors.append(load_factor)

            modelled_load_factors = np.array(modelled_load_factors)
            mu_model, sigma_model = np.mean(modelled_load_factors), np.std(modelled_load_factors)

            # Extract historical values (mean and standard deviation
            historical_load_factors = self.historical_powers / self.availabilities

            mu_hist, sigma_hist = np.mean(historical_load_factors), np.std(historical_load_factors)

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
        step_prices_init = prices_init[-1]
        potential_prices_init = []

        if self.is_load:  # consumption mode
            min_price_full_power, max_price_full_power, min_price_no_power, max_price_no_power, _ = prices_init
            prices_in_order = lambda x, y: y <= x  # noqa
            label = "c"

        else:  # production mode
            min_price_no_power, max_price_no_power, min_price_full_power, max_price_full_power, _ = prices_init
            prices_in_order = lambda x, y: x <= y  # noqa
            label = "p"

        for price_no_power in range(min_price_no_power, max_price_no_power + step_prices_init, step_prices_init):
            for price_full_power in range(min_price_full_power, max_price_full_power + step_prices_init,
                                          step_prices_init):
                if prices_in_order(price_no_power, price_full_power):
                    loss = error_function([price_no_power, price_full_power])
                    potential_prices_init.append((loss, price_no_power, price_full_power))

        prices_init = min(potential_prices_init, key=lambda item: item[0])
        print(
            f"Prices for initialisation: {label}0={prices_init[1]}, {label}100={prices_init[2]}, loss={prices_init[0]}")

        # Optimisation of the prices - minimization of the error function
        res = minimize(error_function, x0=np.array([prices_init[1], prices_init[2]]), tol=1e-8,
                       options={'disp': True}, constraints=constraints)

        self._price_model = round(float(res.x[0]), 0), round(float(res.x[1]), 0)

    def build_availabilities(self, availabilities: pd.Series):
        if availabilities.empty:
            power_rating = self.historical_powers.max()
            self.availabilities = pd.Series(data=[power_rating] * len(self.historical_powers),
                index=self.historical_powers.index)

        else: # nuclear (data available on energygraph)
            self.availabilities = availabilities

    @property
    def price_model(self):
        return self._price_model

    def plot_result(self, zone_name: str, historical_prices: pd.Series, path: Path):
        fig = plt.figure()
        x_min: float = -50
        x_max: float = 200

        prices = historical_prices
        powers = self.historical_powers
        plt.scatter(prices, powers, s=10)

        if self.is_load:
            model_y = [-1, -1, 0, 0]
            price_min = self._price_model[1] # consumption_price_full_power
            price_max = self._price_model[0] # consumption_price_no_power
            title = f"{zone_name} - {self.name} - Consumption"

        else:
            model_y = [0, 0, 1, 1]
            price_min = self._price_model[0] # production_price_no_power
            price_max = self._price_model[1] # production_price_full_power
            title = f"{zone_name} - {self.name} - Production"

        model_x = [min(x_min, price_min), price_min, price_max, max(x_max, price_max)]

        plt.plot(model_x, model_y, c='red')
        plt.xlim(x_min, x_max)
        plt.xlabel("Price (€)")
        plt.ylabel("Load factor")
        fig.suptitle(title, fontsize=10)
        plt.savefig(path)