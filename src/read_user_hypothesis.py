import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple

def read_user_hypothesis_data(file_path: Path) -> Tuple[Dict[str, Dict[str, Dict[str, List[float]]]], List[str]]:
    """
    Loads the user hypothesis Excel file and generates a dictionary containing 
    the 0% and 100% threshold prices data structured as {year}{country}{production_mode: [price_0, price_100]}.
    
    The function ensures:
    - price_0 and price_100 exist.
    - price_0 <= price_100.
    Errors are collected and returned but the import continues.

    :param file_path: Path to the Excel file containing user hypotheses.
    :return: A tuple (data_dict, errors_list), where:
             - data_dict is {year: {country: {production_mode: [price_0, price_100]}}}
             - errors_list contains all detected issues.
    """
    
    # Load the Excel file, reading all sheets (each representing a year)
    xls = pd.ExcelFile(file_path)
    
    # Dictionary to store the data
    hypothesis_data_dict = {}
    
    # Store all detected errors
    errors_list = []  

    for year in xls.sheet_names:  # Each sheet represents a year
        # Read data with the first row as the header
        df = pd.read_excel(xls, sheet_name=year, header=0)  

        # Check if the sheet is empty or incorrectly formatted
        if df.empty or df.shape[1] < 2:
            print(f"Warning: The sheet '{year}' in the user hypothesis file is empty or incorrectly formatted.")
            continue
        
        # Set the first column as index (production mode)
        df.set_index(df.columns[0], inplace=True)
        df = df.apply(pd.to_numeric, errors='coerce')  # Convert to float, NaN if conversion fails

        year_data = {}

        for country in df.columns:
            country_data = {}
            mode_names = list(df.index)

            # Iterate through production modes, expecting two consecutive rows (mode_0 and mode_100)
            for i in range(0, len(mode_names), 2):
                mode_base = mode_names[i].rsplit("_", 1)[0]  

                if i + 1 < len(mode_names) and mode_names[i + 1] == mode_base + "_100": # Verify if there is well the same mode with "_0_ and "_100".
                    price_0 = df.loc[mode_names[i], country]
                    price_100 = df.loc[mode_names[i + 1], country]

                    # Check if both price_0 and price_100 exist
                    if pd.isna(price_0) or pd.isna(price_100):
                        errors_list.append(
                            f"ERROR: Missing price_0 or price_100 in {year} for {country}, {mode_base}."
                        )

                    # Check if price_0 <= price_100
                    elif price_0 > price_100:
                        errors_list.append(
                            f"ERROR: Invalid data in {year} for {country}, {mode_base}: "
                            f"price_0 ({price_0}) > price_100 ({price_100})."
                        )

                    # Store the values (even if incorrect, to preserve data structure)
                    country_data[mode_base] = [price_0, price_100]
                else:
                    errors_list.append(f"Warning: Missing pair for {mode_names[i]} in {year}, {country}")

            year_data[country] = country_data

        hypothesis_data_dict[year] = year_data

    return hypothesis_data_dict, errors_list


# Example usage
if __name__ == "__main__":
    file_path = Path(r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD User\Hypothesis User.xlsx")
    
    user_hypotheses, errors = read_user_hypothesis_data(file_path)

    # Display detected errors
    if errors:
        print("\n--- Errors Detected ---")
        for error in errors:
            print(error)

    # Example of accessing data
    year = "2017"
    country = "FR"
    production_mode = "fossil_gas"

    try:
        value = user_hypotheses[year][country][production_mode]
        print(f"\nPrices in {year} for {production_mode} in {country}: price_0 = {value[0]} €, price_100 = {value[1]} €")
    except KeyError:
        print("Data not found, please check your inputs.")
