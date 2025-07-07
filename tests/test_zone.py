from unittest.mock import patch, MagicMock, ANY

import pandas as pd
import pytest
from pandas import Timestamp
from pandas.testing import assert_series_equal

from src.zone import Zone


@pytest.fixture
def zone_test_setup():
    # Timestamps
    timestamps = [
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("05/02/2015  13:00:00"),
        Timestamp("10/03/2015  14:00:00"),
        Timestamp("15/04/2015  09:00:00"),
        Timestamp("20/05/2015  16:00:00"),
        Timestamp("25/06/2015  08:00:00"),
        Timestamp("30/07/2015  19:00:00"),
        Timestamp("04/09/2015  11:00:00"),
        Timestamp("10/11/2015  22:00:00"),
    ]

    # Data for a sector in a zone
    historical_prices = pd.Series(
        [50, 55, 53, 48, 60, 58, 62, 64, 59], index=timestamps
    )
    powers = pd.Series(
        [100, 150, 200, 250, 180, 300, 270, 220, 190], index=timestamps
    )

    # Mocks
    sector_cls = patch("src.zone.Sector").start()
    storage_cls = patch("src.zone.Storage").start()

    sector = MagicMock(name="sector_mock")
    sector.name = "solar"
    sector_cls.return_value = sector

    storage = MagicMock(name="storage_mock")
    storage.load = MagicMock(name="storage_load")
    storage.load.name = "hydro pump storage"
    storage.generator = MagicMock(name="storage_gen")
    storage.generator.name = "hydro pump storage"
    storage_cls.return_value = storage

    # --- Zone ---
    zone = Zone("EU", historical_prices=historical_prices)

    yield {
        "zone": zone,
        "powers": powers,
        "timestamps": timestamps,
        "historical_prices": historical_prices,
        "sector_cls": sector_cls,
        "sector": sector,
        "storage_cls": storage_cls,
        "storage": storage,
    }

    patch.stopall()


def test_add_sector(zone_test_setup):
    zone = zone_test_setup["zone"]  # instance of Zone class
    historical_powers = zone_test_setup["powers"]  # Data
    sector_cls = zone_test_setup["sector_cls"]  # fake Sector class
    sector = zone_test_setup["sector"]  # fake instance of sector_cls

    is_controllable = False
    zone.add_sector("solar", historical_powers, is_controllable=is_controllable)

    # Checks that Sector has been instantiated with the correct arguments
    sector_cls.assert_called_once_with("solar", historical_powers, is_controllable)

    # Check that the object sector has been added to the sectors list
    assert sector in zone.sectors


def test_add_storage(zone_test_setup):
    zone = zone_test_setup["zone"]
    powers = zone_test_setup["powers"]
    storage_cls = zone_test_setup["storage_cls"]
    storage = zone_test_setup["storage"]
    is_controllable = False

    zone.add_storage("hydro pump storage", powers, is_controllable=is_controllable)

    # Checks that Storage has been instantiated with the correct arguments
    storage_cls.assert_called_once_with("hydro pump storage", powers, is_controllable)

    # Check that both load and generator sectors have been added to the sectors list
    # (and that the object storage to the storages list)
    assert storage.load in zone.sectors
    assert storage.generator in zone.sectors
    assert storage in zone._storages


def test_build_price_model(zone_test_setup):
    zone = zone_test_setup["zone"]
    powers = zone_test_setup["powers"]
    sector = zone_test_setup["sector"]
    is_controllable = False

    zone.add_sector("solar", powers, is_controllable)

    zone.build_price_model((10, 100, 0, 100, 20))

    # Checks that the internal sector method has been called
    sector.build_price_model.assert_called_once_with(
        historical_prices=zone._historical_prices,
        prices_init=(10, 100, 0, 100, 20),
        zone_name=zone._name
    )

    assert isinstance(zone._historical_prices, pd.Series)
    assert all(isinstance(idx, pd.Timestamp) for idx in zone._historical_prices.index)


