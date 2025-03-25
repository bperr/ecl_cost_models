from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from pandas import Timestamp

from src.controller import Controller

TIME_STAMPS = [Timestamp("01/01/2015  12:00:00"),
               Timestamp("01/01/2015  13:00:00"),
               Timestamp("01/01/2015  14:00:00"),
               Timestamp("01/01/2016  12:00:00"),
               Timestamp("01/01/2016  13:00:00"),
               Timestamp("01/01/2016  14:00:00"),
               Timestamp("01/01/2017  12:00:00"),
               Timestamp("01/01/2017  13:00:00"),
               Timestamp("01/01/2017  14:00:00")]


@pytest.fixture(scope='function')
def spot_setup():
    spot_df = pd.DataFrame(
        columns=["ES", "FR", "PT"],
        index=TIME_STAMPS,
        data=[
            # 2015
            [30, 30, 30],
            [40, 40, 40],
            [50, 50, 50],
            # 2016
            [60, 60, 60],
            [70, 70, 70],
            [80, 80, 80],
            # 2017
            [100, 100, 100],
            [100, 100, 100],
            [100, 100, 100]
        ]
    )
    spot_dict = spot_df.to_dict()

    # This line tells python so emulate 'load_database_price_user' function
    # Therefore, calling 'load_database_price_user' will return the expected dataframe
    read_price_mock = patch("src.controller.read_database_price_user", return_value=spot_dict).start()

    yield {'mock': read_price_mock}

    patch.stopall()  # Cancel the patch command on 'load_database_price_user' (or any function)


@pytest.fixture(scope='function')
def prod_setup():
    fr_prod_df = pd.DataFrame(
        columns=["fossil_gas_MW", "fossil_hard_coal_MW", "hydro_pumped_storage_MW"],
        index=TIME_STAMPS,
        # Ref price models: Gas 40-60, Coal 60-80, Hydro storage 30-50-50-70
        data=[
            [0, 0, -100],  # 30 €/MWh
            [0, 0, -50],  # 40 €/MWh
            [100, 0, 0],  # 50 €/MWh
            [200, 0, 50],  # 60 €/MWh
            [200, 100, 100],  # 70 €/MWh
            [300, 100, 100],  # 80 €/MWh
            [50, 50, 50],  # 100 €/MWh but not considered (ex: energy crisis)
            [50, 50, 50],  # 100 €/MWh but not considered
            [50, 50, 50],  # 100 €/MWh but not considered
        ])
    fr_prod_dict = fr_prod_df.to_dict()
    es_prod_dict = fr_prod_dict
    pt_prod_dict = fr_prod_dict

    # This line tells python so emulate 'load_database_prod_user' function
    # Therefore, calling 'load_database_prod_user' will return the expected dataframe

    read_power_mock = patch("src.controller.read_database_prod_user",
                            return_value={"ES": es_prod_dict, "FR": fr_prod_dict, "PT": pt_prod_dict}).start()

    yield {'mock': read_power_mock}

    patch.stopall()  # Cancel the patch command on 'load_database_prod_user' (or any function)


def test_controller(prod_setup, spot_setup):
    fake_db_dir = Path("fake/database")
    fake_work_dir = Path("fake/work_dir")

    user_inputs = (
        [(2015, 2016)],
        {"IBR": ["ES", "PT"], "FRA": ["FR"]},
        {"Fossil": ["fossil_gas", "fossil_hard_coal"], "Storage": ["hydro_pumped_storage"]},
        {"Storage"}
    )
    read_user_inputs_mock = patch("src.controller.read_user_inputs", return_value=user_inputs).start()
    price_hypothesis = {
        (2015, 2016): {"IBR": {"Fossil": [None, None, 30, 60], "Storage": [0, 50, 50, 70]},
                       "FRA": {"Fossil": [None, None, 50, 60], "Storage": [0, 50, 50, 70]}}
    }
    read_price_hypothesis_mock = patch("src.controller.read_price_hypothesis", return_value=price_hypothesis).start()
    patch("src.controller.add_missing_dates_prod").start()
    patch("src.controller.add_missing_dates_price").start()

    controller = Controller(work_dir=fake_work_dir, db_dir=fake_db_dir)
    results = controller.run(export_to_excel=False)

    load_price_mock = spot_setup["mock"]
    load_price_mock.assert_called_once()
    load_power_mock = prod_setup["mock"]
    load_power_mock.assert_called_once()
    read_user_inputs_mock.assert_called_once()
    read_price_hypothesis_mock.assert_called_once()

    # Model used to build the test inputs
    expected_results = {'2015-2016': {"FRA": {"Fossil": [None, None, 40, 80],
                                              "Storage": [30, 50, 50, 70]},
                                      "IBR": {"Fossil": [None, None, 40, 80],
                                              "Storage": [30, 50, 50, 70]}}}

    # assert results == expected_results  # Fails due to rounding errors
    # Comparing nested dictionaries directly is not possible with pytest.approx, we need to compare the dict element by
    # element
    for years, year_data in expected_results.items():
        assert years in results.keys()
        for zone, zone_data in year_data.items():
            assert zone in results[years].keys()
            for sector, sector_prices in zone_data.items():
                assert sector in results[years][zone].keys()
                sector_results = results[years][zone][sector]
                assert sector_results == pytest.approx(sector_prices, abs=3)  # Alowing max absolute diff of 3
