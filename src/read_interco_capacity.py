import pandas as pd
from pathlib import Path
from function_map_fullnames_to_alpha2codes import map_full_name_to_alpha2_code

def read_interconnection_capacities_data(file_path_data: Path, file_path_map: Path) -> pd.DataFrame:
    """
    Loads and transforms interconnection power capacity data between countries from source file.

    :param file_path_data: Path to the Excel file containing interconnection capacity data.
    :param file_path_map: Path to the Excel file containing the mapping of EU country names and alpha2 codes.
    :return: DataFrame with columns "country_from", "country_to" and "Capacity (MW)".
    """
    
    # Load data
    xls = pd.ExcelFile(file_path_data)  
    df_interco_capacity_raw = pd.read_excel(xls) 
    
    # Call function map_full_name_to_alpha2_code which returns a conversion file
    country_to_alpha2 = map_full_name_to_alpha2_code(file_path_map)
    
    # Replace country names in the dataframe with their Alpha-2 codes
    df_interco_capacity_renamed = df_interco_capacity_raw.replace({"Country_1": country_to_alpha2, "Country_2": country_to_alpha2})

    # Renaming columns
    df_interco_capacity_renamed = df_interco_capacity_renamed.rename(columns={"Country_1": "country_from", "Country_2": "country_to"})

    # Creating the reversed DataFrame and concatenate both original and reversed data : to have for one interconnection, two lines in the dataframe with each country once in country_from and once in country_to.
    df_reversed = df_interco_capacity_renamed.rename(columns={"country_from": "country_to", "country_to": "country_from"})
    df_final = pd.concat([df_interco_capacity_renamed, df_reversed], ignore_index=True)

    return df_final

# Example usage
if __name__ == "__main__":
    file_path_data = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\Connection capacities.xlsx"
    file_path_map = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\List of EU countries.xlsx"
    interconnection_capacities_data = read_interconnection_capacities_data(file_path_data, file_path_map)