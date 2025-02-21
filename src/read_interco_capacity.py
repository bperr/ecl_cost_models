import pandas as pd
from pathlib import Path

def read_interconnection_capacities_data(file_path):
    """
    Loads and transforms interconnection power capacity data between countries from source file.

    :param file_path: Path to the Excel file containing interconnection capacity data.
    :return: DataFrame with columns "country_from", "country_to" and "Capacity (MW)".
    """
    
    # Load data
    xls = pd.ExcelFile(file_path)  
    df_interco_capacity_raw = pd.read_excel(xls) 

    # Load country name conversion file
    path_conversion_country_name_code = Path(r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\List of EU countries.xlsx")
    country_code_conversion_df = pd.read_excel(path_conversion_country_name_code)

    # Create a mapping dictionary from country name to Alpha-2 code
    country_to_alpha2 = dict(zip(country_code_conversion_df["Country"], country_code_conversion_df["Alpha-2"]))

    # Replace country names in the dataframe with their Alpha-2 codes
    df_interco_capacity_renamed = df_interco_capacity_raw.replace({"Country_1": country_to_alpha2, "Country_2": country_to_alpha2})

    # Renaming columns
    df_interco_capacity_renamed = df_interco_capacity_renamed.rename(columns={"Country_1": "country_from", "Country_2": "country_to"})

    # Creating the reversed DataFrame and oncatenating both original and reversed data : to have for one interconnection, two lines in the dataframe with each country once in country_from and once in country_to.
    df_reversed = df_interco_capacity_renamed.rename(columns={"country_from": "country_to", "country_to": "country_from"})
    df_final = pd.concat([df_interco_capacity_renamed, df_reversed], ignore_index=True)

    return df_final

# Example usage
if __name__ == "__main__":
    file_path = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\Connection capacities.xlsx"
    interconnection_capacities_data = read_interconnection_capacities_data(file_path)