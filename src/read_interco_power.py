import pandas as pd
from pathlib import Path

def read_interconnection_power_data(file_path, year):
    """
    Loads and transforms interconnection power data from source file, selecting the sheet for the specified year.

    :param file_path: Path to the Excel file containing interconnection power data.
    :param year: Year corresponding to the sheet to be loaded.
    :return: DataFrame with columns "Time", "Power (MW)", "country_from", and "country_to".
    """
    
    # Verify if the sheet exists
    xls = pd.ExcelFile(file_path)  
    sheet_name = str(year)  # Convert year to string to match sheet names
    
    if sheet_name not in xls.sheet_names:
        raise ValueError(f"Sheet '{sheet_name}' does not exist in the file '{file_path}'. Available sheets: {xls.sheet_names}")
    
    # Load data from the specified sheet
    df_interco_raw = pd.read_excel(xls, sheet_name=sheet_name)

    # Reshape data to good format
    reshaped_df = df_interco_raw.set_index("Time").stack().reset_index(name="Power (MW)").rename(columns={'level_1': 'direction'})
    reshaped_df[["country_from", "country_to"]] = reshaped_df["direction"].str.split(" --> ", n=1, expand=True)
    reshaped_df.drop(columns="direction", inplace=True)
    df_interco = reshaped_df[reshaped_df["Power (MW)"] != 0] # Avoid interco with 0 Power exchanged

    # Load country name conversion file
    path_conversion_country_name_code = Path(r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\List of EU countries.xlsx")
    country_code_conversion_df = pd.read_excel(path_conversion_country_name_code)

    # Create a mapping dictionary from country name to Alpha-2 code
    country_to_alpha2 = dict(zip(country_code_conversion_df["Country"], country_code_conversion_df["Alpha-2"]))

    # Replace country names in the dataframe with their Alpha-2 codes
    df_interco_renamed = df_interco.replace({"country_from": country_to_alpha2, "country_to": country_to_alpha2})

    return df_interco_renamed

# Example usage
if __name__ == "__main__":
    file_path = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\Interconnection time series.xlsx"
    year = 2018  # Year to load
    interconnection_power_data = read_interconnection_power_data(file_path, year)