def test_save_plots_calls_plot_result_with_correct_path(zone_test_setup, tmp_path):
    zone = zone_test_setup["zone"]
    sector = zone_test_setup["sector"]
    storage = zone_test_setup["storage"]
    is_controllable = False

    # Add a production sector (non-storage)
    sector.is_storage_load = False
    zone.add_sector("solar", zone_test_setup["powers"],
                    is_controllable=is_controllable)

    # Add a storage --> add 2 sectors (load and generator)
    storage.load.is_storage_load = True  # Storage mock
    storage.generator.is_storage_load = False
    zone.add_storage("hydro pump storage", zone_test_setup["powers"], is_controllable=is_controllable)

    # Method to test
    zone.save_plots(tmp_path)

    expected_calls = [
        {
            "mock": sector,
            "path": tmp_path / "EU-solar-generator.png",
        },
        {
            "mock": storage.load,
            "path": tmp_path / "EU-hydro pump storage-load.png",
        },
        {
            "mock": storage.generator,
            "path": tmp_path / "EU-hydro pump storage-generator.png",
        },
    ]

    for call in expected_calls:
        mock_obj = call["mock"]
        expected_path = call["path"]

        # Check that the method has been called once
        mock_obj.plot_result.assert_called_once_with(
            zone_name="EU",
            path=expected_path,
            historical_prices=ANY
        )

        # Check that historical_prices is well called (values, index, dtype, etc.)
        kwargs = mock_obj.plot_result.call_args.kwargs
        pd.testing.assert_series_equal(kwargs["historical_prices"], zone_test_setup["historical_prices"])


def test_set_price_model(zone_test_setup):
    zone = zone_test_setup["zone"]

    # Creation of two sector mocks: a normal mock and a load mock
    sector = MagicMock(name="sector_mock")
    sector.name = "solar"
    sector.is_storage_load = False

    storage_sector = MagicMock(name="storage_sector_mock")
    storage_sector.name = "hydro pump storage"
    storage_sector.is_storage_load = True

    # These two sectors are injected into the zone
    zone._sectors = [sector, storage_sector]

    # Simulated pricing model
    price_models = {
        "solar": [None, None, 10, 40],  # cons_full, cons_none, prod_none, prod_full
        "hydro pump storage": [0, 20, 30, 70]
    }

    # Calling the method
    zone.set_price_model(price_models)

    # Check that calls are correct
    sector.set_price_model.assert_called_once_with((10, 40))  # prod_none, prod_full
    storage_sector.set_price_model.assert_called_once_with((20, 0))  # cons_none, cons_full


def test_compute_demand(zone_test_setup):
    zone = zone_test_setup["zone"]

    # Creation of two sector mocks with historical powers
    solar = MagicMock(name="sector1_mock")
    solar.historical_powers = pd.Series([10, 20, None, 30], index=pd.date_range("2015-01-01", periods=4, freq="D"))

    nuclear = MagicMock(name="sector2_mock")
    nuclear.historical_powers = pd.Series([5, 15, 25, 25], index=pd.date_range("2015-01-01", periods=4, freq="D"))

    zone._sectors = [solar, nuclear]

    # Creation of a series of net imports
    net_imports = pd.Series([2, -3, 5, 4], index=pd.date_range("2015-01-01", periods=4, freq="D"))

    # Calling the method
    zone.compute_demand(net_imports)

    # Expected calculation: (solar + nuclear) + net_imports
    expected_demand = pd.Series([17.0, 32.0, 30.0, 59.0], index=pd.date_range("2015-01-01", periods=4, freq="D"))

    # Verification
    assert_series_equal(zone._power_demand, expected_demand)


def test_compute_demand_without_net_imports(zone_test_setup):
    zone = zone_test_setup["zone"]

    solar = MagicMock(name="sector1_mock")
    solar.historical_powers = pd.Series([10, 20, 30], index=pd.date_range("2015-01-01", periods=3, freq="D"))

    nuclear = MagicMock(name="sector2_mock")
    nuclear.historical_powers = pd.Series([5, 15, 25], index=pd.date_range("2015-01-01", periods=3, freq="D"))

    zone._sectors = [solar, nuclear]

    zone.compute_demand(None)

    expected_demand = pd.Series([15, 35, 55], index=pd.date_range("2015-01-01", periods=3, freq="D"))

    assert_series_equal(zone._power_demand, expected_demand)


def test_updated_simulated_powers(zone_test_setup):
    zone = zone_test_setup["zone"]

    # Mock sectors
    solar = MagicMock()
    nuclear = MagicMock()
    zone._sectors = [solar, nuclear]

    # Mock interconnections
    interconnection1 = MagicMock()
    interconnection2 = MagicMock()
    zone._interconnections = [interconnection1, interconnection2]

    # Fake timestep
    timestep = pd.Timestamp("2015-01-01 12:00:00")

    # Act
    zone.update_simulated_powers(timestep)

    # Assert
    # Check that each sector has called update_simulated_powers with the correct timestep
    for sector in zone._sectors:
        sector.update_simulated_powers.assert_called_once_with(timestep)

    # Checks that each interconnection has called update_simulated_powers with the correct timestep
    for interconnection in zone._interconnections:
        interconnection.update_simulated_powers.assert_called_once_with(timestep)
