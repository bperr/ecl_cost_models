import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.input_reader import InputReader
from src.network import Network

SIMULATED_POWERS_DIRECTORY_ROOT = 'countries_simulated_powers_by_sector'
SIMULATED_POWERS_FILE_ROOT = 'simulated_powers_by_sector'
YEAR_PL_AVAILABLE_DATA = 2018
MAXIMUM_MISSING_STEPS_PER_YEAR = 100


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

        self._interco_power_ratings = self._input_reader.read_interco_power_ratings()
        self._interco_powers = self._input_reader.read_interco_powers()

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

        first_zone_name = next(iter(self._network.zones))
        sectors = self._powers[first_zone_name].columns
        sector_to_index = {sector_name: idx for idx, sector_name in enumerate(sectors)}

        for zone in self._network.zones.values():
            # Row initialisation
            row_cons_max = [zone.name, "Cons_max"] + [np.nan] * len(sectors)
            row_cons_min = [zone.name, "Cons_min"] + [np.nan] * len(sectors)
            row_prod_min = [zone.name, "Prod_min"] + [np.nan] * len(sectors)
            row_prod_max = [zone.name, "Prod_max"] + [np.nan] * len(sectors)

            for sector in zone.sectors:
                prices = sector.price_model
                idx = sector_to_index[sector.name]

                if sector.is_storage_load:
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

    def check_price_models(self, price_models: dict):
        """
        Validates the integrity and logical consistency of the price models for each sector in all zones.

        The price_models dictionary should have the following structure:
        price_models[zone][sector] = [cons_full, cons_none, prod_none, prod_full]

        Validation rules:
        - Sectors that are not storage units must not have consumption prices
            (i.e. cons_full and cons_none must be None)
        - Production prices (prod_none and prod_full) must not be None
        - prod_none must be less than or equal to prod_full
        - For storage sectors only:
            - Consumption prices (cons_full and cons_none) must not be None
            - cons_full must be less than or equal to cons_none
            - cons_none must be less than or equal to prod_none

        :param price_models: Dictionary containing the price models per zone and sector
        :param storages: List of sector names that are storages

        :raises ValueError: If any of the logical consistency checks fail
        """

        for zone, sectors in price_models.items():
            for sector, prices in sectors.items():
                cons_full, cons_none, prod_none, prod_full = prices

                # Check production prices
                if prod_none is None or prod_full is None:
                    raise ValueError(f"Missing production prices for '{sector}' in zone '{zone}'")
                if prod_none > prod_full:
                    raise ValueError(
                        f"Logical error: Prod_none > Prod_full for '{sector}' in zone '{zone}' "
                        f"({prod_none} > {prod_full})"
                    )

                if sector in self._storages:
                    # Check consumption prices
                    if cons_none is None or cons_full is None:
                        raise ValueError(f"Missing consumption prices for storage sector '{sector}' in zone '{zone}'")
                    if cons_full > cons_none:
                        raise ValueError(
                            f"Logical error: Cons_full > Cons_none for '{sector}' in zone '{zone}' "
                            f"({cons_full} > {cons_none})"
                        )
                    if cons_none > prod_none:
                        raise ValueError(
                            f"Logical error: Cons_none > Prod_none for '{sector}' in zone '{zone}' "
                            f"({cons_none} > {prod_none})"
                        )
                else:
                    # If sector is not storage, it should not have consumption prices
                    if cons_full is not None or cons_none is not None:
                        raise ValueError(
                            f"Sector '{sector}' in zone '{zone}' is not storage but has consumption prices."
                        )

    def build_network_model(self, start_year: int, end_year: int):
        """
        Builds the entire energy network model for the specified time period if data is available
        (especially Poland Price data) and returns if the model was built or not.

        This method initializes the network if it has not already been built : it adds the user defined zones, their
        historical prices, storages and sectors with their historical powers to the network.

        It also adds interconnections between zones based on power ratings and historical flow data to the network.
        Finally, it computes the total demand for each zone (main load)

        :param start_year: Starting year of the modelled period
        :param end_year: Ending year of the modelled period

        :return: bool True if the model was built, False otherwise
        """
        # ------- add zones -------
        self._network = Network()
        prices = self._prices[(self._prices.index.year >= start_year) & (self._prices.index.year <= end_year)]
        powers = {
            zone: df[(df.index.year >= start_year) & (df.index.year <= end_year)]
            for zone, df in self._powers.items()
        }

        for zone in self._zones:
            if ('PL' in self._input_reader.get_countries_in_zone(zone)
                    and (start_year < YEAR_PL_AVAILABLE_DATA)):
                warnings.warn(f"Price data for Poland is incomplete before 2018. The simulation for "
                              f"{start_year}-{end_year} cannot be performed, please change the input years")
                return False

            else:
                self._network.add_zone(zone_name=zone, sectors_historical_powers=powers[zone],
                                       storages=self._storages, controllable_sectors=self._controllable_sectors,
                                       historical_prices=prices[zone])

        # We suppose that the production data is complete for all zones (8784 hours/year for leap years, 8760 otherwise)
        missing_steps = len(next(iter(powers.values()))) - len(self._network.datetime_index)

        print(f"Skipped {missing_steps} timesteps for time period '{start_year}-{end_year}' "
              f"because of missing data (prices)")

        missing_steps_limit = MAXIMUM_MISSING_STEPS_PER_YEAR * (end_year - start_year + 1)

        if missing_steps > missing_steps_limit:
            warnings.warn(
                f"More than {missing_steps_limit} timesteps cannot be used due to missing data in SPOT price"
                f"data for this time period. The simulation for {start_year}-{end_year} cannot be performed"
            )
            return False

        else:
            price_models = self._input_reader.read_price_models()[f"{start_year}-{end_year}"]

            # check that data from price_models excel is consistent
            self.check_price_models(price_models)

            # set price models for each sector of each zone
            self._network.set_price_model(price_models)

            # ------- add interconnections -------
            # power_rating excel is used to navigate through the interconnections
            for index, row in self._interco_power_ratings.iterrows():
                zone_from = row['zone_from']
                zone_to = row['zone_to']
                power_rating = row['Capacity (MW)']

            # Check if the interconnection between the two zones already exist to avoid all the calculation if it does
                interco_exists = False

                for interconnection in self._network.interconnections:
                    if ((interconnection.zone_from.name == zone_from and interconnection.zone_to.name == zone_to) or
                            (interconnection.zone_from.name == zone_to and interconnection.zone_to.name == zone_from)):
                        interco_exists = True
                        break

                if interco_exists:
                    continue

                # If new interconnection : creation of the power series for this interconnection
                flow_forward = self._interco_powers[
                    (self._interco_powers['zone_from'] == zone_from) & (self._interco_powers['zone_to'] == zone_to)
                    ].set_index("Time")["Power (MW)"]

                flow_backward = self._interco_powers[
                    (self._interco_powers['zone_from'] == zone_to) & (self._interco_powers['zone_to'] == zone_from)
                    ].set_index("Time")["Power (MW)"]

                # Net power : forward - backward
                interco_powers = flow_forward.sub(flow_backward, fill_value=0).sort_index()

                self._network.add_interconnection(self._network.zones[zone_from], self._network.zones[zone_to],
                                                  power_rating, interco_powers)

            # ------- add loads -------
            # Demand = production + net import
            for zone_name, zone in self._network.zones.items():
                net_import = 0
                for interconnection in zone.interconnections:
                    if interconnection.zone_from.name == zone_name:
                        net_import -= interconnection.historical_powers
                    elif interconnection.zone_to.name == zone_name:
                        net_import += interconnection.historical_powers
                zone.compute_demand(net_import)

            return True

    def run_opfs(self):
        """
        Runs the Optimal Power Flow (OPF) simulations for the configured time periods

        For each defined period, this method builds the corresponding network model and sequentially runs
        the OPF calculation for each timestep within that period. After all OPF simulations are completed
        for a given period, the results are exported.
        """
        for start_year, end_year in self._years:
            model_built = self.build_network_model(start_year, end_year)
            if not model_built:
                continue
            for timestep in self._network.datetime_index:
                self._network.run_opf(timestep)
            self.export_opfs()

    def export_opfs(self):
        """
        Exports the results of the Optimal Power Flow (OPF) simulations for each zone.

        For each zone in the network, this method retrieves the simulated power time series for each sector,
        compiles them into a single DataFrame, and exports the results to an Excel file. Each file is saved
        in a directory named according to the simulation period.

        - The OPF simulation results must be available in the '_simulated_powers' attribute of each sector.
        - The export format includes a timestamp column ('Début de l'heure') and one column per sector
          showing the simulated power in MW.
        - The directory is created under the working directory.
        """
        for zone_name, zone in self._network.zones.items():
            sectors = zone.sectors

            # Get the simulated power series for each sector of the current zone
            sector_data = {}
            for sector in sectors:
                sector_name = sector.name
                simulated_powers = sector.simulated_powers
                sector_data[f'{sector_name}_MW'] = simulated_powers

            # Build the DataFrame with data from all sectors of the current zone
            combined_df = pd.concat(sector_data, axis=1)

            # Create a first column "Start time" with index (timesteps)
            combined_df.insert(0, 'Start time', combined_df.index)

            # sheet name
            start_year = combined_df['Start time'].min().year
            end_year = combined_df['Start time'].max().year
            sheet_name = f'{start_year}-{end_year}'

            # file path
            folder_name = f"{SIMULATED_POWERS_DIRECTORY_ROOT}_{start_year}-{end_year}"
            folder_path = self._work_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)

            file_name = f"{SIMULATED_POWERS_FILE_ROOT}_{zone_name}.xlsx"
            file_path = folder_path / file_name

            # Export Excel
            with pd.ExcelWriter(file_path) as writer:
                combined_df.to_excel(writer, sheet_name=sheet_name, index=False)

            print(f'File successfully exported : {file_path}')
