import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from pandas import Timestamp
from scipy.optimize import minimize

from src.database_corrector import add_missing_dates_price, add_missing_dates_prod
from src.read_database import read_database_price_user, read_database_prod_user
from src.read_user_inputs import read_user_inputs


class Controller:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.work_dir = work_dir
        self.db_dir = db_dir

        # Updated in self._read_user_inputs()
        self.zones = dict()
        self.sectors = dict()
        self.storages = set()
        self.years = list()

        # Updated in self._read_database()
        self.historical_powers = dict()
        self.historical_prices = dict()

        # Read inputs
        self._read_user_inputs()
        self._read_database()

    def _read_user_inputs(self):
        """
        Read user inputs of group years, countries and sectors. (2017-2019) means 'from 2017 to 2019'.

        Example of stored data dictionary:
         - self.zones =  {"IBR": ["ES", "PT"], "FRA": ["FR"]}
         - self.sectors = {"Fossil": ["fossil_gas", "fossil_hard_coal"], "Storage": ["hydro_pumped_storage"]}
         - self.storages=  {Storage}
         - self.years =  [(2015, 2016, p0 min, p0 max, p100 min, p100 max, step grid crossing)]

        """

        hyp_user_path = self.work_dir / "User_inputs.xlsx"

        user_inputs = read_user_inputs(file_path=hyp_user_path)
        self.years = user_inputs[0]
        self.zones = user_inputs[1]
        self.sectors = user_inputs[2]
        self.storages = user_inputs[3]

    def _read_database(self):
        """
        Read the database for the used years
        """
        countries = list(set([country for country_list in self.zones.values() for country in country_list]))
        power_path = self.db_dir / "Production par pays et par filière 2015-2019"
        price_path = self.db_dir / "Prix spot par an et par zone 2015-2019"

        self.historical_powers = {}
        self.historical_prices = {}

        for (year_min, year_max, *_) in self.years:  # For each year group
            powers_users = read_database_prod_user(folder_path=power_path, country_list=countries,
                                                   start_year=year_min, end_year=year_max)
            prices_users = read_database_price_user(folder_path=price_path, country_list=countries,
                                                    start_year=year_min, end_year=year_max)

            add_missing_dates_prod(powers_users, countries, year_min, year_max)
            add_missing_dates_price(prices_users, countries, year_min, year_max)

            for country, prod_mode_dict in powers_users.items():
                if country not in self.historical_powers.keys():
                    self.historical_powers[country] = {}
                for prod_mode, power_dict in prod_mode_dict.items():
                    if prod_mode not in self.historical_powers[country].keys():
                        self.historical_powers[country][prod_mode] = {}
                    self.historical_powers[country][prod_mode].update(power_dict)

            for country, price_dict in prices_users.items():
                if country not in self.historical_prices.keys():
                    self.historical_prices[country] = {}
                self.historical_prices[country].update(price_dict)

    @staticmethod
    def _compute_load_factor(price: float, price_no_power: float, price_full_power: float, consumption_mode: bool):
        """
        Compute the load factor associated to the input price, for the input price model
        :param price: Electricity price (€/MWh)
        :param price_no_power: Price from which production is possible
        :param price_full_power: Price from which full power is possible
        :return: Offered power (between 0 and 1) for the input price
        """
        if consumption_mode:
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

    def _get_series(self, years: list[int], countries: list[str], detailed_sectors: list[str],
                    consumption_mode: bool) -> dict[Timestamp, dict[str, float]]:
        """
        Extract (from the database in attribute) the operating points (time step, price, power) associated to the input
        years | countries | detailed_sectors
        :param years: List of years
        :param countries: List of countries
        :param detailed_sectors: List of detailed sectors
        :param consumption_mode: If True only the negative powers are considered. Else only the positive powers are.
        :return: {Time step: {"price": price, "load factor": load_factor, "power": power}
        """
        # {time_step: power} associated to the input group of years, countries and sectors
        power_series = dict()
        for country in countries:
            if country in self.historical_powers.keys():
                country_data = self.historical_powers[country]
                for sector in detailed_sectors:
                    if f"{sector}_MW" in country_data.keys():
                        sector_data = country_data[f"{sector}_MW"]
                        for time_step in sector_data.keys():
                            if time_step.year in years:
                                if time_step not in power_series.keys():
                                    power_series[time_step] = 0
                                if not pd.isna(sector_data[time_step]):
                                    power_series[time_step] += sector_data[time_step]
                    else:
                        warnings.warn(f"{sector} not in {country} data")
            else:
                warnings.warn(f"{country} not in historical power data")

        # {time_step: price, load factor, power} associated to the input group of years, countries and sectors
        series = dict()
        power_rating = max(abs(power) for power in power_series.values())  # power rating must be positive

        if power_rating == 0:  # The power plant does not exist in the country
            return {}

        for time_step in power_series.keys():
            prices = list()
            for country in countries:
                assert country in self.historical_prices.keys()
                if time_step in self.historical_prices[country]:
                    if not pd.isna(self.historical_prices[country][time_step]):
                        prices.append(self.historical_prices[country][time_step])
            if len(prices) == 0:
                warnings.warn(f"price for {time_step} is not provided. Time step is skipped")
                continue
            power = power_series[time_step]
            if (not consumption_mode and power >= 0) or (consumption_mode and power <= 0):
                series[time_step] = {"price": sum(prices) / len(prices),
                                     "load factor": power / power_rating,
                                     "power": power}

        return series

    def _optimize_error(self, series: dict[Timestamp, dict[str, float]], prices_init: tuple, consumption_mode: bool) \
            -> tuple:
        """
        Optimise the price model for a producer or a consumer.
        :param series: Database extraction: {Time step: {"price": price, "load factor": load_factor, "power": power}}
        :param prices_init:
            prices and step for price initialisation (p0 min, p0 max, p100 min, p100 max, step grid crossing)
        :param consumption_mode: If True a consumption model is optimised. Else a production model is optimised.
        :return: (price_no_power, price_full_power)
        """

        # Extract historical values (mean and standard deviation)
        historical_load_factors = np.array([data["load factor"] for data in series.values()])
        mu_hist, sigma_hist = np.mean(historical_load_factors), np.std(historical_load_factors)

        def error_function(x: np.array):
            """
            Compute error between the modeled and historical load factors distributions,
            using statistical moments (mean and std) of power.

            :param x: [price_no_power, price_full_power]
            :return: error based on difference in moments
            """
            modelled_load_factors = []

            for time_step, data in series.items():
                price = data["price"]

                load_factor = self._compute_load_factor(
                    price=price,
                    price_no_power=x[0],
                    price_full_power=x[1],
                    consumption_mode=consumption_mode
                )

                modelled_load_factors.append(load_factor)

            modelled_load_factors = np.array(modelled_load_factors)
            mu_model, sigma_model = np.mean(modelled_load_factors), np.std(modelled_load_factors)

            mean_error = (mu_model - mu_hist) ** 2
            std_error = (sigma_model - sigma_hist) ** 2

            total_error = np.sqrt(mean_error + std_error)
            return total_error

        # Definition of constraints
        if consumption_mode:
            constraints = {'type': "ineq", 'fun': lambda x: x[0] - x[1]}  # max_price-min_price must be positive
        else:
            constraints = {'type': "ineq", 'fun': lambda x: x[1] - x[0]}  # max_price-min_price must be positive

        # Prices initialisation
        step_prices_init = prices_init[-1]
        potential_prices_init = []

        if consumption_mode:  # consumption mode
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

        return round(float(res.x[0]), 0), round(float(res.x[1]), 0)

    def _export_results(self, results: dict):

        """
        Takes the dictionary results and displays its data in a spreadsheet in xlsx format. Each sheet represents a
        range of years entered by the user.

        :param results : dictionary made by run with the computed
        price model for each year range x zone x main sector.
        """

        dfs = {}
        for year, zones_data in results.items():
            year_str = str(year)

            data = []
            all_sectors = set()

            for zone_info in zones_data.values():
                all_sectors.update(zone_info.keys())

            all_sectors = sorted(all_sectors)
            columns = ['Zone', 'Price Type'] + list(all_sectors)
            prices_type = ['Cons_max', 'Cons_min', 'Prod_min', 'Prod_max']

            for zone, sectors_dict in zones_data.items():
                for index, price_type in enumerate(prices_type):
                    row = [zone, price_type] + [sectors_dict.get(sect, [None] * 4)[index] for sect in all_sectors]
                    data.append(row)

            dfs[year_str] = pd.DataFrame(data, columns=columns)

        results_dir = self.work_dir / "results"
        results_dir.mkdir(exist_ok=True)

        with pd.ExcelWriter(self.work_dir / "results" / "Output_prices.xlsx") as writer:
            for year_str, df in dfs.items():
                df.to_excel(writer, sheet_name=year_str, index=False)

    def run(self, export_to_excel: bool) -> dict:
        """
        Compute price model for each year range x zone x main sector.
        A price model is a list of 4 prices: [price(cons=100%), price(cons=0%), price(prod=0%), price(prod=100%)]
        There should be: price(cons=100%) <= price(cons=0%) <= price(prod=0%) <= price(prod=100%)
        The results can be returned or exported in an Excel file
        :param export_to_excel: To export the results in an Excel file
        :return: {'year_min-year_max': {zone: {main_sector: [price_c_100%, price_c_0%, price_p_0%, price_p_100%]}}}
        """
        results = dict()
        for (year_min, year_max, *grid_init) in self.years:
            years_key = f"{year_min}-{year_max}"
            results[years_key] = dict()
            for (zone, countries) in self.zones.items():
                results[years_key][zone] = dict()
                for (main_sector, detailed_sectors) in self.sectors.items():
                    is_storage = main_sector in self.storages

                    consumption_price_full_power = None
                    consumption_price_no_power = None
                    production_price_no_power = None
                    production_price_full_power = None

                    if is_storage:
                        # Optimise consumption prices
                        zone_consumption_series = self._get_series(
                            years=[y for y in range(year_min, year_max + 1)],
                            countries=countries,
                            detailed_sectors=detailed_sectors,
                            consumption_mode=True)

                        if len(zone_consumption_series) > 0:
                            optimized_prices = self._optimize_error(series=zone_consumption_series,
                                                                    prices_init=grid_init,
                                                                    consumption_mode=True)
                            consumption_price_no_power, consumption_price_full_power = optimized_prices
                            title = f"{year_min}-{year_max} - {zone} - {main_sector} - Consumption"
                            self.plot_result(series=zone_consumption_series, price_min=consumption_price_full_power,
                                             price_max=consumption_price_no_power, title=title, consumption_mode=True)

                    # Optimise production prices
                    zone_production_series = self._get_series(
                        years=[y for y in range(year_min, year_max + 1)],
                        countries=countries,
                        detailed_sectors=detailed_sectors,
                        consumption_mode=False)

                    if len(zone_production_series) > 0:
                        optimized_prices = self._optimize_error(series=zone_production_series, prices_init=grid_init,
                                                                consumption_mode=False)
                        production_price_no_power, production_price_full_power = optimized_prices
                        title = f"{year_min}-{year_max} - {zone} - {main_sector} - Production"
                        self.plot_result(series=zone_production_series, price_min=production_price_no_power,
                                         price_max=production_price_full_power, title=title, consumption_mode=False)

                    # Expected:
                    # consumption_price_full_power <= consumption_price_no_power
                    # <= production_price_no_power <= production_price_full_power
                    if is_storage:  # consumption prices are not None unless series was empty
                        if (isinstance(consumption_price_full_power, (float, int)) and
                                isinstance(consumption_price_full_power, (float, int))):
                            if consumption_price_no_power > production_price_no_power:
                                print(f"{year_min} to {year_max} | {zone} | {main_sector}: "
                                      f"consumption_price_no_power = {consumption_price_no_power} "
                                      f"> {production_price_no_power} = production_price_no_power\n"
                                      f"Both are replaced by their average")
                                consumption_price_no_power = production_price_no_power \
                                    = (consumption_price_no_power + production_price_no_power) / 2

                            if consumption_price_full_power > consumption_price_no_power:
                                print(f"{year_min} to {year_max} | {zone} | {main_sector}: "
                                      f"consumption_price_full_power = {consumption_price_full_power} "
                                      f"> {consumption_price_no_power} = consumption_price_no_power\n"
                                      f"consumption_price_full_power is replaced by consumption_price_no_power")
                                consumption_price_full_power = consumption_price_no_power

                    if (isinstance(production_price_no_power, (float, int)) and
                            isinstance(production_price_full_power, (float, int))):
                        if production_price_no_power > production_price_full_power:
                            print(f"Warning: {year_min} to {year_max} | {zone} | {main_sector}: "
                                  f"production_price_no_power = {production_price_no_power} "
                                  f"> {production_price_full_power} = production_price_full_power\n"
                                  f"production_price_full_power is replaced by production_price_no_power")
                            production_price_full_power = production_price_no_power

                    results[years_key][zone][main_sector] = [consumption_price_full_power,
                                                             consumption_price_no_power,
                                                             production_price_no_power,
                                                             production_price_full_power]

        if export_to_excel:
            self._export_results(results=results)
        return results

    @staticmethod
    def plot_result(series: dict, price_min: float, price_max: float, title: str, consumption_mode: bool):
        fig = plt.figure()
        x_min: float = -50
        x_max: float = 200
        prices = np.array([series_data["price"] for series_data in series.values()])
        powers = np.array([series_data["load factor"] for series_data in series.values()])
        plt.scatter(prices, powers, s=10)
        model_x = [min(x_min, price_min), price_min, price_max, max(x_max, price_max)]
        if consumption_mode:
            model_y = [-1, -1, 0, 0]
        else:
            model_y = [0, 0, 1, 1]
        plt.plot(model_x, model_y, c='red')
        plt.xlim(x_min, x_max)
        plt.xlabel("Price (€)")
        plt.ylabel("Load factor")
        fig.suptitle(title, fontsize=10)
        plt.show()
