from pathlib import Path
from unittest.mock import ANY, call, patch

import numpy as np
import pandas as pd
import pytest
from pandas import Timestamp

from src.load_database import load_database_price_user, load_database_prod_user


def get_dict_depth(d: dict):
    if isinstance(d, dict):
        return 1 + max(map(get_dict_depth, d.values()), default=0)
    return 0


@pytest.fixture(scope='function')
def prod_setup():
    at_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 300, 1000, 20],
                                  [Timestamp("01/01/2015  13:00:00"), 300, 1000, 30],
                                  [Timestamp("01/01/2015  14:00:00"), 300, 1000, 30],
                                  [Timestamp("01/01/2016  12:00:00"), 300, 1000, 25],
                                  [Timestamp("01/01/2016  13:00:00"), 300, 1000, 35],
                                  [Timestamp("01/01/2016  14:00:00"), 300, 1000, 35],
                              ])

    de_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 1000, 5000, 200],
                                  [Timestamp("01/01/2015  13:00:00"), 1000, 5000, 300],
                                  [Timestamp("01/01/2015  14:00:00"), 1000, 5000, 300],
                                  [Timestamp("01/01/2016  12:00:00"), 1000, 5000, 250],
                                  [Timestamp("01/01/2016  13:00:00"), 1000, 5000, 350],
                                  [Timestamp("01/01/2016  14:00:00"), 1000, 5000, 350],
                              ])

    fr_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 1200, 3000, 300],
                                  [Timestamp("01/01/2015  13:00:00"), 1200, 3000, 400],
                                  [Timestamp("01/01/2015  14:00:00"), 1200, 3000, 400],
                                  [Timestamp("01/01/2016  12:00:00"), 1200, 3000, 350],
                                  [Timestamp("01/01/2016  13:00:00"), 1200, 3000, 450],
                                  [Timestamp("01/01/2016  14:00:00"), 1200, 3000, 450],
                              ])

    # Function that returns the dataframe from the country code inside the filename
    def filename_to_df(filename: str) -> pd.DataFrame:
        if "AT" in filename:
            return at_prod_df
        if "DE" in filename:
            return de_prod_df
        if "FR" in filename:
            return fr_prod_df
        raise Exception(f"Unexpected filename {filename}")

    # This line tells python so emulate 'read_excel' function and to apply the side_effect instead
    # Therefore, calling 'read_excel' will call filename_to_df and return the expected dataframe
    read_excel_mock = patch("pandas.read_excel",
                            side_effect=lambda filename, **kwargs: filename_to_df(filename.stem)).start()

    yield {
        'mocks': {
            'pandas.read_excel': read_excel_mock
        }
    }

    patch.stopall()  # Cancel the patch command on 'read excel' (or any function)


def test_load_database_prod_user_creates_expected_dictionary_structure(prod_setup):
    # Set inputs
    fake_folder_path = Path("fake/database/folder/path")
    country_list = ["FR", "DE"]  # AT is not required
    start_year = 2015
    end_year = 2015  # Get only data of 2015
    read_excel_mock = prod_setup["mocks"]["pandas.read_excel"]

    # Run function
    production_dict = load_database_prod_user(fake_folder_path, country_list, start_year, end_year)

    # Check 'read_excel' calls
    assert read_excel_mock.call_count == 2  # One for each country
    read_excel_mock.assert_has_calls([  # Check the parameter in each call
        call(fake_folder_path / "Prod_FR_2015_2019.xlsx", sheet_name="Prod_FR_2015_2019", header=0),
        call(fake_folder_path / "Prod_DE_2015_2019.xlsx", sheet_name="Prod_DE_2015_2019", header=0),
    ])

    # Check the output of the function
    # Expected structure is {country1 : {prod_type1 : {hour1:value, hour2:value...}, ... }, ...}
    # Therefore a dictionary of depth 3
    assert get_dict_depth(production_dict) == 3

    expected_value = {
        # Only FR and DE
        'FR': {
            'biomass_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 1200,
                Timestamp("01/01/2015  13:00:00"): 1200,
                Timestamp("01/01/2015  14:00:00"): 1200
            },
            'fossil_gas_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 3000,
                Timestamp("01/01/2015  13:00:00"): 3000,
                Timestamp("01/01/2015  14:00:00"): 3000
            },
            'solar_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 300,
                Timestamp("01/01/2015  13:00:00"): 400,
                Timestamp("01/01/2015  14:00:00"): 400
            }
        },
        'DE': {
            'biomass_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 1000,
                Timestamp("01/01/2015  13:00:00"): 1000,
                Timestamp("01/01/2015  14:00:00"): 1000
            },
            'fossil_gas_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 5000,
                Timestamp("01/01/2015  13:00:00"): 5000,
                Timestamp("01/01/2015  14:00:00"): 5000
            },
            'solar_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 200,
                Timestamp("01/01/2015  13:00:00"): 300,
                Timestamp("01/01/2015  14:00:00"): 300
            }
        }
    }

    assert production_dict == expected_value


