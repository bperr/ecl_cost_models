import numpy as np
from pandas import Timestamp
from pathlib import Path
from scipy.optimize import minimize

from src.load_database import load_database_prod_user, load_database_price_user


class Controller:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.work_dir = work_dir
        self.db_dir = db_dir

        # Updated in self._read_user_inputs()
        self.zones = dict()
        self.sectors = dict()
        self.storages = set()
        self.years = list()
        self.initial_prices = dict()

        # Updated in self._read_database()
        self.historical_powers = dict()
        self.historical_prices = dict()

        # Read inputs
        self._read_user_inputs()
        self._read_database()

    def _read_user_inputs(self):
        """
        read user inputs: zones, sectors, years, initial prices
        :return:
        """
        user_inputs = read_user_inputs(self.work_dir)
        self.zones = user_inputs["zones"]
        self.sectors = user_inputs["sectors"]
        self.storages = user_inputs["storages"]
        self.years = user_inputs["years"]
        self.initial_prices = user_inputs["initial prices"]

    def _read_database(self):
        """
        Read the database for the used years
        """
        year_min = min([years[0] for years in self.years])
        year_max = max([years[1] for years in self.years])
        countries = list(set([country for country_list in self.zones.values() for country in country_list]))
        power_path = self.db_dir / "Production par pays et par filière 2015-2019"
        self.historical_powers = load_database_prod_user(folder_path=power_path, country_list=countries,
                                                         start_year=year_min, end_year=year_max)
        # TODO option 1: use self.years in inputs of load_database_prod_user instead of (start_year, year_max)
        # TODO option 2: use a for loop here and have 1 tab per year in the power database
        price_path = self.db_dir / "Prix spot par an et par zone 2015-2019"
        self.historical_prices = load_database_price_user(folder_path=price_path, country_list=countries,
                                                          start_year=year_min, end_year=year_max)

    @staticmethod
    def _compute_power_factor(price: float, price_no_power: float, price_full_power: float, consumption_mode: bool):
        """
        Compute the power factor associated to the input price, for the input price model
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
        :return: {Time step: {"price": price, "power factor": power factor, "power": power}
        """
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
                                power_series[time_step] += sector_data[time_step]
                    else:
                        print(f"Warning: {sector} not in {country} data")
                else:
                    print(f"Warning: {country} not in historical power data")

        series = dict()
        if consumption_mode:
            power_rating = min(0, min(power_series.values()))  # consumption rating <= 0
        else:
            power_rating = max(0, max(power_series.values()))  # production rating >= 0
        for time_step in power_series.keys():
            prices = list()
            for country in countries:
                assert country in self.historical_prices.keys()
                if time_step in self.historical_prices[country]:
                    prices.append(self.historical_prices[country][time_step])
            if len(prices) == 0:
                print(f"Warning: price for {time_step} is not provided.")
            power = power_series[time_step]
            if power * power_rating >= 0:
                series[time_step] = {"price": sum(prices)/len(prices),
                                     "power factor": power/power_rating,
                                     "power": power}
        return series

    def _optimize_error(self, initial_prices: list, series: dict[Timestamp, dict[str, float]], consumption_mode: bool) \
            -> tuple:
        """
        Optimise the price model for a producer or a consumer.
        :param initial_prices: Initialization of the price model (price_no_power, price_full_power)
        :param series: Database extraction: {Time step: {"price": price, "power factor": power factor, "power": power}}
        :param consumption_mode: If True a consumption model is optimised. Else a production model is optimised.
        :return: (price_no_power, price_full_power)
        """
        initial_prices = np.array(initial_prices)

        def error_function(x: np.array):
            """
            Compute an error associated to a price model
            :param x: (price_no_power, price_full_power)
            :return: Mean absolute difference between modelled and expected power factor
            """
            errors = list()
            for time_step, data in series.items():
                price = data["price"]
                expected_power_factor = data["power factor"]
                power_factor_model = self._compute_power_factor(
                    price=price, price_no_power=x[0], price_full_power=x[1], consumption_mode=consumption_mode)
                errors.append(abs(expected_power_factor - power_factor_model))
            return sum(errors) / len(errors)

        res = minimize(error_function, initial_prices, method='nelder-mead',
                       options={'xatol': 1e-8, 'disp': True})
        return float(res.x[0]), float(res.x[1])

    def _export_results(self, results: dict):
        raise NotImplementedError

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
        for (year_min, year_max) in self.years:
            years_key = f"{year_min}-{year_max}"
            results[years_key] = dict()
            for (zone, countries) in self.zones.items():
                results[years_key][zone] = dict()
                for (main_sector, detailed_sectors) in self.sectors.items():
                    is_storage = main_sector in self.storages

                    consumption_price_full_power = None
                    consumption_price_no_power = None
                    if is_storage:
                        zone_consumption_series = self._get_series(
                            years=[y for y in range(year_min, year_max + 1)],
                            countries=countries,
                            detailed_sectors=detailed_sectors,
                            consumption_mode=True)
                        assert len(zone_consumption_series) > 0
                        initial_price_full_power, initial_price_no_power = self.initial_prices[zone][main_sector][0:2]
                        initial_prices = [initial_price_no_power, initial_price_full_power]
                        optimized_prices = self._optimize_error(series=zone_consumption_series,
                                                                initial_prices=initial_prices, consumption_mode=True)
                        consumption_price_no_power, consumption_price_full_power = optimized_prices

                    zone_production_series = self._get_series(
                        years=[y for y in range(year_min, year_max + 1)],
                        countries=countries,
                        detailed_sectors=detailed_sectors,
                        consumption_mode=False)
                    assert len(zone_production_series) > 0
                    initial_price_no_power, initial_price_full_power = self.initial_prices[zone][main_sector][2:4]
                    initial_prices = [initial_price_no_power, initial_price_full_power]
                    optimized_prices = self._optimize_error(series=zone_production_series,
                                                            initial_prices=initial_prices, consumption_mode=False)
                    production_price_no_power, production_price_full_power = optimized_prices
                    # Expected:
                    # consumption_price_full_power <= consumption_price_no_power
                    # <= production_price_no_power <= production_price_full_power
                    if is_storage:  # consumption prices are not None
                        assert isinstance(consumption_price_full_power, float | int)
                        assert isinstance(consumption_price_no_power, float | int)
                        if consumption_price_no_power > production_price_no_power:
                            print(f"Warning: {year_min} to {year_max} | {zone} | {main_sector}: "
                                  f"consumption_price_no_power = {consumption_price_no_power} "
                                  f"> {production_price_no_power} = production_price_no_power")
                            consumption_price_no_power = production_price_no_power \
                                = (consumption_price_no_power + production_price_no_power) / 2
                        if consumption_price_full_power > consumption_price_no_power:
                            consumption_price_full_power = consumption_price_no_power
                            print(f"Warning: {year_min} to {year_max} | {zone} | {main_sector}: "
                                  f"consumption_price_full_power = {consumption_price_full_power} "
                                  f"> {consumption_price_no_power} = consumption_price_no_power")

                    assert isinstance(production_price_no_power, float | int)
                    assert isinstance(production_price_full_power, float | int)
                    if production_price_no_power > production_price_full_power:
                        production_price_full_power = production_price_no_power
                        print(f"Warning: {year_min} to {year_max} | {zone} | {main_sector}: "
                              f"production_price_no_power = {production_price_no_power} "
                              f"> {production_price_full_power} = production_price_full_power")
                    results[years_key][zone][main_sector] = [consumption_price_full_power,
                                                             consumption_price_no_power,
                                                             production_price_no_power,
                                                             production_price_full_power]
        if export_to_excel:
            self._export_results(results=results)
        return results


def read_user_inputs(work_dir: Path):  # FIXME not implemented
    """
    Read user inputs to group years, countries and sectors. (2017-2019) means 'from 2017 to 2019'.

    Example of returned dictionary:
    {"zones": {"IBR": ["ES", "PT"], "FRA": ["FR"]},
     "sectors": {"Fossil": ["fossil_gas", "fossil_hard_coal"], "Storage": ["hydro_pumped_storage"]},
     "storages": {Storage},
     "years": [(2015, 2016), (2017, 2019)],
     "initial prices": {"IBR": {"Fossil": [None, None, 40, 60], "Storage": [10, 20, 30, 40]},
                        "FRA": {"Fossil": [None, None, 40, 60], "Storage": [10, 20, 30, 40]}}}

    :param work_dir: Working directory including user inputs file(s)
    :return: Dictionary with zones, sectors, storages, and years
    """

    raise NotImplementedError
