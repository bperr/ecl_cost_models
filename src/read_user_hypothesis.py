import pandas as pd
from pathlib import Path
from typing import Dict, List

def read_user_hypothesis_data(file_path: Path) -> Dict[str, Dict[str, Dict[str, List[float]]]]:
    """
    Loads the user hypothesis Excel file and generates a dictionary containing 
    the marginal cost data structured as {year}{country}{production_mode: [seuil_price_0, seuil_price_100]}.

    :param file_path: Path to the Excel file containing user hypotheses.
    :return: A dictionary structured as {year: {country: {production_mode: [seuil_price_0, seuil_price_100]}}}.
    
    NOUVELLE VERSION
    """
    # Load the Excel file, reading all sheets (each representing a year)
    xls = pd.ExcelFile(file_path)
    
    # Dictionary to store the data
    hypothesis_data_dict = {}

    for year in xls.sheet_names:  # Each sheet represents a year
        # Read data with the first row as the header
        df = pd.read_excel(xls, sheet_name=year, header=0)  

        # Check if the sheet is empty or incorrectly formatted
        if df.empty or df.shape[1] < 2:
            print(f"Warning: The sheet '{year}' in the user hypothesis file is empty or incorrectly formatted.")
            continue
        
        # Set the first column as index (Production Mode)
        df.set_index(df.columns[0], inplace=True)

        # Convert values to float (if possible)
        df = df.apply(pd.to_numeric, errors='coerce')

        # Dictionary for the current year
        year_data = {}

        # Process each country column
        for country in df.columns:
            country_data = {}

            # Iterate over production modes (step of 2 to group _0 and _100)
            mode_names = list(df.index)
            for i in range(0, len(mode_names), 2):
                mode_base = mode_names[i].rsplit("_", 1)[0]  # Remove _0 or _100
                
                # Check if both _0 and _100 exist
                if i + 1 < len(mode_names) and mode_names[i + 1] == mode_base + "_100":
                    price_0 = df.loc[mode_names[i], country]
                    price_100 = df.loc[mode_names[i + 1], country]
                    country_data[mode_base] = [price_0, price_100]
                else:
                    print(f"Warning: Missing pair for {mode_names[i]} in {year}, {country}")

            year_data[country] = country_data

        hypothesis_data_dict[year] = year_data

    return hypothesis_data_dict

# Example usage
if __name__ == "__main__":
    file_path = Path(r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD User\Hypothesis User.xlsx")
    user_hypotheses = read_user_hypothesis_data(file_path)

    # Example of data access
    year = "2017"
    country = "FR"
    production_mode = "fossil_gas"

    try:
        value = user_hypotheses[year][country][production_mode]
        print(f"Prices in {year} for {production_mode} in {country}: Seuil_0 = {value[0]} €, Seuil_100 = {value[1]} €")
    except KeyError:
        print("Data not found, please check your inputs.")
