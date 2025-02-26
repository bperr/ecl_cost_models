from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.map_full_names_to_alpha2codes import map_full_name_to_alpha2_code


def test_map_full_name_to_alpha2_code_returns_expected_value():
    # -- Create mocks -- #
    fake_excel_df = pd.DataFrame(columns=["Country", "Alpha-2", "Alpha-3"],
                                 data=[
                                     ["France", "FR", "FRA"],
                                     ["Germany", "DE", "DEU"],
                                     ["Switzerland", "CH", "CHE"],
                                 ])
    # This line tells python so emulate 'read_excel' function and to return instead fake_excel_df
    read_excel_mock = patch("pandas.read_excel", return_value=fake_excel_df).start()

    # -- Set input and run function -- #
    fake_mapping_file_path = Path("fake/path/to/mapping/file")
    mapping_dict = map_full_name_to_alpha2_code(fake_mapping_file_path)

    # -- Check if mocks have been correctly called -- #
    read_excel_mock.assert_called_once_with(fake_mapping_file_path)

    # -- Check if the function output is the expected one -- #
    expected_dict = {'France': "FR", 'Germany': "DE", 'Switzerland': "CH"}
    assert mapping_dict == expected_dict

    patch.stopall()  # Cancel the patch command on 'read excel'
