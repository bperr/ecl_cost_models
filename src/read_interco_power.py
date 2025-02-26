from pathlib import Path

import pandas as pd

from src.map_full_names_to_alpha2codes import map_full_name_to_alpha2_code


def read_interconnection_power_data(file_path_data: Path, file_path_map: Path, year: int | str) -> pd.DataFrame:
    """
    Loads and transforms interconnection power data from source file, selecting the sheet for the specified year.

    :param file_path_data: Path to the Excel file containing interconnection power data.
    :param file_path_map: Path to the Excel file containing the mapping of EU country names and alpha2 codes.
    :param year: Year corresponding to the sheet to be loaded.
    :return: DataFrame with columns "Time", "Power (MW)", "country_from", and "country_to".
    """

    # Verify if the sheet exists
    xls = pd.ExcelFile(file_path_data)
    sheet_name = str(year)  # Convert year to string to match sheet names

    if sheet_name not in xls.sheet_names:
        raise ValueError(
            f"Sheet '{sheet_name}' does not exist in the file '{file_path_data}'. Available sheets: {xls.sheet_names}")

    # Load data from the specified sheet
    df_interco_raw = pd.read_excel(file_path_data, sheet_name=sheet_name)

    # Reshape data to good format
    reshaped_df = df_interco_raw.set_index("Time").stack().reset_index(name="Power (MW)").rename(
        columns={'level_1': 'direction'})
    reshaped_df[["country_from", "country_to"]] = reshaped_df["direction"].str.split(" --> ", n=1, expand=True)
    reshaped_df.drop(columns="direction", inplace=True)
    df_interco = reshaped_df[reshaped_df["Power (MW)"] != 0]  # Avoid interco with 0 Power exchanged

    # Call function map_full_name_to_alpha2_code which returns a conversion file
    country_to_alpha2 = map_full_name_to_alpha2_code(file_path_map)

    # Replace country names in the dataframe with their Alpha-2 codes
    df_interco_renamed = df_interco.replace({"country_from": country_to_alpha2, "country_to": country_to_alpha2})

    return df_interco_renamed


# Example usage
if __name__ == "__main__":
    file_path_data = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\Interconnection time series.xlsx"
    file_path_map = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\List of EU countries.xlsx"
    year = 2018  # Year to load
    interconnection_power_data = read_interconnection_power_data(file_path_data, file_path_map, year)