def test_load_database_prod_user_raise_error_if_end_year_is_smaller_than_start_year(prod_setup):
    # Set inputs
    fake_folder_path = Path("fake/database/folder/path")
    country_list = ["FR", "DE"]
    start_year = 2017
    end_year = 2015  # Smaller that start year !
    read_excel_mock = prod_setup["mocks"]["pandas.read_excel"]

    # Run function
    with pytest.raises(ValueError) as e:
        load_database_prod_user(fake_folder_path, country_list, start_year, end_year)

    # Check 'read_excel' calls
    read_excel_mock.assert_not_called()

    # Check the error message
    assert e.value.args[0] == "End year cannot be before start year"


@pytest.fixture(scope='function')
def spot_setup():
    spot_2015_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR"],
        index=[Timestamp("01/01/2015  12:00:00"), Timestamp("01/01/2015  13:00:00"), Timestamp("01/01/2015  14:00:00")],
        data=[
            [np.nan, 25, 20, 30],
            [35, 20, 20, 35],
            [30, 18, 20, 30],
        ]
    )

    spot_2016_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR"],
        index=[Timestamp("01/01/2016  12:00:00"), Timestamp("01/01/2016  13:00:00"), Timestamp("01/01/2016  14:00:00")],
        data=[
            [30, 30, 20, 30],
            [25, 35, 20, 25],
            [10, 20, 20, 10],
        ]
    )

    spot_2017_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR"],
        index=[Timestamp("01/01/2017  12:00:00"), Timestamp("01/01/2017  13:00:00"), Timestamp("01/01/2017  14:00:00")],
        data=[
            [30, 25, 20, 30],
            [35, 20, 20, 35],
            [30, 18, 20, 30],
        ]
    )

    # Function that returns the dataframe from the year inside the filename
    def filename_to_df(filename: str) -> pd.DataFrame:
        if "2015" in filename:
            return spot_2015_df
        if "2016" in filename:
            return spot_2016_df
        if "2017" in filename:
            return spot_2017_df
        raise Exception(f"Unexpected filename {filename}")

    # This line tells python so emulate 'read_excel' function and to apply the side_effect instead
    # Therefore, calling 'read_excel' will call filename_to_df and return the expected dataframe
    read_excel_mock = patch("pandas.read_excel",
                            side_effect=lambda filename, **kwargs: filename_to_df(filename.stem)).start()

    yield {
        'mocks': {
            'pandas.read_excel': read_excel_mock
        }
    }

    patch.stopall()  # Cancel the patch command on 'read excel' (or any function)


def test_load_database_price_user_creates_expected_dictionary_structure(spot_setup):
    # Set inputs
    fake_folder_path = Path("fake/database/folder/path")
    country_list = ["DK", "BE"]  # FR is not required
    start_year = 2015
    end_year = 2016  # Get data from 2015 to 2016
    read_excel_mock = spot_setup["mocks"]["pandas.read_excel"]

    # Run function
    price_dict = load_database_price_user(fake_folder_path, country_list, start_year, end_year)

    # Check 'read_excel' calls
    assert read_excel_mock.call_count == 2  # One for each year
    read_excel_mock.assert_has_calls([  # Check the parameter in each call
        call(fake_folder_path / "SPOT_2015.xlsx", sheet_name="SPOT_2015", header=0, index_col=0),
        call(fake_folder_path / "SPOT_2016.xlsx", sheet_name="SPOT_2016", header=0, index_col=0),
    ])

    # Check the output of the function
    # Expected structure is {country1 : {hour1:value, hour2:value...}, ...}
    # Therefore a dictionary of depth 2
    assert get_dict_depth(price_dict) == 2

    expected_value = {
        # Only BE and DK
        'BE': {
            # Only 2015 and 2016 time steps
            Timestamp("01/01/2015  12:00:00"): ANY,  # Value is np.nan But np.nan!=np.nan
            Timestamp("01/01/2015  13:00:00"): 35.,
            Timestamp("01/01/2015  14:00:00"): 30.,
            Timestamp("01/01/2016  12:00:00"): 30.,
            Timestamp("01/01/2016  13:00:00"): 25.,
            Timestamp("01/01/2016  14:00:00"): 10.
        },
        'DK': {
            # Only 2015 and 2016 time steps
            Timestamp("01/01/2015  12:00:00"): 22.5,
            Timestamp("01/01/2015  13:00:00"): 20.,
            Timestamp("01/01/2015  14:00:00"): 19.,
            Timestamp("01/01/2016  12:00:00"): 25.,
            Timestamp("01/01/2016  13:00:00"): 27.5,
            Timestamp("01/01/2016  14:00:00"): 20.
        }
    }

    assert price_dict == expected_value
    assert pd.isna(price_dict["BE"][Timestamp("01/01/2015  12:00:00")])


def test_load_database_price_user_raise_error_if_end_year_is_smaller_than_start_year(spot_setup):
    # Set inputs
    fake_folder_path = Path("fake/database/folder/path")
    country_list = ["DK", "BE"]
    start_year = 2017
    end_year = 2015  # Smaller that start year !
    read_excel_mock = spot_setup["mocks"]["pandas.read_excel"]

    # Run function
    with pytest.raises(ValueError) as e:
        load_database_price_user(fake_folder_path, country_list, start_year, end_year)

    # Check 'read_excel' calls
    read_excel_mock.assert_not_called()

    # Check the error message
    assert e.value.args[0] == "End year cannot be before start year"
