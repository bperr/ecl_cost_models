from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest
from pandas import Timestamp

from src.input_reader import InputReader


def set_parse_side_effect(dataframes: dict[str, pd.DataFrame], mocks: dict):
    mocks['pandas.ExcelFile.parse'].side_effect = lambda sheet_name, **kwargs: dataframes[sheet_name]

# -------------- Tests for user inputs -------------- #

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

    fake_work_dir = Path("fake/work/dir")
    fake_db_dir = Path("fake/db/dir")
    # Creates an instance of InputReader with the fake directories
    reader = InputReader(work_dir=fake_work_dir, db_dir=fake_db_dir)

    yield {
        'data': {
            'dataframes': {  # Keys are sheet names, values are dataframes
                'Clustering': clustering_df,
                'Zones': zones_df,
                'Sectors': sectors_df,
                'Years': years_df,
            },
            'reader': reader,
            'fake directories': {
                'fake work dir': fake_work_dir,
                'fake db dir': fake_db_dir}
        },
        'mocks': {
            'pathlib.Path.exists': file_exist_mock,
            'pandas.ExcelFile': pd_excel_file_mock,
            'pandas.ExcelFile.parse': parse_mock,
            'warnings.warn': warning_mock
        }
    }

    patch.stopall()


def test_read_user_inputs_raise_error_if_file_does_not_exist(setup):

    fake_file_path = setup["data"]["fake directories"]["fake work dir"] / "User_inputs.xlsx"
    mocks = setup["mocks"]

    # Update pathlib.Path.exists mock to return False
    mocks["pathlib.Path.exists"].return_value = False

    # Run test
    with pytest.raises(FileNotFoundError) as error:
        setup["data"]["reader"].read_user_inputs()

    # Check mocks call
    mocks["pathlib.Path.exists"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_not_called()
    mocks["pandas.ExcelFile.parse"].assert_not_called()
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == f"File not found: {fake_file_path}"


@pytest.mark.parametrize("sheet_name,column_to_drop",
                         [("Years", "Year min"), ("Sectors", "Main sector"), ("Zones", "Node"),
                          ("Clustering", "Main sector")])
def test_read_user_inputs_raise_error_if_a_column_is_missing(setup, sheet_name, column_to_drop):
    fake_file_path = setup["data"]["fake directories"]["fake work dir"] / "User_inputs.xlsx"
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]

    # Remove a column from years dataframe
    df = dataframes[sheet_name]
    df.drop(columns=[column_to_drop], inplace=True)
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    with pytest.raises(ValueError) as error:
        setup["data"]["reader"].read_user_inputs()

    # Check mocks call
    mocks["pathlib.Path.exists"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile.parse"].assert_called()
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == (f"Error while reading the Excel file: "
                                   f"Missing columns in '{sheet_name}' sheet: { {column_to_drop} }")  # noqa


def test_read_user_inputs_raise_error_if_a_year_min_is_greater_than_year_max(setup):
    fake_file_path = setup["data"]["fake directories"]["fake work dir"] / "User_inputs.xlsx"
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]

    # Update year min in Years dataframe
    years_df = dataframes["Years"]
    years_df.loc[0, "Year min"] = years_df.loc[0, "Year max"] + 1
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    with pytest.raises(ValueError) as error:
        setup["data"]["reader"].read_user_inputs()

    # Check mocks call
    mocks["pathlib.Path.exists"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile"].assert_called_once_with(fake_file_path)
    mocks["pandas.ExcelFile.parse"].assert_called_once_with('Years', dtype={'Year min': int, 'Year max': int,
                                                                            'Min initial price': int,
                                                                            'Max initial price': int})
    mocks["warnings.warn"].assert_not_called()

    # Check error message
    assert error.value.args[0] == ("Error while reading the Excel file: Invalid data in 'Years' sheet: 'Year min' must "
                                   "be <= 'Year max' for all rows.")


def test_read_user_inputs_returns_expected_results_while_raising_warnings(setup):
    fake_file_path = setup["data"]["fake directories"]["fake work dir"] / "User_inputs.xlsx"
    mocks = setup["mocks"]
    dataframes = setup["data"]["dataframes"]
    set_parse_side_effect(dataframes=dataframes, mocks=mocks)

    # Run test
    years, countries_group, sectors_group, storages = setup["data"]["reader"].read_user_inputs()

    # Check mocks call
    mocks["pathlib.Path.exists"].assert_called_once_with(fake_file_path)
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
    assert years == [(2015, 2016, 0, 120, 0, 120, 12)]
    assert countries_group == {'IBR': ["ES", "PT"]}
    assert sectors_group == {'RES': ["biomass", "geothermal"], 'Storage': ["hydro_pumped_storage"]}
    assert storages == ["Storage"]

# -------------- Tests for DataBase -------------- #

# --- Production --- #

@pytest.fixture(scope='function')
def prod_setup():
    fake_work_dir = Path("fake/work/dir")
    fake_db_dir = Path("fake/db/dir")
    # Creates an instance of InputReader with the fake directories
    reader = InputReader(work_dir=fake_work_dir, db_dir=fake_db_dir)

    # We consider that no cell is empty in the production DataBase
    at_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW","wind_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 300, 1000, 20, 10],
                                  [Timestamp("01/01/2015  13:00:00"), 300, 1000, 30, 10],
                                  [Timestamp("01/01/2015  14:00:00"), 300, 1000, 30, 10],
                                  [Timestamp("01/01/2016  12:00:00"), 300, 1000, 25, 10],
                                  [Timestamp("01/01/2016  13:00:00"), 300, 1000, 35, 10],
                                  [Timestamp("01/01/2016  14:00:00"), 300, 1000, 35, 10],
                              ])

    de_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW","wind_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 1000, 5000, 200, 50],
                                  [Timestamp("01/01/2015  13:00:00"), 1000, 5000, 300, 50],
                                  [Timestamp("01/01/2015  14:00:00"), 1000, 5000, 300, 50],
                                  [Timestamp("01/01/2016  12:00:00"), 1000, 5000, 250, 50],
                                  [Timestamp("01/01/2016  13:00:00"), 1000, 5000, 350, 50],
                                  [Timestamp("01/01/2016  14:00:00"), 1000, 5000, 350, 50],
                              ])

    fr_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW","wind_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 1200, 3000, 300, 0],
                                  [Timestamp("01/01/2015  13:00:00"), 1200, 3000, 400, 0],
                                  [Timestamp("01/01/2015  14:00:00"), 1200, 3000, 400, 0],
                                  [Timestamp("01/01/2016  12:00:00"), 1200, 3000, 350, 0],
                                  [Timestamp("01/01/2016  13:00:00"), 1200, 3000, 450, 0],
                                  [Timestamp("01/01/2016  14:00:00"), 1200, 3000, 450, 0],
                              ])

    es_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW","wind_MW"],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 900, 2000, 2100, 40],
                                  [Timestamp("01/01/2015  13:00:00"), 900, 2000, 2100, 40],
                                  [Timestamp("01/01/2015  14:00:00"), 900, 2000, 2100, 40],
                                  [Timestamp("01/01/2016  12:00:00"), 900, 2000, 2100, 40],
                                  [Timestamp("01/01/2016  13:00:00"), 900, 2000, 2100, 40],
                                  [Timestamp("01/01/2016  14:00:00"), 900, 2000, 2100, 40],
                              ])

    pt_prod_df = pd.DataFrame(columns=["Début de l'heure", "biomass_MW", "fossil_gas_MW", "solar_MW",'wind_MW'],
                              data=[
                                  [Timestamp("01/01/2015  12:00:00"), 800, 1800, 1800, 20],
                                  [Timestamp("01/01/2015  13:00:00"), 800, 1800, 1800, 20],
                                  [Timestamp("01/01/2015  14:00:00"), 800, 1800, 1800, 20],
                                  [Timestamp("01/01/2016  12:00:00"), 800, 1800, 1800, 20],
                                  [Timestamp("01/01/2016  13:00:00"), 800, 1800, 1800, 20],
                                  [Timestamp("01/01/2016  14:00:00"), 800, 1800, 1800, 20],
                              ])

    def filename_to_df(filename: str) -> pd.DataFrame:
        if "AT" in filename:
            return at_prod_df
        if "DE" in filename:
            return de_prod_df
        if "FR" in filename:
            return fr_prod_df
        if "ES" in filename:
            return es_prod_df
        if "PT" in filename:
            return pt_prod_df
        raise Exception(f"Unexpected filename {filename}")

    # This line tells python to emulate 'read_excel' function and to apply the side_effect instead
    # Therefore, calling 'read_excel' will call filename_to_df and return the expected dataframe
    read_excel_mock = patch("pandas.read_excel",
                            side_effect=lambda filename, **kwargs: filename_to_df(filename.stem)).start()

    yield {'reader': reader,
           'fake directories': {
               'fake work dir': fake_work_dir,
               'fake db dir': fake_db_dir},
            'mocks': {
                'pandas.read_excel': read_excel_mock}
    }

    patch.stopall()  # Cancel the patch command on 'read excel' (or any function)

