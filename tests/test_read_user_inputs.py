from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from src.read_user_inputs import read_user_inputs


def set_parse_side_effect(dataframes: dict[str, pd.DataFrame], mocks: dict):
    mocks['pandas.ExcelFile.parse'].side_effect = lambda sheet_name, **kwargs: dataframes[sheet_name]


@pytest.fixture(scope='function')
def setup():
    # Emulate 'exists()' method of Path objects to return True. autospec=True allows to catch the object that called the
    # method.
    file_exist_mock = patch.object(Path, "exists", autospec=True, return_value=True).start()

    years_df = pd.DataFrame(columns=["Year min", "Year max", "Min initial price", "Max initial price"],
                            data=[[2015, 2016, 0, 120]])
    zones_df = pd.DataFrame(columns=["Node", "Country names", "Zone", "Zone name"],
                            data=[["ES", "Spain", "IBR", "Iberian"], ["PT", "Portugal", "IBR", "Iberian"]])
    sectors_df = pd.DataFrame(columns=["Detailed sector", "Main sector"],
                              data=[["biomass", "RES"], ["geothermal", "RES"], ["hydro_pumped_storage", "Storage"]])
    clustering_df = pd.DataFrame(columns=["Zone", "Zone name", "Unnamed", "Main sector", "Is storage"],
                                 data=[["IBR", "Iberian", np.nan, "RES", 0],
                                       ["FR", "France", np.nan, "Storage", 1],
                                       [np.nan, np.nan, np.nan, "Nuclear", 0]])

    # Emulate pd.ExcelFile
    fake_excel_file = MagicMock(autospec=True)
    pd_excel_file_mock = patch("pandas.ExcelFile", return_value=fake_excel_file).start()

    # Emulate 'parse()' method of the excel_file_mock
    parse_mock = patch.object(fake_excel_file, "parse").start()

    # Emulate 'warnings.warn'
    warning_mock = patch("warnings.warn").start()

    yield {
        'data': {
            'dataframes': {  # Keys are sheet names, values are dataframes
                'Clustering': clustering_df,
                'Zones': zones_df,
                'Sectors': sectors_df,
                'Years': years_df,
            },
        },
        'mocks': {
            'pathlib.Path.exist': file_exist_mock,
            'pandas.ExcelFile': pd_excel_file_mock,
            'pandas.ExcelFile.parse': parse_mock,
            'warnings.warn': warning_mock
        }
    }

    patch.stopall()


def test_read_user_inputs_raise_error_if_file_does_not_exist(setup):
    fake_file_path = Path("fake/file/path")
    mocks = setup["mocks"]

    # Update pathlib.Path.exist mock to return False
    mocks["pathlib.Path.exist"].return_value = False

    # Run test
    with pytest.raises(FileNotFoundError) as error:
        read_user_inputs(fake_file_path)

    # Check mocks call
    mocks["pathlib.Path.exist"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_not_called()
    mocks["pandas.ExcelFile.parse"].assert_not_called()
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == f"File not found: {fake_file_path}"


@pytest.mark.parametrize("sheet_name,column_to_drop",
                         [("Years", "Year min"), ("Sectors", "Main sector"), ("Zones", "Node"),
                          ("Clustering", "Main sector")])
def test_read_user_inputs_raise_error_if_a_column_is_missing(setup, sheet_name, column_to_drop):
    fake_file_path = Path("fake/file/path")
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]

    # Remove a column from years dataframe
    df = dataframes[sheet_name]
    df.drop(columns=[column_to_drop], inplace=True)
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    with pytest.raises(ValueError) as error:
        read_user_inputs(fake_file_path)

    # Check mocks call
    mocks["pathlib.Path.exist"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile.parse"].assert_called()
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == (f"Error while reading the Excel file: "
                                   f"Missing columns in '{sheet_name}' sheet: { {column_to_drop} }")  # noqa


def test_read_user_inputs_raise_error_if_a_year_min_is_greater_than_year_max(setup):
    fake_file_path = Path("fake/file/path")
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]

    # Update year min in Years dataframe
    years_df = dataframes["Years"]
    years_df.loc[0, "Year min"] = years_df.loc[0, "Year max"] + 1
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    with pytest.raises(ValueError) as error:
        read_user_inputs(fake_file_path)

    # Check mocks call
    mocks["pathlib.Path.exist"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile.parse"].assert_called_once_with('Years', dtype={'Year min': int, 'Year max': int,
                                                                            'Min initial price': int,
                                                                            'Max initial price': int})
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == ("Error while reading the Excel file: Invalid data in 'Years' sheet: 'Year min' must "
                                   "be <= 'Year max' for all rows.")


def test_read_user_inputs_returns_expected_results_while_raising_warnings(setup):
    fake_file_path = Path("fake/file/path")
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    user_inputs = read_user_inputs(fake_file_path)

    # Check mocks call
    mocks["pathlib.Path.exist"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_file_path)
    assert mocks["pandas.ExcelFile.parse"].call_count == 4
    mocks["pandas.ExcelFile.parse"].assert_has_calls([
        call('Years', dtype={'Year min': int, 'Year max': int, 'Min initial price': int, 'Max initial price': int}),
        call('Zones', dtype=str),
        call("Sectors", dtype=str),
        call("Clustering", dtype={'Is storage': float})
    ])
    assert mocks["warnings.warn"].call_count == 2
    mocks["warnings.warn"].assert_has_calls([
        call("The following 'Main sector' values from 'Clustering' do not appear in sheet 'Sectors': {'Nuclear'}",
             stacklevel=2),
        call("The following 'Zone' values from 'Clustering' do not appear in sheet 'Zones': {'FR'}",
             stacklevel=2),
    ])

    # Check results
    years, countries_group, sectors_group, storages = user_inputs
    assert years == [(2015, 2016, 0, 120, 0, 120, 12)]
    assert countries_group == {'IBR': ["ES", "PT"]}
    assert sectors_group == {'RES': ["biomass", "geothermal"], 'Storage': ["hydro_pumped_storage"]}
    assert storages == ["Storage"]
