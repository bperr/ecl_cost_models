from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.input_reader import InputReader
from src.network import Network


class Controller:
    """
        Coordinates the reading of input data, processing of power and price data, construction of network-based price
        models, and export of results

        This class acts as the main interface to build and export energy price models based on historical data for
        different zones, sectors, and years.
    """

    def __init__(self, work_dir: Path, db_dir: Path):
        """
            Initializes the Controller with working and database directories

            Sets up the input reader and loads all required user inputs and database information including prices and
            power data

            :param work_dir: Path to the working directory where outputs will be saved
            :param db_dir: Path to the database directory containing input data files
       """
        self._input_reader = InputReader(work_dir, db_dir)
        self._work_dir = work_dir
        self._network: Network | None = None

        (self._years, self._zones, self._sectors,
         self._storages, self._controllable_sectors, self._prices_init) = self._input_reader.read_user_inputs()
        self._prices = self._input_reader.read_db_prices()
        self._powers = self._input_reader.read_db_powers()

    def build_price_models(self):
        """
            Build price models for each time period defined in self._years

            For each (start_year, end_year) pair, this method:
              - Filters relevant price and power data
              - Initializes a Network instance and adds zones with associated data
              - Builds price models using initial prices
              - Call the method to export the resulting price models to an Excel file and saves associated plots
        """
        create_file = True
        current_date = datetime.now().strftime("%Y%m%d_%Hh%M")

        for start_year, end_year in self._years:
            print("=" * 60)
            print("=" * 30)
            print(f"\n ====== Building price models for year {start_year}-{end_year} ======")
            self._network = Network()
            prices = self._prices[(self._prices.index.year >= start_year) & (self._prices.index.year <= end_year)]
            powers = {
                zone: df[(df.index.year >= start_year) & (df.index.year <= end_year)]
                for zone, df in self._powers.items()
            }

            for zone in self._zones:
                self._network.add_zone(zone_name=zone, sectors_historical_powers=powers[zone],
                                       storages=self._storages, controllable_sectors=self._controllable_sectors,
                                       historical_prices=prices[zone])
            self._network.build_price_models(self._prices_init[f"{start_year}-{end_year}"])
            self.export_price_models(start_year, end_year, create_file, current_date)

            create_file = False

    def export_price_models(self, start_year: int, end_year: int, create_file: bool, current_date: str):
        """
            Export the generated price models for all zones and sectors to an Excel file and save visual plots in the
            working directory in a directory called "results YYYYMMDD_HHhMM"

            Each zone's model prices are structured into rows representing:
              - Maximum and minimum consumption prices (Cons_max, Cons_min)
              - Maximum and minimum production prices (Prod_max, Prod_min)

            :param start_year: Starting year of the modelled period
            :param end_year: Ending year of the modelled period
            :param create_file: Whether to create a new Excel file (True) or append to an existing one
            with a new sheet (False)
            :param current_date: Timestamp string used to name the output folder for results
        """
        data = []

        first_zone_name = self._network.zones[0].name
        sectors = self._powers[first_zone_name].columns
        sector_to_index = {sector_name: idx for idx, sector_name in enumerate(sectors)}

        for zone in self._network.zones:
            # Row initialisation
            row_cons_max = [zone.name, "Cons_max"] + [np.nan] * len(sectors)
            row_cons_min = [zone.name, "Cons_min"] + [np.nan] * len(sectors)
            row_prod_min = [zone.name, "Prod_min"] + [np.nan] * len(sectors)
            row_prod_max = [zone.name, "Prod_max"] + [np.nan] * len(sectors)

            for sector in zone.sectors:
                prices = sector.price_model
                idx = sector_to_index[sector.name]

                if sector.is_load:
                    row_cons_min[idx + 2] = prices[0]
                    row_cons_max[idx + 2] = prices[1]

                else:
                    row_prod_min[idx + 2] = prices[0]
                    row_prod_max[idx + 2] = prices[1]

            data += [row_cons_max, row_cons_min, row_prod_min, row_prod_max]

            plot_folder_path = self._work_dir / f"results {current_date}" / f"Plots for years {start_year}-{end_year}"
            plot_folder_path.mkdir(parents=True, exist_ok=True)
            zone.save_plots(plot_folder_path)

        df = pd.DataFrame(data, columns=["Zone", "Price Type"] + list(sectors))

        with pd.ExcelWriter(self._input_reader.work_dir / f"results {current_date}" / "Output_prices.xlsx",
                            mode='w' if create_file else 'a') as writer:
            df.to_excel(writer, index=False, sheet_name=f"{start_year}-{end_year}")