def test_load_database_prod_user_creates_expected_dictionary_structure(prod_setup):
    # Set inputs
    fake_folder_path = prod_setup["fake directories"]["fake db dir"] / "Production par pays et par filière 2015-2019"

    reader = prod_setup["reader"]
    reader.years=[(2015, 2015, 0, 120, 0, 120, 12)]
    reader.zones={"FR": ["FR"], "DE":["DE"], "IBR":['ES', 'PT']}
    reader.sectors_group = {'biomass_MW':{'biomass_MW'},
                                          'fossil_gas_MW':{'fossil_gas_MW'},
                                          'RES_MW':{'solar_MW','wind_MW'}}

    read_excel_mock = prod_setup["mocks"]["pandas.read_excel"]

    # Run function
    historical_power = reader.read_db_powers()

    # Check 'read_excel' calls
    assert read_excel_mock.call_count == 4  # One for each country called
    read_excel_mock.assert_has_calls([  # Check the parameter in each call
        call(fake_folder_path / "Prod_FR_2015_2019.xlsx", sheet_name="Prod_FR_2015_2019", header=0),
        call(fake_folder_path / "Prod_DE_2015_2019.xlsx", sheet_name="Prod_DE_2015_2019", header=0),
        call(fake_folder_path / "Prod_ES_2015_2019.xlsx", sheet_name="Prod_ES_2015_2019", header=0),
        call(fake_folder_path / "Prod_PT_2015_2019.xlsx", sheet_name="Prod_PT_2015_2019", header=0)
    ], any_order=True)

    # Check the output of the function
    # Expected structure is {zone : DataFrame (col=sector)}
    assert isinstance(historical_power, dict)
    assert all(isinstance(zone, str) for zone in historical_power)
    assert all(isinstance(df, pd.DataFrame) for df in historical_power.values())

    expected_value = {
        # Only FR and DE
        'FR': pd.DataFrame({
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
            'RES_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 300,
                Timestamp("01/01/2015  13:00:00"): 400,
                Timestamp("01/01/2015  14:00:00"): 400
            }
        }),
        'DE': pd.DataFrame({
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
            'RES_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 250,
                Timestamp("01/01/2015  13:00:00"): 350,
                Timestamp("01/01/2015  14:00:00"): 350
            }
        }),
        'IBR': pd.DataFrame({
            'biomass_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 1700,
                Timestamp("01/01/2015  13:00:00"): 1700,
                Timestamp("01/01/2015  14:00:00"): 1700
            },
            'fossil_gas_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 3800,
                Timestamp("01/01/2015  13:00:00"): 3800,
                Timestamp("01/01/2015  14:00:00"): 3800
            },
            'RES_MW': {
                # Only 2015 time steps
                Timestamp("01/01/2015  12:00:00"): 3960,
                Timestamp("01/01/2015  13:00:00"): 3960,
                Timestamp("01/01/2015  14:00:00"): 3960
            }
        })
    }
    expected_value['FR'].index.name = 'Début de l\'heure'
    expected_value['DE'].index.name = 'Début de l\'heure'
    expected_value['IBR'].index.name = 'Début de l\'heure'

    for zone in ["FR", "DE","IBR"]:
        pd.testing.assert_frame_equal(historical_power[zone], expected_value[zone])

