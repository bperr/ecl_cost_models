from pathlib import Path

import pandas as pd


def map_full_name_to_alpha2_code(file_path: Path) -> dict[str, str]:
    """
    Loads an Excel file containing the list of EU countries names and their Alpha-2 codes,
    then creates a dictionary mapping each country name to its corresponding Alpha-2 code.

    :param file_path: Path to the Excel file containing the country names and their Alpha-2 codes.
    :return dict[str, str]:
        A dictionary where the keys are country names (str) and the values are the corresponding Alpha-2 codes (str).
    """

    # Load country name conversion file
    country_code_conversion_df = pd.read_excel(file_path)

    # Create a mapping dictionary from country name to Alpha-2 code
    country_to_alpha2 = dict(zip(country_code_conversion_df["Country"], country_code_conversion_df["Alpha-2"]))

    return country_to_alpha2


if __name__ == "__main__":
    file_path = r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD Interco\List of EU countries.xlsx"
    country_to_alpha2 = map_full_name_to_alpha2_code(file_path)
