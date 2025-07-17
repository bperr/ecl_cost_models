from pathlib import Path
from unittest.mock import MagicMock, call, patch, ANY

import pandas as pd
import pytest
from pandas import Timestamp
from pandas.testing import assert_series_equal

from src.controller import Controller
from src.controller import SIMULATED_POWERS_DIRECTORY_ROOT, SIMULATED_POWERS_FILE_ROOT
from src.zone import Zone


@pytest.fixture(scope="function")
def controller_setup():
    # --- Timestamps and data ---
    timestamps = [
        Timestamp("2015-01-01 12:00:00"),
        Timestamp("2015-02-01 13:00:00"),
        Timestamp("2015-03-10 14:00:00"),
        Timestamp("2016-01-05 15:00:00"),
        Timestamp("2016-03-15 10:00:00"),
    ]

    powers = {
        "IBR": pd.DataFrame({"solar": [200, 230, 230, 190, 150],
                             "hydro pump storage": [-200, -230, 0, 30, 10]},
                            index=timestamps),
        "FR": pd.DataFrame({"solar": [200, 230, 230, 190, 150],
                            "hydro pump storage": [0, 0, 0, -20, 10]},
                           index=timestamps),
    }
    prices = pd.DataFrame({
        "IBR": [50, 55, 53, 56, 58],
        "FR": [48, 52, 54, 53, 51],
    }, index=timestamps)

    prices_init = {
        "2015-2015": (0, 80, 0, 80, 8),
        "2016-2016": (0, 100, 0, 100, 10),
    }

    # --- Mocks ---
    input_reader_mock = MagicMock()
    input_reader_mock.read_db_prices.return_value = prices
    input_reader_mock.read_db_powers.return_value = powers
    input_reader_mock.read_user_inputs.return_value = (
        [(2015, 2015), (2016, 2016)], ["IBR", "FR"], ["solar", "hydro pump storage"], ["hydro pump storage"],
        ["hydro pump storage"], prices_init
    )
    input_reader_mock.work_dir = Path("fake/work_dir")

    # Patch InputReader
    input_reader_patch = patch("src.controller.InputReader", return_value=input_reader_mock).start()

    # Patch Network
    network_mock = MagicMock()
    patch("src.controller.Network", return_value=network_mock).start()

    # Patch mkdir
    patch("pathlib.Path.mkdir").start()

    # Patch pd.ExcelWriter
    excel_writer_patch = patch("pandas.ExcelWriter").start()

    work_dir = Path("fake/work_dir")
    db_dir = Path("fake/db_dir")
    controller = Controller(work_dir=work_dir, db_dir=db_dir)

    yield {
        "controller": controller,
        "input_reader": input_reader_mock,
        "network": network_mock,
        "excel_writer_patch": excel_writer_patch,
        "input_reader_patch": input_reader_patch,
        "work_dir": work_dir,
        "db_dir": db_dir,
    }

    patch.stopall()


# -------------- Price models methods --------------

