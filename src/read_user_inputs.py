from pathlib import Path
import pandas as pd
import warnings


def read_user_inputs(file_path: Path) -> tuple[
    list[tuple[int, int]],  # years
    dict[str, list[str]],  # countries_group
    dict[str, list[str]],  # sectors_group
    list[str]]:  # storages
    """
    Loads the user inputs Excel file and returns the parameters to enter in the read_price_hypothesis function.
    
    :param file_path: Path to the Excel file containing user inputs.
    :return years: List of years group whose prices hypothesis must be read. A year group is start year and end year.
    :return countries_group: Dictionary listing zone to whose prices hypothesis must be read.
    :return sectors_group: Dictionary listing production mode whose prices hypothesis must be read.
    :return storages: List of production mode that are actually storages.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Load the Excel file
        xls = pd.ExcelFile(file_path)

        # Column names validation before running #
        def check_columns(df: pd.DataFrame, required_columns: set, sheet_name: str):
            """ Checks if the required columns exist in the given sheet. """
            missing_columns = required_columns - set(df.columns)
            if missing_columns:
                raise ValueError(f"Missing columns in '{sheet_name}' sheet: {missing_columns}")

        # --- Extract years ---
        df_years = xls.parse('Years', dtype={'Year min': int, 'Year max': int})
        check_columns(df_years, {'Year min', 'Year max'}, 'Years')

        ## Data validation ##
        if (df_years['Year min'] > df_years['Year max']).any():
            raise ValueError("Invalid data in 'Years' sheet: 'Year min' must be <= 'Year max' for all rows.")

        years = list(zip(df_years['Year min'], df_years['Year max']))

        # --- Extract grid bounds for price initialisation ---
        df_grid_bounds = xls.parse('Years', dtype={'p0 min': int, 'p0 max': int,
                                                   'p100 min': int, 'p100 max': int, 'step grid crossing': int})
        check_columns(df_years, {'p0 min', 'p0 max', 'p100 min', 'p100 max', 'step grid crossing'}, 'Years')

        ## Data validation ##
        if (df_grid_bounds['p0 min'] > df_grid_bounds['p0 max']).any():
            raise ValueError("Invalid data in 'Years' sheet: 'p0 min' must be <= 'p0 max' for all rows.")
        if (df_grid_bounds['p100 min'] > df_grid_bounds['p100 max']).any():
            raise ValueError("Invalid data in 'Years' sheet: 'p100 min' must be <= 'p100 max' for all rows.")
        if (df_grid_bounds['p0 min'] > df_grid_bounds['p100 min']).any():
            raise ValueError("Invalid data in 'Years' sheet: 'p0 min' must be <= 'p100 min' for all rows.")
        if (df_grid_bounds['p100 max'] > df_grid_bounds['p100 max']).any():
            raise ValueError("Invalid data in 'Years' sheet: 'p0 max' must be <= 'p100 max' for all rows.")

        grid_bounds = list(zip(df_years['p0 min'], df_years['p0 max'],df_years['p100 min'],
                               df_years['p100 max'],df_years['step grid crossing']))

        # --- Extract country groups ---
        df_zones = xls.parse('Zones', dtype=str)
        check_columns(df_zones, {'Zone', 'Node'}, 'Zones')
        countries_group = df_zones.groupby('Zone')['Node'].apply(list).to_dict()

        # --- Extract sector groups ---
        df_sectors = xls.parse('Sectors', dtype=str)
        check_columns(df_sectors, {'Main sector', 'Detailed sector'}, 'Sectors')
        sectors_group = df_sectors.groupby('Main sector')['Detailed sector'].apply(list).to_dict()

        # --- Extract storage-related production modes ---
        df_clustering = xls.parse('Clustering', dtype={'Is storage': float})
        check_columns(df_clustering, {'Main sector', 'Is storage'}, 'Clustering')
        storages = df_clustering[df_clustering['Is storage'] == 1.0]['Main sector'].dropna().unique().tolist()

        # --- Validation: Check if all zones & main sectors in Clustering exist in other sheets ---
        unused_main_sectors = set(df_clustering['Main sector'].dropna()) - set(sectors_group.keys())
        unused_zones = set(df_clustering['Zone'].dropna()) - set(countries_group.keys())
        if len(unused_main_sectors) > 0:
            warnings.warn(
                f"The following 'Main sector' values from 'Clustering' do not appear in sheet 'Sectors': {unused_main_sectors}",
                stacklevel=2)
        if len(unused_zones) > 0:
            warnings.warn(
                f"The following 'Zone' values from 'Clustering' do not appear in sheet 'Zones': {unused_zones}",
                stacklevel=2)

        return years, grid_bounds, countries_group, sectors_group, storages

    except Exception as e:
        raise ValueError(f"Error while reading the Excel file: {e}")


# Example usage
if __name__ == "__main__":
    file_path = Path("C:/Users/b.perreyon/Documents/ECL cost models/ecl_cost_models/Templates/User_inputs_Test.xlsx")
    try:
        years, countries_group, sectors_group, storages = read_user_inputs(file_path)
    except Exception as e:
        print(f"Error: {e}")