# --- Prices --- #

@pytest.fixture(scope='function')
def spot_setup():
    fake_work_dir = Path("fake/work/dir")
    fake_db_dir = Path("fake/db/dir")
    # Creates an instance of InputReader with the fake directories
    reader = InputReader(work_dir=fake_work_dir, db_dir=fake_db_dir)

    spot_2015_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR", "GE"],
        index=[Timestamp("01/01/2015  12:00:00"), Timestamp("01/01/2015  13:00:00"), Timestamp("01/01/2015  14:00:00")],
        data=[
            [np.nan, 25, 20, 30, 10],
            [35, 20, 20, 35, 10],
            [30, 18, 20, 30, 20],
        ]
    )

    spot_2016_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR", "GE"],
        index=[Timestamp("01/01/2016  12:00:00"), Timestamp("01/01/2016  13:00:00"), Timestamp("01/01/2016  14:00:00")],
        data=[
            [30, 30, 20, 30, 20],
            [25, 35, 20, 25, 20],
            [10, 20, 20, 10, 20],
        ]
    )

    spot_2017_df = pd.DataFrame(
        columns=["BE", "DK1", "DK2", "FR", "GE"],
        index=[Timestamp("01/01/2017  12:00:00"), Timestamp("01/01/2017  13:00:00"), Timestamp("01/01/2017  14:00:00")],
        data=[
            [30, 25, 20, 30, 30],
            [35, 20, 20, 35, 30],
            [30, 18, 20, 30, 30],
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

    # This line tells python to emulate 'read_excel' function and to apply the side_effect instead
    # Therefore, calling 'read_excel' will call filename_to_df and return the expected dataframe
    read_excel_mock = patch("pandas.read_excel",
                            side_effect=lambda filename, **kwargs: filename_to_df(filename.stem)).start()

    yield {'reader': reader,
           'fake directories': {
               'fake work dir': fake_work_dir,
               'fake db dir': fake_db_dir},
           'mocks': {
               'pandas.read_excel': read_excel_mock}
           }

    patch.stopall()  # Cancel the patch command on 'read excel' (or any function)

def test_load_database_price_user_creates_expected_dataframe_structure(spot_setup):
    # Set inputs
    fake_folder_path = spot_setup["fake directories"]["fake db dir"] / "Prix spot par an et par zone 2015-2019"

    reader = spot_setup['reader']
    reader.years = [(2015, 2016, 0, 120, 0, 120, 12)] # Get data from 2015 to 2016
    reader.zones = {"BE": ["BE"], "DK": ["DK"],"FG":["FR","GE"]}

    read_excel_mock = spot_setup["mocks"]["pandas.read_excel"]

    # Run function
    historical_prices = reader.read_db_prices()

    # Check 'read_excel' calls
    assert read_excel_mock.call_count == 2  # One for each year
    read_excel_mock.assert_has_calls([  # Check the parameter in each call
        call(fake_folder_path / "SPOT_2015.xlsx", sheet_name="SPOT_2015", header=0, index_col=0),
        call(fake_folder_path / "SPOT_2016.xlsx", sheet_name="SPOT_2016", header=0, index_col=0),
    ])

    # Check the output of the function
    # Expected structure is DataFrame (col=zone)
    assert isinstance(historical_prices, pd.DataFrame)

    expected_value = pd.DataFrame({
        # BE, DK and FR&GE
        'BE': {
            # Only 2015 and 2016 time steps
            Timestamp("01/01/2015  12:00:00"): np.nan,  # Value is np.nan But np.nan!=np.nan
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
        },
        'FG': {
            # Only 2015 and 2016 time steps
            Timestamp("01/01/2015  12:00:00"): 20.,
            Timestamp("01/01/2015  13:00:00"): 22.5,
            Timestamp("01/01/2015  14:00:00"): 25.,
            Timestamp("01/01/2016  12:00:00"): 25.,
            Timestamp("01/01/2016  13:00:00"): 22.5,
            Timestamp("01/01/2016  14:00:00"): 15.
        }
    })

    pd.testing.assert_frame_equal(historical_prices, expected_value)

# -------------- Test for Price Models -------------- #

@pytest.fixture(scope='function')
def pmodel_setup():
    fake_work_dir = Path("fake/work/dir")
    fake_db_dir = Path("fake/db/dir")

    reader = InputReader(work_dir=fake_work_dir, db_dir=fake_db_dir)

    df_2015 = pd.DataFrame({
        "Zone": ["BE", "BE", "BE", "BE", "FR", "FR", "FR", "FR"],
        "Price Type": ["Cons_max", "Cons_min", "Prod_min", "Prod_max"] * 2,
        "coal": [np.nan, np.nan, 5, 80, np.nan, np.nan, 50, 80],
        "gas": [np.nan] * 4 + [np.nan, np.nan, 15, 70],
        "hydro damp": [10, 30, 40, 90, np.nan, np.nan, 20, 90],
        "nuclear": [np.nan, np.nan, -20, 60, np.nan, np.nan, -10, 60]
    })

    df_2016 = pd.DataFrame({
        "Zone": ["BE", "BE", "BE", "BE", "FR", "FR", "FR", "FR"],
        "Price Type": ["Cons_max", "Cons_min", "Prod_min", "Prod_max"] * 2,
        "coal": [np.nan, np.nan, 6, 60, np.nan, np.nan, 30, 80],
        "gas": [np.nan] * 4 + [np.nan, np.nan, 10, 50],
        "hydro damp": [5, 40, 40, 100, np.nan, np.nan, 10, 80],
        "nuclear": [np.nan, np.nan, 0, 50, np.nan, np.nan, 10, 60]
    })

    # Mock ExcelFile object
    mock_xls = MagicMock()
    mock_xls.sheet_names = ["2015", "2016"]

    # Patch ExcelFile call to return the mocked object
    excel_file_mock = patch("pandas.ExcelFile", return_value=mock_xls).start()

    # Patch read_excel to return the correct df based on sheet name
    def sheetname_to_df(xls,sheet_name, **kwargs):
        if sheet_name == "2015":
            return df_2015
        elif sheet_name == "2016":
            return df_2016
        else:
            raise ValueError(f"Unexpected sheet name: {sheet_name}")

    read_excel_mock = patch("pandas.read_excel", side_effect=sheetname_to_df).start()

    yield {
        "reader": reader,
        "fake directories": {
            "fake work dir": fake_work_dir,
            "fake db dir": fake_db_dir
        },
        "mocks": {
            "pandas.ExcelFile": excel_file_mock,
            "pandas.read_excel": read_excel_mock
        }}

    patch.stopall()

def test_load_price_models_user_creates_expected_dictionary_structure(pmodel_setup):
    # Set inputs
    fake_folder_path = pmodel_setup["fake directories"]["fake work dir"] / "results"

    reader = pmodel_setup["reader"]

    reader.years = [(2015, 2016, 0, 120, 0, 120, 12)] # Get data from 2015 to 2016
    reader.zones = {"BE": ["BE"], "FR": ["FR"]}
    reader.storages = {"hydro damp"}

    read_excel_mock = pmodel_setup["mocks"]["pandas.read_excel"]
    excel_file_mock = pmodel_setup["mocks"]["pandas.ExcelFile"]

    # Run function
    results = reader.read_price_models()

    # Assert ExcelFile and read_excel are called as expected
    assert read_excel_mock.call_count == 2
    read_excel_mock.assert_has_calls([  # Check the parameter in each call
        call(fake_folder_path / "Output_prices.xlsx", sheet_name="2015", header=0, index_col=0),
        call(fake_folder_path / "Output_prices.xlsx", sheet_name="2016", header=0, index_col=0),
    ])
    excel_file_mock.assert_called_once_with(fake_folder_path / "Output_prices.xlsx")

    # Expected results dictionary
    expected = {
        "2015": {
            "BE": {
                "coal": [None, None, 5, 80],
                "hydro damp": [10, 30, 40, 90],
                "nuclear": [None, None, -20, 60]
            },
            "FR": {
                "coal": [None, None, 50, 80],
                "gas": [None, None, 15, 70],
                "hydro damp": [None, None, 20, 90],
                "nuclear": [None, None, -10, 60]
            }
        },
        "2016": {
            "BE": {
                "coal": [None, None, 6, 60],
                "hydro damp": [5, 40, 40, 100],
                "nuclear": [None, None, 0, 50]
            },
            "FR": {
                "coal": [None, None, 30, 80],
                "gas": [None, None, 10, 50],
                "hydro damp": [None, None, 10, 80],
                "nuclear": [None, None, 10, 60]
            }
        }
    }

    assert results == expected

def test_read_price_models_error_if_consumption_for_non_storage(pmodel_setup):
    reader = pmodel_setup["reader"]
    reader.storages = ["battery"]

    df_invalid = pd.DataFrame({
        "Zone": ["BE"],
        "Price Type": ["Cons_max"],
        "gas": [10],  # gas is not a storage
    })

    mock_xls = MagicMock()
    mock_xls.sheet_names = ["2015"]

    with patch("pandas.ExcelFile", return_value=mock_xls), \
         patch("pandas.read_excel", return_value=df_invalid):
        with pytest.raises(ValueError, match=r"n'est pas un stockage"):
            reader.read_price_models()

def test_read_price_models_raises_if_prod_min_gt_max(pmodel_setup):
    reader = pmodel_setup["reader"]
    reader.storages = ["battery"]

    df_invalid = pd.DataFrame({
        "Zone": ["BE", "BE"],
        "Price Type": ["Prod_min", "Prod_max"],
        "coal": [100, 50]  # Prod_min > Prod_max
    })

    mock_xls = MagicMock()
    mock_xls.sheet_names = ["2015"]

    with patch("pandas.ExcelFile", return_value=mock_xls), \
         patch("pandas.read_excel", return_value=df_invalid):
        with pytest.raises(ValueError, match=r"Prod_min > Prod_max"):
            reader.read_price_models()

def test_read_price_models_raises_if_cons_max_gt_min(pmodel_setup):
    reader = pmodel_setup["reader"]
    reader.storages = ["battery"]

    df_invalid = pd.DataFrame({
        "Zone": ["BE", "BE"],
        "Price Type": ["Cons_max", "Cons_min"],
        "battery": [80, 30]  # Cons_max > Cons_min
    })

    mock_xls = MagicMock()
    mock_xls.sheet_names = ["2015"]

    with patch("pandas.ExcelFile", return_value=mock_xls), \
         patch("pandas.read_excel", return_value=df_invalid):
        with pytest.raises(ValueError, match=r"Cons_max > Cons_min"):
            reader.read_price_models()
