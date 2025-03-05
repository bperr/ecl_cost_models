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
    
    # Load the Excel file
    xls = pd.ExcelFile(file_path)
    
    # Extract years from the 'Years' sheet
    df_years = xls.parse('Years')
    years = list(zip(df_years['Year min'], df_years['Year max']))

    # Extract country groupings from the 'Zones' sheet
    df_zones = xls.parse('Zones')
    countries_group = df_zones.groupby('Zone name')['Country name'].apply(list).to_dict()

    # Extract sector groupings from the 'Sectors' sheet
    df_sectors = xls.parse('Sectors')
    sectors_group = df_sectors.groupby('Main sector')['Detailed sector'].apply(list).to_dict()

    # Extract storage-related production modes from the 'Clustering' sheet
    df_clustering = xls.parse('Clustering')
    storages = df_clustering[df_clustering['Is storage'] == 1.0]['Main sector'].dropna().unique().tolist()
    
    return(years, countries_group, sectors_group, storages)

# Example usage
if __name__ == "__main__":
    file_path = Path(r"D:\ECL\4a\Option\Projet SuperGrid\Code\Code BDD User\User_inputs.xlsx")
    years, countries_group, sectors_group, storages = read_user_inputs(file_path)