def test_build_price_models(controller_setup):
    controller = controller_setup["controller"]
    network = controller_setup["network"]

    # Patch export_price_models
    with patch.object(controller, "export_price_models") as export_patch:
        controller.build_price_models()

    index_2015 = [
        Timestamp("2015-01-01 12:00:00"),
        Timestamp("2015-02-01 13:00:00"),
        Timestamp("2015-03-10 14:00:00")
    ]
    index_2016 = [
        Timestamp("2016-01-05 15:00:00"),
        Timestamp("2016-03-15 10:00:00")
    ]

    expected_powers = {"2015-2015-IBR": pd.DataFrame({"solar": [200, 230, 230],
                                                      "hydro pump storage": [-200, -230, 0]},
                                                     index=index_2015),
                       "2016-2016-IBR": pd.DataFrame({"solar": [190, 150],
                                                      "hydro pump storage": [30, 10]},
                                                     index=index_2016),
                       "2015-2015-FR": pd.DataFrame({"solar": [200, 230, 230],
                                                     "hydro pump storage": [0, 0, 0]},
                                                    index=index_2015),
                       "2016-2016-FR": pd.DataFrame({"solar": [190, 150],
                                                     "hydro pump storage": [-20, 10]},
                                                    index=index_2016)
                       }

    expected_prices = {"2015-2015-IBR": pd.Series([50, 55, 53], index=index_2015, name="IBR"),
                       "2016-2016-IBR": pd.Series([56, 58], index=index_2016, name="IBR"),
                       "2015-2015-FR": pd.Series([48, 52, 54], index=index_2015, name="FR"),
                       "2016-2016-FR": pd.Series([53, 51], index=index_2016, name="FR")
                       }

    # Check add_zone mock calls.
    assert network.add_zone.call_count == 4
    network.add_zone.assert_has_calls([
        call(zone_name="IBR", storages=["hydro pump storage"], controllable_sectors=['hydro pump storage'],
             sectors_historical_powers=ANY, historical_prices=ANY),
        call(zone_name="FR", storages=["hydro pump storage"], controllable_sectors=['hydro pump storage'],
             sectors_historical_powers=ANY, historical_prices=ANY),
        call(zone_name="IBR", storages=["hydro pump storage"], controllable_sectors=['hydro pump storage'],
             sectors_historical_powers=ANY, historical_prices=ANY),
        call(zone_name="FR", storages=["hydro pump storage"], controllable_sectors=['hydro pump storage'],
             sectors_historical_powers=ANY, historical_prices=ANY)
    ])

    # Verify series in calls
    expected_series = [
        (expected_powers["2015-2015-IBR"], expected_prices["2015-2015-IBR"]),
        (expected_powers["2015-2015-FR"], expected_prices["2015-2015-FR"]),
        (expected_powers["2016-2016-IBR"], expected_prices["2016-2016-IBR"]),
        (expected_powers["2016-2016-FR"], expected_prices["2016-2016-FR"]),
    ]
    for call_number, actual_call_args in enumerate(network.add_zone.call_args_list):
        expected_historical_powers = expected_series[call_number][0]
        expected_historical_prices = expected_series[call_number][1]
        pd.testing.assert_frame_equal(
            expected_historical_powers,
            actual_call_args.kwargs["sectors_historical_powers"]
        )
        pd.testing.assert_series_equal(
            expected_historical_prices,
            actual_call_args.kwargs["historical_prices"]
        )

    assert network.build_price_models.call_count == 2

    network.build_price_models.assert_has_calls([
        call(controller._prices_init["2015-2015"]),
        call(controller._prices_init["2016-2016"]),
    ])

    export_patch.assert_has_calls([
        call(2015, 2015, True, ANY),
        call(2016, 2016, False, ANY)
    ])


def create_mock_zone(name, sector_specs):
    """
    Creates a mock zone with sectors with respect to the specified specs

    :param name: name of the zone (str)
    :param sector_specs: List of tuples (name, is_storage_load, price_model)
    :return: MagicMock of zone
    """
    zone = MagicMock(spec=Zone)
    zone.name = name
    sectors = []
    for sector_name, is_storage_load, price_model in sector_specs:
        sector = MagicMock()
        sector.name = sector_name
        sector.is_storage_load = is_storage_load
        sector.price_model = price_model
        sectors.append(sector)
    zone.sectors = sectors
    return zone


def test_export_price_models(controller_setup):
    controller = controller_setup["controller"]
    network = controller_setup["network"]
    work_dir = controller_setup["work_dir"]

    # Create two zones with mocked sectors
    zone_mock_IBR = create_mock_zone("IBR", [
        ("hydro pump storage", True, (10, 0)),
        ("hydro pump storage", False, (60, 100)),
        ("solar", False, (20, 200)),
    ])

    zone_mock_FR = create_mock_zone("FR", [
        ("hydro pump storage", True, (20, 0)),
        ("hydro pump storage", False, (80, 100)),
        ("solar", False, (10, 100)),
    ])

    network.zones = {'IBR': zone_mock_IBR, 'FR': zone_mock_FR}
    controller._network = network

    written_df = {}  # to get the exported df

    def fake_to_excel(self, writer, index=False, sheet_name=None):  # to_excel mock
        written_df['df'] = self  # get df

    with patch("pandas.DataFrame.to_excel", new=fake_to_excel):
        current_date = "20250618_13h02"
        controller.export_price_models(start_year=2015, end_year=2015, create_file=True, current_date=current_date)
        df = written_df['df']

    # Ensure save_plots and pd.ExcelWriter are called with the good arguments
    zone_mock_IBR.save_plots.assert_called_with(
        Path(work_dir / f"results {current_date}/Plots for years 2015-2015"))
    zone_mock_FR.save_plots.assert_called_with(
        work_dir / f"results {current_date}/Plots for years 2015-2015")
    controller_setup["excel_writer_patch"].assert_called_with(
        work_dir / f"results {current_date}" / "Output_prices.xlsx",
        mode='w'
    )

    # check df
    expected_df = pd.DataFrame(
        columns=["Zone", "Price Type", "solar", "hydro pump storage"],
        data=[
            ["IBR", "Cons_max", None, 0],
            ["IBR", "Cons_min", None, 10],
            ["IBR", "Prod_min", 20, 60],
            ["IBR", "Prod_max", 200, 100],
            ["FR", "Cons_max", None, 0],
            ["FR", "Cons_min", None, 20],
            ["FR", "Prod_min", 10, 80],
            ["FR", "Prod_max", 100, 100]
        ],
    )
    pd.testing.assert_frame_equal(df, expected_df)


