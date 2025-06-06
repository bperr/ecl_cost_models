from pathlib import Path
import pandas as pd
import warnings


class InputReader:
    def __init__(self, work_dir: Path, db_dir: Path):
        self.work_dir = work_dir
        self.db_dir = db_dir

        # Updated in self._read_user_inputs()
        self.zones = dict()
        self.sectors_group = dict()
        self.storages = set()
        self.years = list()

        # Updated in self._read_db_powers() & self._read_db_prices()
        self.historical_powers: dict[str, pd.DataFrame] = dict()
        self.historical_prices = pd.DataFrame()

    def read_user_inputs(self):
        """
        Read user inputs of group years, countries and sectors. (2017-2019) means 'from 2017 to 2019'.

        self.years: List of years group whose prices hypothesis must be read. A year group is start year and end year.
        self.zones: Dictionary listing zone to whose prices hypothesis must be read.
        self.sectors_group: Dictionary listing production mode whose prices hypothesis must be read.
        self.storages: List of production mode that are actually storages.

        Example of stored data dictionary:
         - self.years =  [(2015, 2016, p0 min, p0 max, p100 min, p100 max, step grid crossing)]
         - self.zones =  {"IBR": ["ES", "PT"], "FRA": ["FR"]}
         - self.sectors_group = {"Fossil": ["fossil_gas", "fossil_hard_coal"], "Storage": ["hydro_pumped_storage"]}
         - self.storages=  {Storage}

        """

        file_path = self.work_dir / "User_inputs.xlsx"

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

            # --- Extract years ---
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
            self.years = list(zip(df_years['Year min'], df_years['Year max'], df_years['Min initial price'],
                                  df_years['Max initial price'], df_years['Min initial price'],
                                  df_years['Max initial price'], df_years['step grid crossing']))

            # --- Extract country groups ---
            df_zones = xls.parse('Zones', dtype=str)
            check_columns(df_zones, {'Zone', 'Node'}, 'Zones')
            zones = df_zones.groupby('Zone')['Node'].apply(list).to_dict()

            # --- Extract sector groups ---
            df_sectors = xls.parse('Sectors', dtype=str)
            check_columns(df_sectors, {'Main sector', 'Detailed sector'}, 'Sectors')
            sectors_group = df_sectors.groupby('Main sector')['Detailed sector'].apply(list).to_dict()

            # --- Extract storage-related production modes ---
            df_clustering = xls.parse('Clustering', dtype={'Is storage': float})
            check_columns(df_clustering, {'Main sector', 'Is storage'}, 'Clustering')
            storages_group = df_clustering[df_clustering['Is storage'] == 1.0]['Main sector'].dropna().unique().tolist()

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

            self.zones = zones
            self.sectors_group = sectors_group
            self.storages = storages_group

        except Exception as e:
            raise ValueError(f"Error while reading the Excel file: {e}")

        return self.years, list(self.zones.keys()), list(self.sectors_group.keys()), self.storages

    def read_db_powers(self):
        """
        Reads the production DataBase and creates a dictionary {zone: DataFrame}
        DataFrame with Time index and sectors groups as columns
        """
        power_path = self.db_dir / "Production par pays et par filière 2015-2019"

        for (year_min, year_max, *_) in self.years:  # For each year group

            if year_max < year_min:
                raise ValueError("End year cannot be before start year")

            file_name_template = "Prod_{}_2015_2019.xlsx"  # Country code will be inserted instead of brackets
            country_power_dfs = {}  # {country: pd.DataFrame}

            # List containing all the countries
            all_countries = {country for countries in self.zones.values() for country in countries}

            for country in all_countries:
                file_name = file_name_template.format(country)  # Replace {} by the country code
                sheet_name = file_name[:-5]  # filename without .xlsx

                df = pd.read_excel(power_path / f"{file_name}", sheet_name=sheet_name, header=0)
                df = df[(df["Début de l'heure"].dt.year >= year_min) & (
                        df["Début de l'heure"].dt.year <= year_max)]  # Filter only the years wanted

                df.set_index(df.columns[0],
                             inplace=True)  # First column (time) as index and Column name is also kept as index name

                country_power_dfs[country] = df

            # Group by zone
            for zone, countries in self.zones.items():
                # List of DataFrames per country
                zone_dfs = [country_power_dfs[country] for country in countries if country in country_power_dfs]
                if not zone_dfs:
                    continue

                # Sum of instantaneous powers (each hour) of all the zone's countries
                zone_sector_power_df = pd.concat(zone_dfs).groupby(level=0).sum()

                # Group by sector_group
                zone_grouped_power_df = pd.DataFrame(index=zone_sector_power_df.index)

                for group_name, sectors in self.sectors_group.items():
                    sector_in_group = [sector_name for sector_name in sectors if
                                       sector_name in zone_sector_power_df.columns]
                    if not sector_in_group:
                        continue
                    zone_grouped_power_df[group_name] = zone_sector_power_df[sector_in_group].sum(axis=1)

                # Update of the main dictionary
                self.historical_powers[zone] = zone_grouped_power_df

        return self.historical_powers

    def read_db_prices(self):
        """
        Reads the price DataBase and creates a DataFrame with Time index and zones as columns
        """
        price_path = self.db_dir / "Prix spot par an et par zone 2015-2019"
        all_dfs = [] # List of Dataframes (one per year) to concatenate

        for (year_min, year_max, *_) in self.years:  # For each year group

            if year_max < year_min:
                raise ValueError("End year cannot be before start year")

            file_name_template = "SPOT_{}.xlsx"  # Year will be inserted instead of brackets

            for year in range(year_min, year_max + 1):
                file_name = file_name_template.format(year)
                sheet_name = file_name[:-5]  # filename without .xlsx

                # index_col = 0 to set column time as index
                df = pd.read_excel(price_path / file_name, sheet_name=sheet_name, header=0, index_col=0)
                df_cleaned = df.apply(pd.to_numeric, errors='coerce')  # convert unconvertible strings into NaN

                zone_df = pd.DataFrame(index=df_cleaned.index)

                for zone, countries in self.zones.items():
                    # Keep only columns of countries belonging to the current zone
                    zone_columns = [col for col in df_cleaned.columns if
                                    any(col.startswith(country) for country in countries)]
                    if not zone_columns:
                        continue  # skip if no column is matching

                    # Mean of all countries data in the current zone
                    zone_df[zone] = df_cleaned[zone_columns].mean(axis=1)

                all_dfs.append(zone_df)

        # Update of the main DataFrame
        self.historical_prices = pd.concat(all_dfs).sort_index()

        return self.historical_prices

    def read_price_models(self) -> dict:
        """
        Reconstructs the results dictionary from the Output_prices.xlsx file.
        Returns:
            results (dict): structure [years][zone][main_sector] = [cons_full, cons_none, prod_none, prod_full]
        """
        results = {}
        file_path = self.work_dir / "results" / "Output_prices.xlsx"
        sheet_names = pd.ExcelFile(file_path).sheet_names

        for sheet_name in sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, index_col=0)

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
                        if sector not in self.storages:
                            if any(price is not None for price in [cons_max, cons_min]):
                                raise ValueError(
                                    f"[{year_key}] Le secteur '{sector}' dans la zone '{zone}' "
                                    "n'est pas un stockage et ne doit pas contenir de consommation."
                                )

                        # Check if Prod_min <= Prod_max
                        if prod_min is not None and prod_max is not None:
                            if prod_min > prod_max:
                                raise ValueError(
                                    f"[{year_key}] Erreur logique : Prod_min > Prod_max "
                                    f"pour '{sector}' dans la zone '{zone}' ({prod_min} > {prod_max})"
                                )

                        # Check if Cons_max <= Cons_min
                        if cons_max is not None and cons_min is not None:
                            if cons_max > cons_min:
                                raise ValueError(
                                    f"[{year_key}] Erreur logique : Cons_max > Cons_min pour '{sector}' dans la zone '{zone}' "
                                    f"({cons_max} > {cons_min})"
                                )
        return results
