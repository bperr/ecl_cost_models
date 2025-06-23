import warnings
from pathlib import Path

import pandas as pd

PROD_FOLDER_NAME = "Production par pays et par filière 2015-2019"
PRICES_FOLDER_NAME = "Prix spot par an et par zone 2015-2019"
OUTPUT_EXCEL_NAME = "Output_prices.xlsx"


class InputReader:
    """
        A utility class to load, validate, and organize input data for energy price modelling

        This class centralizes all logic related to:
        - Reading user-defined configurations (zones, sector groups, storage types, etc.)
        - Loading historical production and price data from a structured database
        - Structuring the data for downstream modeling tasks

        It handles consistency checks, grouping, and formatting of data, providing the
        rest of the application with ready-to-use, clean input structures.
    """

    def __init__(self, work_dir: Path, db_dir: Path):
        """
            Initializes the InputReader instance by setting the working and database directories.


            :param work_dir: Path to the working directory where user-defined Excel file 'User_inputs.xlsx' is stored.
            :param db_dir: Path to the database directory containing historical production and price data organized by
                country and year.

            The constructor does not load any data immediately. Data is loaded and processed
            only when the corresponding methods (`read_user_inputs`, `read_db_powers`, etc.) are called.

            Internal attributes are initialized to store:
            - User-defined configurations (zones, sector groups, storage sectors, etc.)
            - Historical power and price data
        """

        self._work_dir: Path = work_dir
        self._db_dir: Path = db_dir

        # Updated in self._read_user_inputs()
        self._zones: dict[str, list[str]] = dict()
        self._sectors_group: dict[str, set[str]] = dict()
        self._storages: set[str] = set()
        self._controllable_sectors: set[str] = set()
        self._years: list[tuple[int, int]] = list()
        self._prices_init: dict[str, tuple] = dict()

        # Updated in self._read_db_powers() & self._read_db_prices()
        self._historical_powers: dict[str, pd.DataFrame] = dict()
        self._historical_prices = pd.DataFrame()

    @property
    def work_dir(self):
        return self._work_dir

    def read_user_inputs(self):
        """
        Reads user-defined configuration from the Excel file 'User_inputs.xlsx' and updates the attributes of the class

        Parses data related to:
        - Year groups and associated price intervals
        - Geographical zones (mapping countries to zones)
        - Sector groups (mapping detailed sectors to main groups)
        - Storage and controllable classifications from clustering data

        :raise:
            FileNotFoundError: If the input Excel file is missing.
            ValueError: If required columns are missing or contain inconsistent data.

        :return:
            tuple: (
                List of (year_min, year_max),
                List of zone names,
                List of main sector names,
                Set of storage sector names,
                Set of controllable sector names,
                Dictionary of initial prices per year group
            )

        Example :
            - self._years =  [(2015, 2016)]
            - list(self._zones.keys()) =  ["IBR", "FRA"]
            - list(self._sectors_group.keys()) = ["Fossil", "Storage", "Nuclear"]
            - self._storages =  [Storage]
            - self._controllable_sectors = ["Fossil", "Nuclear"]
            - self._prices_init = {"2015-2016" : (0, 100, 0, 100, 10)}
        """

        file_path = self._work_dir / "User_inputs.xlsx"

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Load the Excel file
            xls = pd.ExcelFile(file_path)

            # Column names validation before running #
            def check_columns(df: pd.DataFrame, required_columns: set, sheet_name: str):
                """ Checks if the required columns exist in the given sheet. """
                missing_columns = required_columns - set(df.columns)
                if missing_columns:
                    raise ValueError(f"Missing columns in '{sheet_name}' sheet: {missing_columns}")

            # --- Extract years & prices initialisation ---
            df_years = xls.parse('Years', dtype={'Year min': int, 'Year max': int, 'Min initial price': int,
                                                 'Max initial price': int})
            check_columns(df_years, {'Year min', 'Year max', 'Min initial price', 'Max initial price'}, 'Years')

            # Data validation
            if (df_years['Year min'] > df_years['Year max']).any():
                raise ValueError("Invalid data in 'Years' sheet: 'Year min' must be <= 'Year max' for all rows.")
            if (df_years['Min initial price'] > df_years['Max initial price']).any():
                raise ValueError(
                    "Invalid data in 'Years' sheet: 'Min initial price' must be <= 'Max initial price' for all rows.")

            nb_initial_prices = 10
            df_years['step grid crossing'] = (((df_years['Max initial price'] - df_years['Min initial price'])
                                               / nb_initial_prices).round().astype(int))
            self._years = list(zip(df_years['Year min'], df_years['Year max']))

            self._prices_init = {f"{year_min}-{year_max}": (min_price_1, max_price_1, min_price_2, max_price_2, step)
                                 for (year_min, year_max), min_price_1, max_price_1, min_price_2, max_price_2, step in
                                 zip(
                                     self._years,
                                     df_years['Min initial price'], df_years['Max initial price'],
                                     df_years['Min initial price'], df_years['Max initial price'],
                                     df_years['step grid crossing']
                                 )
                                 }

            # --- Extract country groups ---
            df_zones = xls.parse('Zones', dtype=str)
            check_columns(df_zones, {'Zone', 'Node'}, 'Zones')
            zones = df_zones.groupby('Zone')['Node'].apply(list).to_dict()

            # --- Extract sector groups ---
            df_sectors = xls.parse('Sectors', dtype=str)
            check_columns(df_sectors, {'Main sector', 'Detailed sector'}, 'Sectors')
            sectors_group = df_sectors.groupby('Main sector')['Detailed sector'].apply(list).to_dict()

            # --- Extract storage-related production modes ---
            df_clustering = xls.parse('Clustering', dtype={'Is storage': float, 'Is controllable': float})
            check_columns(df_clustering, {'Main sector', 'Is storage', 'Is controllable'}, 'Clustering')

            storages_group = df_clustering[df_clustering['Is storage'] == 1.0]['Main sector'].dropna().unique().tolist()
            controllable_sectors = df_clustering[df_clustering['Is controllable'] == 1.0][
                'Main sector'].dropna().unique().tolist()

            # --- Validation: Check if all zones & main sectors in Clustering exist in other sheets ---
            unused_main_sectors = set(df_clustering['Main sector'].dropna()) - set(sectors_group.keys())
            unused_zones = set(df_clustering['Zone'].dropna()) - set(zones.keys())
            if len(unused_main_sectors) > 0:
                warnings.warn(
                    "The following 'Main sector' values from 'Clustering' do not appear in sheet 'Sectors': "
                    f"{unused_main_sectors}",
                    stacklevel=2)
            if len(unused_zones) > 0:
                warnings.warn(
                    f"The following 'Zone' values from 'Clustering' do not appear in sheet 'Zones': {unused_zones}",
                    stacklevel=2)

            self._zones = zones
            self._sectors_group = sectors_group
            self._storages = storages_group
            self._controllable_sectors = controllable_sectors

        except Exception as e:
            raise ValueError(f"Error while reading the Excel file: {e}")

        return (self._years, list(self._zones.keys()), list(self._sectors_group.keys()), set(self._storages),
                set(self._controllable_sectors), self._prices_init)

    def read_db_powers(self):
        """
        Reads historical production data from Excel files in the database directory.

        For each country and year defined in `self._years`, extracts hourly production data,
        groups it by zones, and aggregates it by sector groups.

        :raise:
            ValueError: If the year range is inconsistent (e.g., end year < start year).

        :return:
            dict[str, pd.DataFrame]: Dictionary mapping zones names to DataFrames of aggregated
            sector historical power data (per main sector) indexed by time. Columns names are the main sectors names.
        """
        power_path = self._db_dir / PROD_FOLDER_NAME

        # Checks if User Inputs have been read, raises an error if not
        if self._years is None:
            raise Exception("Attribute _years is empty, User inputs have not been read. "
                            "Call 'read_user_inputs()' before accessing this data.")

        # Build all years to read
        all_years = set()
        for year_min, year_max in self._years:
            if year_max < year_min:
                raise ValueError("End year cannot be before start year")
            all_years.update(range(year_min, year_max + 1))

        file_name_template = "Prod_{}_2015_2019.xlsx"  # Country code will be inserted instead of brackets
        country_power_dfs = {}  # {country: pd.DataFrame}

        # List containing all the countries
        all_countries = {country for countries in self._zones.values() for country in countries}

        for country in all_countries:
            file_name = file_name_template.format(country)  # Replace {} by the country code
            sheet_name = file_name[:-5]  # filename without .xlsx

            df = pd.read_excel(power_path / f"{file_name}", sheet_name=sheet_name)
            df = df[df["Début de l'heure"].dt.year.isin(all_years)]  # Filter only the years wanted

            df.set_index(df.columns[0],
                         inplace=True)  # First column (time) as index and Column name is also kept as index name

            country_power_dfs[country] = df

        # Group by zone
        for zone, countries in self._zones.items():
            # List of DataFrames per country
            zone_dfs = [country_power_dfs[country] for country in countries if country in country_power_dfs]
            if len(zone_dfs) == 0:
                continue

            # Sum of instantaneous powers (each hour) of all the zone's countries
            zone_sector_power_df = pd.concat(zone_dfs).groupby(level=0).sum()

            # Group by sector_group
            zone_grouped_power_df = pd.DataFrame(index=zone_sector_power_df.index)

            column_map = {
                col.rsplit("_", 1)[0]: col
                for col in zone_sector_power_df.columns
                if col.endswith("_MW")
            }

            for group_name, sectors in self._sectors_group.items():
                sector_in_group = [column_map[sector_name] for sector_name in sectors if
                                   sector_name in column_map]
                if len(sector_in_group) == 0:
                    continue
                zone_grouped_power_df[group_name] = zone_sector_power_df[sector_in_group].sum(axis=1)

            # Update of the main dictionary
            self._historical_powers[zone] = zone_grouped_power_df

        return self._historical_powers

    def read_db_prices(self):
        """
        Reads historical spot price data from Excel files in the database directory.

        For each year and zone, computes the mean price of all associated countries per hour.

        :raise:
            ValueError: If the year range is inconsistent (e.g., end year < start year).

        :return:
            pd.DataFrame: A DataFrame indexed by time, with one column per zone,
            containing average spot prices.
        """
        price_path = self._db_dir / PRICES_FOLDER_NAME
        all_dfs = []  # List of Dataframes (one per year) to concatenate

        # Checks if User Inputs have been read, raises an error if not
        if self._years is None:
            raise Exception("Attribute _years is empty, User inputs have not been read. "
                            "Call 'read_user_inputs()' before accessing this data.")

        for year_min, year_max in self._years:  # For each year group

            if year_max < year_min:
                raise ValueError("End year cannot be before start year")

            file_name_template = "SPOT_{}.xlsx"  # Year will be inserted instead of brackets

            for year in range(year_min, year_max + 1):
                file_name = file_name_template.format(year)
                sheet_name = file_name[:-5]  # filename without .xlsx

                # index_col = 0 to set column time as index
                df = pd.read_excel(price_path / file_name, sheet_name=sheet_name, index_col=0)
                df_cleaned = df.apply(pd.to_numeric, errors='coerce')  # convert unconvertible strings into NaN

                zone_df = pd.DataFrame(index=df_cleaned.index)

                for zone, countries in self._zones.items():
                    # Dictionary to store the dataframes of all the countries' areas
                    country_averages = {}

                    for country in countries:
                        # Find all the columns beginning by the country code
                        country_columns = [col for col in df_cleaned.columns if col.startswith(country)]
                        if len(country_columns) == 0:
                            continue  # ignore the country if there is no column corresponding

                        # Mean of the country's areas prices
                        country_averages[country] = df_cleaned[country_columns].mean(axis=1)

                    if len(country_averages) == 0:
                        continue  # ignore the whole zone if there is no column corresponding

                    country_avg_df = pd.DataFrame(country_averages)

                    # Average of the countries prices in the zone
                    zone_df[zone] = country_avg_df.mean(axis=1)

                all_dfs.append(zone_df)  # Storing all zones data in the all_dfs dataframe (for one year)

        # Storing all studied years data in the main dataframe
        self._historical_prices = pd.concat(all_dfs).sort_index()

        return self._historical_prices

    def read_price_models(self) -> dict:
        # FIXME : change the whole function to recreate the network class based on the excel
        #  (instead of nested dictionary) - will be done for OPF
        """
        Reads computed price results from 'Output_prices.xlsx' and reconstructs a nested dictionary.

        The results dictionary has the following structure:
        results[year][zone][sector] = [cons_full, cons_none, prod_none, prod_full]

        Verifies logical consistency:
        - Storage-only sectors may have consumption values.
        - prod_min must be ≤ prod_max.
        - cons_max must be ≤ cons_min.

        :raise:
            ValueError: If any data inconsistency or unknown price type is detected.

        :return:
            dict: Nested dictionary containing computed prices per year, zone, and sector.
        """
        results = {}
        # TODO : change the folder name, only results otherwise take the last created one

        folder_path = self._work_dir / "results"
        file_path = folder_path / OUTPUT_EXCEL_NAME
        sheet_names = pd.ExcelFile(file_path).sheet_names

        for sheet_name in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name, index_col=0)

            year_key = sheet_name
            results[year_key] = {}

            for _, row in df.iterrows():
                zone = row["Zone"]
                price_type = row["Price Type"]

                if zone not in results[year_key]:
                    results[year_key][zone] = {}

                for sector in df.columns[2:]:  # Skip 'Zone' and 'Price Type'
                    value = row[sector]
                    if pd.isna(value):
                        continue  # None if corresponding cell is empty

                    if sector not in results[year_key][zone]:
                        results[year_key][zone][sector] = [None] * 4  # [Cons_max, Cons_min, Prod_min, Prod_max]

                    if price_type == "Cons_max":
                        results[year_key][zone][sector][0] = value
                    elif price_type == "Cons_min":
                        results[year_key][zone][sector][1] = value
                    elif price_type == "Prod_min":
                        results[year_key][zone][sector][2] = value
                    elif price_type == "Prod_max":
                        results[year_key][zone][sector][3] = value
                    else:
                        raise ValueError(f"Unknown price type: {price_type}")

                # Data verification
                for zone, sectors in results[year_key].items():
                    for sector, values in sectors.items():
                        cons_max, cons_min, prod_min, prod_max = values

                        # No consumption if non-storage
                        if sector not in self._storages:
                            if any(price is not None for price in [cons_max, cons_min]):
                                raise ValueError(
                                    f"[{year_key}] Sector '{sector}' in zone '{zone}' "
                                    "is not storage and must not contain consumption."
                                )

                        # Check if Prod_min <= Prod_max
                        if prod_min is not None and prod_max is not None:
                            if prod_min > prod_max:
                                raise ValueError(
                                    f"[{year_key}] Logical error: Prod_min > Prod_max "
                                    f"for '{sector}' in zone '{zone}' ({prod_min} > {prod_max})"
                                )

                        # Check if Cons_max <= Cons_min
                        if cons_max is not None and cons_min is not None:
                            if cons_max > cons_min:
                                raise ValueError(
                                    f"[{year_key}] Logical error : Cons_max > Cons_min for "
                                    f"'{sector}' in zone '{zone}' ({cons_max} > {cons_min})"
                                )
        return results