# -------------- OPF methods --------------

@pytest.fixture
def controller_opf_setup(controller_setup, request):
    """
    Parametrizable fixture to test both cases:
    - Interconnection already exists
    - Interconnection does not exist yet
    """
    controller = controller_setup["controller"]
    network_mock = controller_setup["network"]
    input_reader_mock = controller_setup["input_reader"]

    # Mock interconnection ratings
    interco_power_ratings = pd.DataFrame({
        "zone_from": ["IBR", "FR"],
        "zone_to": ["FR", "IBR"],
        "Capacity (MW)": [1000, 1000]
    })

    # Mock interconnection flow data
    interco_powers = pd.DataFrame({
        "Time": [
            Timestamp("2015-01-01 12:00:00"),
            Timestamp("2015-02-01 13:00:00"),
            Timestamp("2015-03-10 14:00:00"),
            Timestamp("2016-01-05 15:00:00"),
            Timestamp("2016-03-15 10:00:00"),
            Timestamp("2015-02-01 13:00:00"),
            Timestamp("2016-01-05 15:00:00"),
        ],
        "zone_from": ["IBR", "IBR", "IBR", "IBR", "IBR", "FR", "FR"],
        "zone_to": ["FR", "FR", "FR", "FR", "FR", "IBR", "IBR"],
        "Power (MW)": [100, 150, 120, 130, 140, 70, 80],
    })

    # Mock zones
    zone_mock_ibr = MagicMock(name="IBR_zone")
    zone_mock_ibr.name = "IBR"
    zone_mock_ibr.interconnections = []

    zone_mock_fr = MagicMock(name="FR_zone")
    zone_mock_fr.name = "FR"
    zone_mock_fr.interconnections = []

    network_mock.zones = {"IBR": zone_mock_ibr, "FR": zone_mock_fr}
    network_mock.run_opf = MagicMock(name="OPF")

    expected_interco_powers = pd.Series(
        [100., 80., 120., 50., 140.],
        index=pd.to_datetime([
            "2015-01-01 12:00:00",  # 100
            "2015-02-01 13:00:00",  # 150 - 70 = 80
            "2015-03-10 14:00:00",  # 120
            "2016-01-05 15:00:00",  # 130 - 80 = 50
            "2016-03-15 10:00:00",  # 140
        ]),
        name="Power (MW)"
    )
    expected_interco_powers.index.name = "Time"

    # Parametrize whether the interconnection already exists
    if getattr(request, 'param', False):
        # Mock interconnection already exists
        interconnection_mock = MagicMock()
        interconnection_mock.zone_from.name = "IBR"
        interconnection_mock.zone_to.name = "FR"
        interconnection_mock.historical_powers = expected_interco_powers
        network_mock.interconnections = [interconnection_mock]
    else:
        # No existing interconnection
        network_mock.interconnections = []

    # Inject required controller attributes
    controller._zones = ["IBR", "FR"]
    controller._powers = input_reader_mock.read_db_powers.return_value
    controller._prices = input_reader_mock.read_db_prices.return_value
    controller._storages = ["hydro pump storage"]
    controller._controllable_sectors = ["hydro pump storage"]
    controller._interco_power_ratings = interco_power_ratings
    controller._interco_powers = interco_powers
    controller._years = [(2015, 2016)]

    fake_price_model = dict()
    input_reader_mock.read_price_models.return_value = {"2015-2016": fake_price_model}

    return {
        "controller": controller,
        "network": network_mock,
        "input_reader": input_reader_mock,
        "zone_mock_ibr": zone_mock_ibr,
        "zone_mock_fr": zone_mock_fr,
        "expected_interco_powers": expected_interco_powers,
    }


