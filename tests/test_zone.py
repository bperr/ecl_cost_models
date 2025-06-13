from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from pandas import Timestamp

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

    zone.add_sector("solar", historical_powers)

    # Checks that Sector has been instantiated with the correct arguments
    sector_cls.assert_called_once_with("solar", historical_powers)

    # Check that the object sector has been added to the sectors list
    assert sector in zone.sectors


def test_add_storage(zone_test_setup):
    zone = zone_test_setup["zone"]
    powers = zone_test_setup["powers"]
    storage_cls = zone_test_setup["storage_cls"]
    storage = zone_test_setup["storage"]

    zone.add_storage("hydro pump storage", powers)

    # Checks that Storage has been instantiated with the correct arguments
    storage_cls.assert_called_once_with("hydro pump storage", powers)

    # Check that both load and generator sectors have been added to the sectors list
    # (and that the object storage to the storages list)
    assert storage.load in zone.sectors
    assert storage.generator in zone.sectors
    assert storage in zone.storages


def test_build_price_model(zone_test_setup):
    zone = zone_test_setup["zone"]
    powers = zone_test_setup["powers"]
    sector = zone_test_setup["sector"]

    zone.add_sector("solar", powers)

    zone.build_price_model((10, 100, 0, 100, 20))

    # Checks that the internal sector method has been called
    sector.build_price_model.assert_called_once_with(
        historical_prices=zone.historical_prices,
        prices_init=(10, 100, 0, 100, 20)
    )

    assert isinstance(zone.historical_prices, pd.Series)
    assert all(isinstance(idx, pd.Timestamp) for idx in zone.historical_prices.index)


def test_save_plots_calls_plot_result_with_correct_path(zone_test_setup, tmp_path):
    zone = zone_test_setup["zone"]
    sector = zone_test_setup["sector"]
    storage = zone_test_setup["storage"]

    # Add a production sector (non-storage)
    sector.is_load = False
    zone.add_sector("solar", zone_test_setup["powers"])

    # Add a storage --> add 2 sectors (load and generator)
    storage.load.is_load = True  # Storage mock
    storage.generator.is_load = False
    zone.add_storage("hydro pump storage", zone_test_setup["powers"])

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
        mock_obj.plot_result.assert_called_once_with(
            zone_name="EU",
            historical_prices=zone_test_setup["historical_prices"],
            path=expected_path,
        )
