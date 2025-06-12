from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest
from pandas import Timestamp

from src.controller_new import Controller


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
        prices_init
    )
    input_reader_mock.work_dir = Path("fake/work_dir")

    # Patch InputReader
    input_reader_patch = patch("src.controller_new.InputReader", return_value=input_reader_mock).start()

    # Patch Network
    network_mock = MagicMock()
    patch("src.controller_new.Network", return_value=network_mock).start()

    # Patch mkdir
    patch("pathlib.Path.mkdir").start()

    # Patch pd.ExcelWriter
    excel_writer_patch = patch("pandas.ExcelWriter").start()

    controller = Controller(work_dir=Path("fake/work_dir"), db_dir=Path("fake/db_dir"))

    yield {
        "controller": controller,
        "input_reader": input_reader_mock,
        "network": network_mock,
        "excel_writer_patch": excel_writer_patch,
        "input_reader_patch": input_reader_patch
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

        expected_zone_calls = [
            call(zone_name="IBR", sectors_historical_powers=expected_powers["2015-2015-IBR"],
                 storages=["hydro pump storage"], historical_prices=expected_prices["2015-2015-IBR"]),
            call(zone_name="FR", sectors_historical_powers=expected_powers["2015-2015-FR"],
                 storages=["hydro pump storage"], historical_prices=expected_prices["2015-2015-FR"]),
            call(zone_name="IBR", sectors_historical_powers=expected_powers["2016-2016-IBR"],
                 storages=["hydro pump storage"], historical_prices=expected_prices["2016-2016-IBR"]),
            call(zone_name="FR", sectors_historical_powers=expected_powers["2016-2016-FR"],
                 storages=["hydro pump storage"], historical_prices=expected_prices["2016-2016-FR"])
        ]

        actual_calls = network.add_zone.call_args_list
        assert len(actual_calls) == len(expected_zone_calls)

        for _, expected in enumerate(expected_zone_calls):
            for actual in actual_calls:
                try:
                    assert expected.kwargs["zone_name"] == actual.kwargs["zone_name"]
                    assert expected.kwargs["storages"] == actual.kwargs["storages"]
                    pd.testing.assert_frame_equal(
                        expected.kwargs["sectors_historical_powers"],
                        actual.kwargs["sectors_historical_powers"]
                    )
                    pd.testing.assert_series_equal(
                        expected.kwargs["historical_prices"],
                        actual.kwargs["historical_prices"]
                    )
                    break
                except AssertionError:
                    continue
            else:
                raise AssertionError(f"Expected call not found : {expected}")

        network.build_price_models.assert_has_calls([
            call(controller.prices_init["2015-2015"]),
            call(controller.prices_init["2016-2016"]),
        ], any_order=True)

        export_patch.assert_has_calls([
            call(2015, 2015, True),
            call(2016, 2016, False),
        ])


def test_export_price_models(controller_setup):
    controller = controller_setup["controller"]
    network = controller_setup["network"]

    # Create two zones with mocked sectors
    # Zone IBR
    zone_mock_IBR = MagicMock()
    zone_mock_IBR.name = "IBR"

    load_sector_IBR = MagicMock()
    load_sector_IBR.name = "hydro pump storage"
    load_sector_IBR.is_load = True
    load_sector_IBR.price_model = (0, 10)  # consumption

    gen_sector_IBR = MagicMock()
    gen_sector_IBR.name = "hydro pump storage"
    gen_sector_IBR.is_load = False
    gen_sector_IBR.price_model = (60, 100)  # production

    solar_sector_IBR = MagicMock()
    solar_sector_IBR.name = "solar"
    solar_sector_IBR.is_load = False
    solar_sector_IBR.price_model = (20, 200)

    zone_mock_IBR.sectors = [load_sector_IBR, gen_sector_IBR, solar_sector_IBR]

    # Zone FR
    zone_mock_FR = MagicMock()
    zone_mock_FR.name = "FR"

    load_sector_FR = MagicMock()
    load_sector_FR.name = "hydro pump storage"
    load_sector_FR.is_load = True
    load_sector_FR.price_model = (0, 20)

    gen_sector_FR = MagicMock()
    gen_sector_FR.name = "hydro pump storage"
    gen_sector_FR.is_load = False
    gen_sector_FR.price_model = (80, 100)

    solar_sector_FR = MagicMock()
    solar_sector_FR.name = "solar"
    solar_sector_FR.is_load = False
    solar_sector_FR.price_model = (10, 100)

    zone_mock_FR.sectors = [load_sector_FR, gen_sector_FR, solar_sector_FR]

    network.zones = [zone_mock_IBR, zone_mock_FR]
    controller.network = network

    written_df = {} # to get the exported df

    def fake_to_excel(self, writer, index=False, sheet_name=None): # to_excel mock
        written_df['df'] = self  # get df
        return None

    with patch("pandas.DataFrame.to_excel", new=fake_to_excel):
        controller.export_price_models(start_year=2015, end_year=2015, create_file=True)
        df = written_df['df']

        # Ensure save_plots and pd.ExcelWriter are called with the good arguments
        zone_mock_IBR.save_plots.assert_called_with(Path("fake/work_dir/results/Plots for years 2015-2015"))
        zone_mock_FR.save_plots.assert_called_with(Path("fake/work_dir/results/Plots for years 2015-2015"))
        controller_setup["excel_writer_patch"].assert_called_with(
            Path("fake/work_dir") / "results" / "Output_prices.xlsx",
            mode='w'
        )

        # check df
        expected_df = pd.DataFrame(
        columns=["Zone", "Price Type", "hydro pump storage", "solar"],
        data=[
            ["IBR", "Cons_max", 0, None],
            ["IBR", "Cons_min", 10, None],
            ["IBR", "Prod_min", 60, 20],
            ["IBR", "Prod_max", 100, 200],
            ["FR", "Cons_max", 0, None],
            ["FR", "Cons_min", 20, None],
            ["FR", "Prod_min", 80, 10],
            ["FR", "Prod_max", 100, 100]
        ]
    )
        pd.testing.assert_frame_equal(df, expected_df)
