from pathlib import Path

import pandas as pd


def read_price_hypothesis(file_path: Path, years: list[tuple[int, int]], countries_group: dict[str, list[str]],
                          sectors_group: dict[str, list[str]], storages: list[str]) \
        -> dict[tuple[int, int], dict[str, dict[str, list[float | None]]]]:
    """
    Loads the user hypothesis Excel file and generates a dictionary containing the 0% and 100% threshold prices data
    structured as {year_group}{zone}{production_mode: [cons_price_100, cons_price_0, prod_price_0, prod_price_100]}.
    
    The function ensures:
     - prod_price_0 and prod_price_100 exist.
     - prod_price_0 <= prod_price_100.
     - cons_price_0 and cons_price_100 exist (for storage only).
     - cons_price_0 >= cons_price_100 (for storage only).
     - cons_price_0 <= prod_price_0 (for storage only)

    :param file_path: Path to the Excel file containing user prices hypotheses.
    :param years: List of years group whose prices hypothesis must be read. A year group is start year and end year.
    :param countries_group: Dictionary listing zone to whose prices hypothesis must be read.
    :param sectors_group: Dictionary listing production mode whose prices hypothesis must be read.
    :param storages: List of production mode that are actually storages.
    :return: A dictionary of initial prices per main sector, zones, and years group.
    """

    # Dictionary to store the data
    hypothesis_data_dict = {}

    for year_group in years:
        start_year, end_year = year_group
        sheet_name = f"{start_year}-{end_year}"
        # Read data
        df = pd.read_excel(file_path, sheet_name=sheet_name)

        # Set the first column as index (production mode)
        df.set_index(df.columns[0], inplace=True)
        df = df.apply(pd.to_numeric, errors='coerce')  # Convert to float, NaN if conversion fails

        zones = set(countries_group.keys())  # List of zones to get prices from
        # Compare with dataframe columns
        if not zones.issubset(df.columns):
            missing_zones = zones - set(df.columns)
            raise Exception(f"Hypothesis for zones {missing_zones} are missing in sheet '{sheet_name}'")

        production_modes = set(sectors_group.keys())  # List of production modes to get prices from
        # Compare with dataframe indexes
        for prod_mode in production_modes:
            if f"{prod_mode}_p0" not in df.index:
                raise Exception(
                    f"Minimum production price hypothesis for {prod_mode} is missing in sheet '{sheet_name}'")
            if f"{prod_mode}_p100" not in df.index:
                raise Exception(
                    f"Maximum production price hypothesis for {prod_mode} is missing in sheet '{sheet_name}'")
            if prod_mode in storages:  # This is not a production but a storage. It should have consumption prices too
                if f"{prod_mode}_c0" not in df.index:
                    raise Exception(
                        f"Minimum consumption price hypothesis for {prod_mode} is missing in sheet '{sheet_name}'")
                if f"{prod_mode}_c100" not in df.index:
                    raise Exception(
                        f"Maximum consumption price hypothesis for {prod_mode} is missing in sheet '{sheet_name}'")

        # Store data in the dictionary
        year_data = {}

        for zone in zones:
            zone_data = {}

            # Iterate through production modes
            for prod_mode in production_modes:
                price_p0 = float(df.loc[f"{prod_mode}_p0", zone])
                price_p100 = float(df.loc[f"{prod_mode}_p100", zone])

                # Check if both price_p0 and price_p100 exist
                if pd.isna(price_p0) or pd.isna(price_p100):
                    raise Exception(f"Missing price_p0 or price_p100 in '{sheet_name}' for {zone}, {prod_mode}")
                # Check if price_0 <= price_100
                if price_p0 > price_p100:
                    raise ValueError(f"Invalid data in '{sheet_name}' for {zone}, {prod_mode}: "
                                     f"price_p0 ({price_p0}) > price_p100 ({price_p100})")

                if prod_mode not in storages:
                    # Store the values
                    zone_data[prod_mode] = [None, None, price_p0, price_p100]
                else:
                    price_c0 = float(df.loc[f"{prod_mode}_c0", zone])
                    price_c100 = float(df.loc[f"{prod_mode}_c100", zone])

                    # Check if both price_c0 and price_c100 exist
                    if pd.isna(price_c0) or pd.isna(price_c100):
                        raise Exception(f"Missing price_c0 or price_c100 in '{sheet_name}' for {zone}, {prod_mode}")
                    # Check if price_c0 >= price_c100
                    if price_c0 < price_c100:
                        raise ValueError(f"Invalid data in '{sheet_name}' for {zone}, {prod_mode}: "
                                         f"price_c0 ({price_c0}) < price_c100 ({price_c100})")
                    # Check if price_c0 <= price_p0
                    if price_c0 > price_p0:
                        raise ValueError(f"Invalid data in '{sheet_name}' for {zone}, {prod_mode}: "
                                         f"price_c0 ({price_c0}) > price_p0 ({price_p0})")
                    zone_data[prod_mode] = [price_c100, price_c0, price_p0, price_p100]

            year_data[zone] = zone_data

        hypothesis_data_dict[year_group] = year_data

    return hypothesis_data_dict


# Example usage
if __name__ == "__main__":
    file_path = Path("C:/Users/b.perreyon/Downloads/Hypothesis User v2.xlsx")
    years_list = [(2015, 2015), (2016, 2018)]
    zones_to_countries = {'FR': ["FR"], 'GB': ["GB"]}
    main_sectors_to_detailed_sectors = {'biomass': ['biomass'], 'fossil_gas': ['fossil_gas'],
                                        'hydro_pumped_storage': ["hydro_pumped_storage"]}
    storage_list = ["hydro_pumped_storage"]

    user_hypotheses = read_price_hypothesis(file_path, years_list, zones_to_countries, main_sectors_to_detailed_sectors,
                                            storage_list)

    # Example of accessing data
    year_range = (2015, 2015)
    zone = "FR"
    production_mode = "hydro_pumped_storage"

    try:
        value = user_hypotheses[year_range][zone][production_mode]
        print(
            f"\nPrices in {year_range} for {production_mode} in {zone}: "
            f"price_c100 = {value[0]} €, price_c0 = {value[1]}€, price_p0 = {value[2]} €, price_p100 = {value[3]}€")
    except KeyError:
        print("Data not found, please check your inputs.")
