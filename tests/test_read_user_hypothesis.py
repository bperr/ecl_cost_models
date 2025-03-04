from pathlib import Path
from unittest.mock import call, patch

import numpy as np
import pandas as pd
import pytest

from src.read_user_hypothesis import read_price_hypothesis


@pytest.fixture(scope='function')
def price_setup():
    df_2015_2016 = pd.DataFrame(columns=["Production_mode", "FR", "BRI", "BNX"],
                                data=[
                                    ["Fossil_p0", 10, 15, 10],
                                    ["Fossil_p100", 20, 25, 20],
                                    ["RES_p0", 5, 10, 10],
                                    ["RES_p100", 10, 15, 15],
                                    ["Storage_p0", 12, 12, 12],
                                    ["Storage_p100", 20, 18, 16],
                                    ["Storage_c0", 10, 10, 12],
                                    ["Storage_c100", 5, 6, 7],
                                ])

    df_2017_2019 = pd.DataFrame(columns=["Production_mode", "FR", "BRI", "BNX"],
                                data=[
                                    ["Fossil_p0", 12, 17, 12],
                                    ["Fossil_p100", 22, 27, 22],
                                    ["RES_p0", 7, 12, 12],
                                    ["RES_p100", 12, 17, 17],
                                    ["Storage_p0", 14, 14, 14],
                                    ["Storage_p100", 22, 20, 18],
                                    ["Storage_c0", 12, 12, 14],
                                    ["Storage_c100", 7, 8, 9],
                                ])

    # Function that returns the dataframe from the years inside the sheet name
    def sheet_name_to_df(sheet_name: str) -> pd.DataFrame:
        if sheet_name == "2015-2016":
            return df_2015_2016
        if sheet_name == "2017-2019":
            return df_2017_2019
        raise Exception(f"Unexpected sheet name {sheet_name}")

    # This line tells python so emulate 'read_excel' function and to apply the side_effect instead
    # Therefore, calling 'read_excel' will call sheet_name_to_df and return the expected dataframe
    read_excel_mock = patch("pandas.read_excel",
                            side_effect=lambda _, sheet_name, **kwargs: sheet_name_to_df(sheet_name)).start()

    yield {
        'data': {
            '2015-2016': df_2015_2016,
            '2017-2019': df_2017_2019,
        },
        'mocks': {
            'pandas.read_excel': read_excel_mock
        }
    }

    patch.stopall()  # Cancel the patch command on 'read excel' (or any function)


def test_read_price_hypothesis_returns_expected_value(price_setup):
    mocks = price_setup["mocks"]

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    prices = read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check 'read_excel' calls
    assert mocks["pandas.read_excel"].call_count == 2
    mocks["pandas.read_excel"].assert_has_calls([
        call(fake_file_path, sheet_name="2015-2016"),
        call(fake_file_path, sheet_name="2017-2019")
    ])

    # Check results
    expected_result = {
        (2015, 2016): {
            'FR': {
                'Fossil': [None, None, 10, 20],
                'RES': [None, None, 5, 10],
                'Storage': [5, 10, 12, 20]
            },
            'BRI': {
                'Fossil': [None, None, 15, 25],
                'RES': [None, None, 10, 15],
                'Storage': [6, 10, 12, 18]
            },
            'BNX': {
                'Fossil': [None, None, 10, 20],
                'RES': [None, None, 10, 15],
                'Storage': [7, 12, 12, 16]
            }
        },
        (2017, 2019): {
            'FR': {
                'Fossil': [None, None, 12, 22],
                'RES': [None, None, 7, 12],
                'Storage': [7, 12, 14, 22]
            },
            'BRI': {
                'Fossil': [None, None, 17, 27],
                'RES': [None, None, 12, 17],
                'Storage': [8, 12, 14, 20]
            },
            'BNX': {
                'Fossil': [None, None, 12, 22],
                'RES': [None, None, 12, 17],
                'Storage': [9, 14, 14, 18]
            }
        }
    }
    assert prices == expected_result


def test_read_price_hypothesis_raise_error_if_zone_is_missing(price_setup):
    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    invalid_zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"], 'DE': ["DE"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, invalid_zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Hypothesis for zones {'DE'} are missing in sheet '2015-2016'"


