import pandas as pd
from pathlib import Path
from typing import Dict

def read_user_hypothesis_data(file_path:Path) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Loads the user hypothesis Excel file and generates a dictionary containing 
    the marginal cost data structured as {year}{country}{production_mode}.

    :param file_path : Path to the Excel file containing user hypotheses.
    :return dict: A dictionary structured as {year: {country: {production_mode: cost}}}.
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
        
        # Set the first column as index (production mode)
        df.set_index(df.columns[0], inplace=True)
        
        # Convert values to float (if possible)
        df = df.apply(pd.to_numeric, errors='coerce')

        # Restructure the data into the desired format            
        hypothesis_data_dict[year] = df.to_dict()

    return hypothesis_data_dict

# Example usage
if __name__ == "__main__":
    
    file_path = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD User\Hypothesis User.xlsx"
    user_hypotheses = read_user_hypothesis_data(file_path)

    # Example of data access
    year = "2017"
    country = "FR"
    production_mode = "fossil_gas"

    try:
        value = user_hypotheses[year][country][production_mode]
        print(f"Value in {year} for {production_mode} in {country}: {value} €")
    except KeyError:
        print("Data not found, please check your inputs.")