@pytest.mark.parametrize('controller_opf_setup', [True], indirect=True)
def test_build_network_model_existing_interco(controller_opf_setup):
    controller = controller_opf_setup["controller"]
    network_mock = controller_opf_setup["network"]
    zone_mock_ibr = controller_opf_setup["zone_mock_ibr"]
    zone_mock_fr = controller_opf_setup["zone_mock_fr"]

    # Run method
    model_built = controller.build_network_model(2015, 2016)

    # Verifications
    assert network_mock.add_zone.call_count == 2
    network_mock.set_price_model.assert_called_once_with(dict())
    network_mock.add_interconnection.assert_not_called()

    zone_mock_ibr.compute_demand.assert_called()
    zone_mock_fr.compute_demand.assert_called()
    assert model_built


@pytest.mark.parametrize('controller_opf_setup', [False], indirect=True)
def test_build_network_model_new_interco(controller_opf_setup):
    controller = controller_opf_setup["controller"]
    network_mock = controller_opf_setup["network"]
    zone_mock_ibr = controller_opf_setup["zone_mock_ibr"]
    zone_mock_fr = controller_opf_setup["zone_mock_fr"]
    expected_interco_powers = controller_opf_setup["expected_interco_powers"]

    # Local list to store created interconnections
    created_interconnections = []

    def add_interconnection_side_effect(zone_from, zone_to, power_rating, interco_powers):
        # Create a simple mock interconnection object
        interco_mock = MagicMock()
        interco_mock.zone_from.name = zone_from.name
        interco_mock.zone_to.name = zone_to.name
        interco_mock.historical_powers = expected_interco_powers
        created_interconnections.append(interco_mock)

        zone_from.interconnections.append(interco_mock)
        zone_to.interconnections.append(interco_mock)

    # Mock add_interconnection to dynamically append to the interconnections list
    network_mock.add_interconnection.side_effect = add_interconnection_side_effect
    network_mock.interconnections = created_interconnections

    # Run method
    model_built = controller.build_network_model(2015, 2016)

    # Verifications
    assert network_mock.add_zone.call_count == 2
    network_mock.set_price_model.assert_called_once_with(dict())

    power_rating = 1000

    # Only one interconnection should have been added
    network_mock.add_interconnection.assert_called_once_with(zone_mock_ibr, zone_mock_fr, power_rating, ANY)
    args, _ = network_mock.add_interconnection.call_args
    interco_powers = args[3]
    assert_series_equal(interco_powers.sort_index(), expected_interco_powers.sort_index())

    expected_net_import_ibr = -expected_interco_powers
    expected_net_import_fr = expected_interco_powers

    assert zone_mock_ibr.compute_demand.called
    ibr_call_args = zone_mock_ibr.compute_demand.call_args[0][0]
    assert_series_equal(ibr_call_args.sort_index(), expected_net_import_ibr.sort_index())

    assert zone_mock_fr.compute_demand.called
    fr_call_args = zone_mock_fr.compute_demand.call_args[0][0]
    assert_series_equal(fr_call_args.sort_index(), expected_net_import_fr.sort_index())

    assert model_built


@pytest.mark.parametrize('controller_opf_setup', [True], indirect=True)
def test_build_network_model_returns_false_if_PL_and_before_2018(controller_opf_setup):
    controller = controller_opf_setup["controller"]
    zone_mock_PL = MagicMock(name="PL_zone")
    zone_mock_PL.name = 'PL'
    controller._zones.append('PL')

    def get_countries_in_zone_mock(zone_name):
        if zone_name == 'PL':
            return ['PL', 'DE']
        else:
            return []

    input_reader_mock = MagicMock()
    input_reader_mock.get_countries_in_zone.side_effect = get_countries_in_zone_mock
    fake_price_model = dict()
    input_reader_mock.read_price_models.return_value = {"2015-2016": fake_price_model, "2018-2019": fake_price_model}
    controller._input_reader = input_reader_mock

    # Run method that should return False and raise a warning
    with pytest.warns(UserWarning, match="Price data for Poland is incomplete before 2018"):
        model_built_false = controller.build_network_model(2015, 2016)

    # Fake data to test a situation with PL in zones but after 2018
    powers = {
        "IBR": pd.DataFrame({"solar": [200],
                             "hydro pump storage": [-200, ]},
                            index=[Timestamp("2018-01-01 12:00:00")]),
        "FR": pd.DataFrame({"solar": [200],
                            "hydro pump storage": [0]},
                           index=[Timestamp("2018-01-01 12:00:00")]),
        "PL": pd.DataFrame({"solar": [200],
                            "hydro pump storage": [0]},
                           index=[Timestamp("2018-01-01 12:00:00")])
    }
    prices = pd.DataFrame({
        "IBR": [50],
        "FR": [48],
        "PL": [48],
    }, index=[Timestamp("2018-01-01 12:00:00")])

    controller._powers = powers
    controller._prices = prices

    # Run method that should return True
    model_built_true = controller.build_network_model(2018, 2019)

    # Verifications
    assert model_built_false is False
    assert model_built_true is True