@pytest.mark.parametrize("row_to_remove", ["Storage_p0", "Storage_p100", "Storage_c0", "Storage_c100"])
def test_read_price_hypothesis_raise_error_if_sector_is_missing(price_setup, row_to_remove):
    # Remove row of 2015-2016_df
    df_2015_2016 = price_setup["data"]["2015-2016"]
    index_to_drop = df_2015_2016.index[df_2015_2016["Production_mode"] == row_to_remove].to_list()[0]
    df_2015_2016.drop(index=index_to_drop, inplace=True)

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    expected_error_by_removed_row = {
        'Storage_p0': "Minimum production price hypothesis for Storage is missing in sheet '2015-2016'",
        'Storage_p100': "Maximum production price hypothesis for Storage is missing in sheet '2015-2016'",
        'Storage_c0': "Minimum consumption price hypothesis for Storage is missing in sheet '2015-2016'",
        'Storage_c100': "Maximum consumption price hypothesis for Storage is missing in sheet '2015-2016'",
    }
    assert error.value.args[0] == expected_error_by_removed_row[row_to_remove]


@pytest.mark.parametrize("price_to_change", ["Fossil_p100", "Fossil_p0"])
def test_read_price_hypothesis_raise_error_if_a_production_price_is_nan(price_setup, price_to_change):
    # Change price_to_change to nan
    df_2015_2016 = price_setup["data"]["2015-2016"]
    fossil_p100_index = df_2015_2016.index[df_2015_2016["Production_mode"] == "Fossil_p100"].to_list()[0]
    df_2015_2016.loc[fossil_p100_index, "FR"] = np.nan

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Missing price_p0 or price_p100 in '2015-2016' for FR, Fossil"


@pytest.mark.parametrize("price_to_change", ["Storage_c100", "Storage_c0"])
def test_read_price_hypothesis_raise_error_if_a_consumption_price_is_nan(price_setup,price_to_change):
    # Change price_to_change to nan
    df_2015_2016 = price_setup["data"]["2015-2016"]
    storage_c0_index = df_2015_2016.index[df_2015_2016["Production_mode"] == "Storage_c0"].to_list()[0]
    df_2015_2016.loc[storage_c0_index, "BRI"] = np.nan

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Missing price_c0 or price_c100 in '2015-2016' for BRI, Storage"


def test_read_price_hypothesis_raise_error_if_p0_is_greater_than_p100(price_setup):
    # Change Fossil_p0 to 25
    df_2015_2016 = price_setup["data"]["2015-2016"]
    fossil_p10_index = df_2015_2016.index[df_2015_2016["Production_mode"] == "Fossil_p0"].to_list()[0]
    df_2015_2016.loc[fossil_p10_index, "FR"] = 25

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Invalid data in '2015-2016' for FR, Fossil: price_p0 (25.0) > price_p100 (20.0)"


def test_read_price_hypothesis_raise_error_if_c0_is_lower_than_c100(price_setup):
    # Change Storage_c0 to 2
    df_2015_2016 = price_setup["data"]["2015-2016"]
    storage_c0_index = df_2015_2016.index[df_2015_2016["Production_mode"] == "Storage_c0"].to_list()[0]
    df_2015_2016.loc[storage_c0_index, "FR"] = 2

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Invalid data in '2015-2016' for FR, Storage: price_c0 (2.0) < price_c100 (5.0)"


def test_read_price_hypothesis_raise_error_if_c0_is_greater_than_p0(price_setup):
    # Change Storage_c0 to 15
    df_2015_2016 = price_setup["data"]["2015-2016"]
    storage_c0_index = df_2015_2016.index[df_2015_2016["Production_mode"] == "Storage_c0"].to_list()[0]
    df_2015_2016.loc[storage_c0_index, "FR"] = 15

    # Set inputs
    fake_file_path = Path("fake/path/to/file")
    years = [(2015, 2016), (2017, 2019)]
    zone_to_countries = {'FR': ["FR"], 'BRI': ["GB", "IE"], 'BNX': ["BE", "NL", "LU"]}
    sectors_group = {'Fossil': ["fossil_gas", "fossil_hard_coal"], 'RES': ["solar", "wind_onshore"],
                     'Storage': ["hydro_pump_storage"]}
    storages = ["Storage"]

    # Run function
    with pytest.raises(Exception) as error:
        read_price_hypothesis(fake_file_path, years, zone_to_countries, sectors_group, storages)

    # Check error
    assert error.value.args[0] == "Invalid data in '2015-2016' for FR, Storage: price_c0 (15.0) > price_p0 (12.0)"
