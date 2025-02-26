from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.read_interco_power import read_interconnection_power_data


@pytest.fixture(scope='function')
def setup():
    # -- Create mocks -- #
    fake_excel_file = MagicMock()
    sheets = ["2015", "2016", "2017", "2018", "2019"]
    fake_excel_file.sheet_names = sheets
    excel_file_mock = patch('pandas.ExcelFile', return_value=fake_excel_file).start()

    fake_excel_df = pd.DataFrame(
        columns=["Time", "France --> Germany", "France --> Switzerland", "Germany --> France",
                 "Switzerland --> France"],
        data=[
            [pd.Timestamp("2015-01-01 00:00:00"), 100, 50, 0, 0],
            [pd.Timestamp("2015-01-01 01:00:00"), 80, 0, 0, 20],
            [pd.Timestamp("2015-01-01 02:00:00"), 50, 15, 10, 0],
        ])
    # This line tells python so emulate 'read_excel' function and to return instead fake_excel_df
    read_excel_mock = patch("pandas.read_excel", return_value=fake_excel_df).start()

    fake_name_code_mapping_dict = {'France': 'FR', 'Germany': 'DE', 'Switzerland': 'CH'}
    # Similarly, this lines tells python to emulate 'map_full_name_to_alpha2_code'. Indeed, we are testing
    # 'read_interconnection_capacities_data' only, not 'map_full_name_to_alpha2_code'. Therefore, whether this function
    # is correctly implemented is not the purpose of this specific test. However, we must test if the function is
    # correctly called.
    map_full_name_mock = patch("src.read_interco_power.map_full_name_to_alpha2_code",
                               return_value=fake_name_code_mapping_dict).start()

    yield {
        'data': {
            'sheets': sheets,
        },
        'mocks': {
            'pandas.ExcelFile': excel_file_mock,
            'pandas.read_excel': read_excel_mock,
            'map_full_name_to_alpha2_code': map_full_name_mock
        }
    }

    patch.stopall()  # Cancel the patch command on 'read excel' and 'map_full_name_to_alpha2_code'


def test_read_interconnection_power_data_creates_expected_structure(setup):
    mocks = setup["mocks"]

    # -- Set inputs -- #
    fake_data_file_path = Path("fake/path/to/data/file")
    fake_mapping_file_path = Path("fake/path/to/mapping/file")
    year = 2015

    # -- Run function -- #
    interconnection_power_df = read_interconnection_power_data(fake_data_file_path, fake_mapping_file_path, year=year)

    # -- Check if mocks have been correctly called -- #
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_data_file_path)
    mocks["pandas.read_excel"].assert_called_once_with(fake_data_file_path, sheet_name=str(year))
    mocks["map_full_name_to_alpha2_code"].assert_called_once_with(fake_mapping_file_path)

    # -- Check if the function output is the expected one -- #
    expected_result = pd.DataFrame(columns=["Time", "Power (MW)", "country_from", "country_to"],
                                   data=[
                                       [pd.Timestamp("2015-01-01 00:00:00"), 100, "FR", "DE"],
                                       [pd.Timestamp("2015-01-01 00:00:00"), 50, "FR", "CH"],
                                       [pd.Timestamp("2015-01-01 01:00:00"), 80, "FR", "DE"],
                                       [pd.Timestamp("2015-01-01 01:00:00"), 20, "CH", "FR"],
                                       [pd.Timestamp("2015-01-01 02:00:00"), 50, "FR", "DE"],
                                       [pd.Timestamp("2015-01-01 02:00:00"), 15, "FR", "CH"],
                                       [pd.Timestamp("2015-01-01 02:00:00"), 10, "DE", "FR"],
                                   ])
    pd.testing.assert_frame_equal(interconnection_power_df.reset_index(drop=True), expected_result)


def test_read_interconnection_power_data_raise_error_if_requested_years_is_not_available(setup):
    mocks = setup["mocks"]
    available_sheets = setup["data"]["sheets"]

    # -- Set inputs -- #
    fake_data_file_path = Path("fake/path/to/data/file")
    fake_mapping_file_path = Path("fake/path/to/mapping/file")
    year = 2023

    # -- Run function -- #
    with pytest.raises(ValueError) as error:
        read_interconnection_power_data(fake_data_file_path, fake_mapping_file_path, year=year)

    # -- Check if mocks have been correctly called -- #
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_data_file_path)
    mocks["pandas.read_excel"].assert_not_called()
    mocks["map_full_name_to_alpha2_code"].assert_not_called()

    # -- Check error message -- #
    assert (error.value.args[0] ==
            f"Sheet '{year}' does not exist in the file '{fake_data_file_path}'. Available sheets: {available_sheets}")
