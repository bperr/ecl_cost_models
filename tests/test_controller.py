from pathlib import Path
from unittest.mock import MagicMock, call, patch, ANY

import pandas as pd
import pytest
from pandas import Timestamp

from src.controller import Controller
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
    :param sector_specs: List of tuples (name, is_load, price_model)
    :return: MagicMock of zone
    """
    zone = MagicMock(spec=Zone)
    zone.name = name
    sectors = []
    for sector_name, is_load, price_model in sector_specs:
        sector = MagicMock()
        sector.name = sector_name
        sector.is_load = is_load
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

    network.zones = [zone_mock_IBR, zone_mock_FR]
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
