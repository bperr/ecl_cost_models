from pathlib import Path
import pandas as pd

def read_user_inputs(file_path: Path) -> tuple[
        list[tuple[int, int]], #years
        dict[str, list[str]],  #countries_group
        dict[str, list[str]], #sectors_group
        list[str]]: #storages
    
    """
    Loads the user inputs Excel file and returns the parameters to enter in the read_price_hypothesis function.
    
    :param file_path: Path to the Excel file containing user inputs.
    :return years: List of years group whose prices hypothesis must be read. A year group is start year and end year.
    :return countries_group: Dictionary listing zone to whose prices hypothesis must be read.
    :return sectors_group: Dictionary listing production mode whose prices hypothesis must be read.
    :return storages: List of production mode that are actually storages.
    """
    
    return()

