from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.read_interco_capacity import read_interconnection_capacities_data


def test_read_interconnection_capacities_data_creates_expected_structure():
    # -- Create mocks -- #
    fake_excel_df = pd.DataFrame(columns=["Country_1", "Country_2", "Capacity (MW)"],
                                 data=[
                                     ["France", "Germany", 1000],
                                     ["France", "Switzerland", 300]
                                 ])
    # This line tells python so emulate 'read_excel' function and to return instead fake_excel_df
    read_excel_mock = patch("pandas.read_excel", return_value=fake_excel_df).start()

    fake_name_code_mapping_dict = {'France': 'FR', 'Germany': 'DE', 'Switzerland': 'CH'}
    # Similarly, this lines tells python to emulate 'map_full_name_to_alpha2_code'. Indeed, we are testing
    # 'read_interconnection_capacities_data' only, not 'map_full_name_to_alpha2_code'. Therefore, whether this function
    # is correctly implemented is not the purpose of this specific test. However, we must test if the function is
    # correctly called.
    map_full_name_mock = patch("src.read_interco_capacity.map_full_name_to_alpha2_code",
                               return_value=fake_name_code_mapping_dict).start()

    # -- Set inputs -- #
    fake_data_file_path = Path("fake/path/to/data/file")
    fake_mapping_file_path = Path("fake/path/to/mapping/file")

    # -- Run function -- #
    interconnection_capacities_df = read_interconnection_capacities_data(fake_data_file_path, fake_mapping_file_path)

    # -- Check if mocks have been correctly called -- #
    read_excel_mock.assert_called_once_with(fake_data_file_path)
    map_full_name_mock.assert_called_once_with(fake_mapping_file_path)

    # -- Check if the function output is the expected one -- #
    expected_result = pd.DataFrame(columns=["country_from", "country_to", "Capacity (MW)"],
                                   data=[
                                       ["FR", "DE", 1000],
                                       ["FR", "CH", 300],
                                       ["DE", "FR", 1000],
                                       ["CH", "FR", 300],
                                   ])
    pd.testing.assert_frame_equal(interconnection_capacities_df, expected_result)

    patch.stopall()  # Cancel the patch command on 'read excel' and 'map_full_name_to_alpha2_code'
