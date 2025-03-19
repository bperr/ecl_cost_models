import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pandas import Timestamp
from scipy.optimize import minimize

from load_database import load_database_price_user, load_database_prod_user
from database_corrector import add_missing_dates_prod, add_missing_dates_price

from read_user_inputs import read_user_inputs
from read_price_hypothesis import read_price_hypothesis


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

        # user_inputs = read_user_inputs(self.work_dir)
        # self.zones = user_inputs["zones"]
        # self.sectors = user_inputs["sectors"]
        # self.storages = user_inputs["storages"]
        # self.years = user_inputs["years"]
        # self.initial_prices = user_inputs["initial prices"]
        
        hyp_user_path = self.work_dir / "User_inputs-v2.xlsx"
        hyp_prices_path = self.work_dir / "Prices_inputs-v2.xlsx"
        
        user_inputs = read_user_inputs(file_path=hyp_user_path)
        self.years = user_inputs[0] 
        self.zones = user_inputs[1]
        self.sectors = user_inputs[2]
        self.storages = user_inputs[3]
        
        self.initial_prices = read_price_hypothesis(file_path=hyp_prices_path, years=self.years, countries_group=self.zones, sectors_group=self.sectors, storages=self.storages)



    def _read_database(self):
        """
        Read the database for the used years
        """
        # year_min = min([years[0] for years in self.years])
        # year_max = max([years[1] for years in self.years])
        countries = list(set([country for country_list in self.zones.values() for country in country_list]))
        power_path = self.db_dir / "Production par pays et par filière 2015-2019" / "new"
        price_path = self.db_dir / "Prix spot par an et par zone 2015-2019"
        
        # TODO option 1: use self.years in inputs of load_database_prod_user instead of (start_year, year_max)
        # TODO option 2: use a for loop here and have 1 tab per year in the power database
        
        self.historical_powers = {}
        self.historical_prices = {}
       
        for (year_min, year_max) in self.years : # For each year group
            powers_users = load_database_prod_user(folder_path=power_path, country_list=countries,
                                                         start_year=year_min, end_year=year_max)
            prices_users = load_database_price_user(folder_path=price_path, country_list=countries,
                                                              start_year=year_min, end_year=year_max)
        
            # add_missing_dates_prod(powers_users, countries, year_min, year_max)
            # add_missing_dates_price(prices_users, countries, year_min, year_max)

            self.historical_powers.update(powers_users)
            self.historical_prices.update(prices_users)


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
                                power_series[time_step] += sector_data[time_step]
                    else:
                        warnings.warn(f"{sector} not in {country} data")
            else:
                warnings.warn(f"{country} not in historical power data")

        # {time_step: price, power factor, power} associated to the input group of years, countries and sectors
        series = dict()
        power_rating = max(abs(power) for power in power_series.values())  # power rating must be positive
        assert power_rating > 0

        for time_step in power_series.keys():
            prices = list()
            for country in countries:
                assert country in self.historical_prices.keys()
                if time_step in self.historical_prices[country]:
                    prices.append(self.historical_prices[country][time_step])
            if len(prices) == 0:
                warnings.warn(f"price for {time_step} is not provided. Time step is skipped")
                continue
            power = power_series[time_step]
            if (not consumption_mode and power >= 0) or (consumption_mode and power <= 0):
                series[time_step] = {"price": sum(prices) / len(prices),
                                     "power factor": power / power_rating,
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

        res = minimize(error_function, initial_prices, method="nelder-mead",
                       options={'xatol': 1e-8, 'disp': True})

        # FIXME: Scipy minimize can be successful but return incorrect results (res.fun >> tolerance (1e-8))
        #  It seems to happen when min and max initial_prices are close ? (to investigate and to fix)
        return float(res.x[0]), float(res.x[1])

    def _export_results(self, results : dict):

        """
        Takes the dictionary results and displays its data in a spreadsheet in 
        xlsx format. Each sheet represents a range of years entered by the user.
    
        :param results : dictionnary made by run with the computed 
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
                            print(f"{year_min} to {year_max} | {zone} | {main_sector}: "
                                  f"consumption_price_no_power = {consumption_price_no_power} "
                                  f"> {production_price_no_power} = production_price_no_power\n"
                                  f"Both are replaced by their average")
                            consumption_price_no_power = production_price_no_power \
                                = (consumption_price_no_power + production_price_no_power) / 2
                        if consumption_price_full_power > consumption_price_no_power:
                            consumption_price_full_power = consumption_price_no_power
                            print(f"{year_min} to {year_max} | {zone} | {main_sector}: "
                                  f"consumption_price_full_power = {consumption_price_full_power} "
                                  f"> {consumption_price_no_power} = consumption_price_no_power\n"
                                  f"consumption_price_full_power is replaced by consumption_price_no_power")

                    assert isinstance(production_price_no_power, float | int)
                    assert isinstance(production_price_full_power, float | int)
                    if production_price_no_power > production_price_full_power:
                        production_price_full_power = production_price_no_power
                        print(f"Warning: {year_min} to {year_max} | {zone} | {main_sector}: "
                              f"production_price_no_power = {production_price_no_power} "
                              f"> {production_price_full_power} = production_price_full_power\n"
                              f"production_price_full_power is replaced by production_price_no_power")
                    results[years_key][zone][main_sector] = [consumption_price_full_power,
                                                             consumption_price_no_power,
                                                             production_price_no_power,
                                                             production_price_full_power]
        if export_to_excel:
            self._export_results(results=results)
        return results


# def read_user_inputs(work_dir: Path):  # FIXME not implemented
#     """
#     Read user inputs to group years, countries and sectors. (2017-2019) means 'from 2017 to 2019'.

#     Example of returned dictionary:
#     {"zones": {"IBR": ["ES", "PT"], "FRA": ["FR"]},
#      "sectors": {"Fossil": ["fossil_gas", "fossil_hard_coal"], "Storage": ["hydro_pumped_storage"]},
#      "storages": {Storage},
#      "years": [(2015, 2016), (2017, 2019)],
#      "initial prices": {"IBR": {"Fossil": [None, None, 40, 60], "Storage": [10, 20, 30, 40]},
#                         "FRA": {"Fossil": [None, None, 40, 60], "Storage": [10, 20, 30, 40]}}}

#     :param work_dir: Working directory including user inputs file(s)
#     :return: Dictionary with zones, sectors, storages, and years
#     """

#     raise NotImplementedError