def test_run_opfs(controller_opf_setup):
    # Definition of mocks
    controller = controller_opf_setup["controller"]
    controller._network = controller_opf_setup["network"]
    controller._years = [(2015, 2016), (2018, 2019)]

    # model_built = True if (start_year, end_year) == (2018, 2019), False otherwise
    controller.build_network_model = MagicMock(
        side_effect=lambda start_year, end_year: (start_year, end_year) == (2018, 2019))
    controller.export_opfs = MagicMock()

    controller._network.datetime_index = [
        "01/01/2018 12:00:00",
        "01/02/2018 12:00:00",
        "01/03/2018 12:00:00"
    ]

    # Execution of the method to be tested
    controller.run_opfs()

    # Vérifications
    controller.build_network_model.assert_has_calls([
        call(2015, 2016),
        call(2018, 2019)
    ])

    # Checking calls to run_opf
    controller._network.run_opf.assert_any_call("01/01/2018 12:00:00")
    controller._network.run_opf.assert_any_call("01/02/2018 12:00:00")
    controller._network.run_opf.assert_any_call("01/03/2018 12:00:00")
    assert controller._network.run_opf.call_count == 3

    # Checking only one call to export_opfs (for 2018-2019)
    controller.export_opfs.assert_called_once_with()


@pytest.mark.parametrize("controller_opf_setup", [False], indirect=True)
def test_export_opfs(controller_opf_setup):
    controller = controller_opf_setup["controller"]
    controller._network = controller_opf_setup["network"]

    # fake work_dir
    fake_work_dir = Path("fake/work/dir")
    controller._work_dir = fake_work_dir

    # Mock datetime_index
    datetime_index = pd.to_datetime([
        "2015-12-28 12:00:00",
        "2015-12-29 12:00:00",
        "2015-12-30 12:00:00",
        "2016-01-01 12:00:00",
        "2016-01-02 12:00:00",
        "2016-01-03 12:00:00",
    ])
    controller._network.datetime_index = datetime_index

    # Mock zones and sectors
    zone_mock_ibr = controller_opf_setup["zone_mock_ibr"]
    sector_mock = MagicMock()
    sector_mock.name = "sector_ibr"
    sector_mock.simulated_powers = pd.Series([10, 20, 30, 40, 50, 60], index=datetime_index)
    zone_mock_ibr.sectors = [sector_mock]
    controller._network.zones = {"IBR": zone_mock_ibr}

    with patch('pathlib.Path.exists', return_value=True), \
            patch('pathlib.Path.mkdir'), \
            patch('pandas.ExcelWriter') as excel_writer_mock, \
            patch('pandas.DataFrame.to_excel', autospec=True) as to_excel_mock:
        controller.export_opfs()

    # Checks that ExcelWriter has been called up with the correct file
    expected_folder = fake_work_dir / f"{SIMULATED_POWERS_DIRECTORY_ROOT}_2015-2016"
    expected_file = expected_folder / f"{SIMULATED_POWERS_FILE_ROOT}_IBR.xlsx"

    excel_writer_mock.assert_called_once_with(expected_file)

    to_excel_mock.assert_called_once_with(ANY, ANY, sheet_name="2015-2016", index=False)

    # get the dataframe
    written_df = to_excel_mock.call_args[0][0]

    # Compare the complete DataFrame
    expected_df = pd.DataFrame({
        "Start time": datetime_index,
        "sector_ibr_MW": [10, 20, 30, 40, 50, 60],
    }, index=datetime_index)

    pd.testing.assert_frame_equal(written_df, expected_df)
