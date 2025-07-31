from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pandas as pd
import pytest
from pandas import Timestamp

from src.interconnection import ExteriorInterconnection, Interconnection, OUT_ZONE_NAME
from src.zone import Zone
from src.network import Network, SECTORS_SIMULATION_ERRORS_DIR, LINES_SIMULATION_ERRORS_DIR


@pytest.fixture(scope="function")
def network_setup():
    # --- Timestamps ---
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

    # --- Data ---
    historical_prices = pd.Series([50, 55, 53, 48, 60, 58, 62, 64, 59], index=timestamps)
    sectors_historical_powers = pd.DataFrame({
        "solar": [100, 150, 200, 250, 180, 300, 270, 220, 190],
        "hydro pump storage": [-50, -60, 40, -20, 60, -70, 80, -10, 30],
    }, index=timestamps)

    # --- Patch Zone ---
    zone_cls = patch("src.network.Zone").start()
    zone = MagicMock(name="zone_mock")
    zone.name = "FR"
    zone_cls.return_value = zone

    yield {
        "historical_prices": historical_prices,
        "sectors_historical_powers": sectors_historical_powers,
        "storages": ["hydro pump storage"],
        "controllable_sectors": ["hydro pump storage"],
        "zone_cls": zone_cls,
        "zone": zone,
    }

    patch.stopall()


def make_sector(name, price_model, is_load):
    mock = MagicMock()
    mock.name = name
    mock.price_model = price_model
    mock.is_load = is_load
    return mock


def test_add_zone(network_setup):
    setup = network_setup
    network = Network(opf_mode=False)

    # Add zone
    network.add_zone(zone_name="FR",
                     sectors_historical_powers=setup["sectors_historical_powers"],
                     storages=setup["storages"],
                     controllable_sectors=setup["controllable_sectors"],
                     historical_prices=setup["historical_prices"])

    # Check that Zone has been created with the correct parameters
    setup["zone_cls"].assert_called_once_with("FR", setup["historical_prices"])

    # Check add_sector et add_storage calls
    setup["zone"].add_sector.assert_called_once_with("solar", setup["sectors_historical_powers"]["solar"],
                                                     False)
    setup["zone"].add_storage.assert_called_once_with("hydro pump storage",
                                                      setup["sectors_historical_powers"]["hydro pump storage"],
                                                      True,
                                                      opf_mode=False)

    # Check that zone has been added to networks.zone
    assert setup["zone"] in network._zones.values()
    pd.testing.assert_index_equal(network._datetime_index, setup["sectors_historical_powers"].index)


def test_add_zone_updates_datetime_index(network_setup):
    setup = network_setup
    network = Network(opf_mode=True)

    timestamps = pd.DatetimeIndex([
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("05/02/2015  13:00:00"),
        Timestamp("10/03/2015  14:00:00"),
        Timestamp("15/04/2015  09:00:00"),
        Timestamp("20/05/2015  16:00:00"),
        Timestamp("25/06/2015  08:00:00"),
        Timestamp("30/07/2015  19:00:00"),
        Timestamp("04/09/2015  11:00:00"),
        Timestamp("10/11/2015  22:00:00"),
    ])

    network._datetime_index = timestamps

    # --- Data ---
    historical_prices = pd.Series([50, None, None, 48, None, None, None, None, None], index=timestamps)
    sectors_historical_powers = pd.DataFrame({
        "solar": [100, 150, 200, 250, 180, 300, 270, 220, 190],
        "hydro pump storage": [-50, -60, 40, -20, 60, -70, 80, -10, 30],
    }, index=timestamps)

    network.add_zone(zone_name="FR", sectors_historical_powers=sectors_historical_powers,
                     storages=setup["storages"],
                     controllable_sectors=setup["controllable_sectors"],
                     historical_prices=historical_prices)

    # Check that Zone has been created with the correct parameters
    setup["zone_cls"].assert_called_once_with("FR", historical_prices)

    # Check add_sector et add_storage calls
    setup["zone"].add_sector.assert_called_once_with("solar", sectors_historical_powers["solar"],
                                                     False)
    setup["zone"].add_storage.assert_called_once_with("hydro pump storage",
                                                      sectors_historical_powers["hydro pump storage"],
                                                      True,
                                                      opf_mode=True)

    # Check that zone has been added to networks.zone
    assert setup["zone"] in network._zones.values()

    expected_index = pd.DatetimeIndex([
        Timestamp("01/01/2015  12:00:00"),
        Timestamp("15/04/2015  09:00:00"),
    ])
    pd.testing.assert_index_equal(network._datetime_index, expected_index)


def test_build_price_models(network_setup):
    network = Network(opf_mode=False)
    zone = network_setup["zone"]

    network._zones[zone.name] = zone

    # Calls build_price_models
    network.build_price_models((0, 100, 0, 100, 10))

    # Check the call of build_price_model of zone
    zone.build_price_model.assert_called_once_with((0, 100, 0, 100, 10))


def test_build_price_models_raises_when_no_zones():
    network = Network(opf_mode=False)
    with pytest.raises(ValueError, match="No zones available to build price models."):
        network.build_price_models((0, 100, 0, 100, 10))


def test_set_price_model(network_setup):
    # Network object creation
    network = Network(opf_mode=True)
    network._zones = {"FR": network_setup["zone"]}

    # Mock price models to set
    price_models = {
        "FR": {
            "solar": [None, None, 10, 40],
            "hydro pump storage": [0, 20, 30, 70]
        }
    }

    # Call the tested method
    network.set_price_model(price_models)

    # Check that the zone's set_price_model has been called with the correct parameters
    network_setup["zone"].set_price_model.assert_called_once_with(price_models["FR"])


def test_run_opf_makes_expected_calls():
    zone_1 = MagicMock(spec=Zone)
    zone_2 = MagicMock(spec=Zone)
    zone_3 = MagicMock(spec=Zone)

    interconnection_1 = MagicMock(spec=Interconnection)
    interconnection_1.optimise_export.side_effect = [-1, -.1, 0]
    interconnection_1.zone_from = zone_1
    interconnection_1.zone_to = zone_2

    interconnection_2 = MagicMock(spec=Interconnection)
    interconnection_2.optimise_export.side_effect = [0, 0, 0]
    interconnection_2.zone_from = zone_2
    interconnection_2.zone_to = zone_3

    network = Network(opf_mode=True)
    network._zones = {"1": zone_1, "2": zone_2, "3": zone_3}
    network._interconnections = [interconnection_1, interconnection_2]
    fake_timestep = pd.Timestamp("2019-01-01 00:00:00")

    with patch.object(network, "initialise_opf") as initialise_opf_mock:
        converged = network.run_opf(timestep=fake_timestep)
    assert converged

    initialise_opf_mock.assert_called_once_with(timestep=fake_timestep)
    for zone in (zone_1, zone_2, zone_3):
        assert zone.market_optimisation.call_count == 2
        zone.market_optimisation.assert_has_calls([call(fake_timestep), call(fake_timestep)])
        zone.update_storages_energy.assert_called_once()
        zone.store_simulated_power.assert_called_once_with(fake_timestep)

    for interconnection in (interconnection_1, interconnection_2):
        assert interconnection.optimise_export.call_count == 3  # Three iterations of the loop
        interconnection.optimise_export.assert_has_calls([
            call(fake_timestep), call(fake_timestep), call(fake_timestep)
        ])
        interconnection.store_simulated_power.assert_called_once_with(fake_timestep)


def test_initialise_opf_raise_warning_if_non_feasible_initialisation_requires_to_fake_the_exterior_interconnection():
    timestep = pd.Timestamp("2019-01-01 00:00:00")

    # Create network
    ch_zone = Zone("CH", pd.Series())
    fr_zone = Zone("FR", pd.Series())
    out_zone = Zone(OUT_ZONE_NAME, pd.Series())

    ch_fr_interconnection = Interconnection(fr_zone, ch_zone, power_rating=100,
                                            historical_power_flows=pd.Series(10, index=[timestep]))
    ch_outside_interconnection = ExteriorInterconnection(ch_zone, out_zone,
                                                         historical_power_flows=pd.Series(20, index=[timestep]))
    fr_outside_interconnection = ExteriorInterconnection(fr_zone, out_zone,
                                                         historical_power_flows=pd.Series(0, index=[timestep]))

    ch_zone._interconnections = [ch_fr_interconnection, ch_outside_interconnection]
    fr_zone._interconnections = [ch_fr_interconnection, fr_outside_interconnection]

    network = Network(opf_mode=True)
    network._zones = {'CH': ch_zone, 'FR': fr_zone}
    network._interconnections = [ch_fr_interconnection, ch_outside_interconnection, fr_outside_interconnection]

    # Fake feasible export per zone
    ch_feasible_export = (-15, 0)
    fr_feasible_export = (-10, 10)

    with patch.object(Zone, "reset_powers"), patch.object(Zone, "update_storages_availability"), \
            patch.object(Zone, "feasible_export_range", side_effect=[ch_feasible_export, fr_feasible_export]), \
            patch("warnings.warn") as warning_mock:
        network.initialise_opf(timestep)

    # Check warning message
    warning_mock.assert_called_with(
        f"At timestep {timestep}, zone CH export constraints could not be satisfied. "
        f"Interconnection with the outside zone is modified by -10, therefore "
        "simulation results cannot be compared with historical data", stacklevel=2
    )


def test_initialise_opf_raise_warning_if_non_feasible_initialisation_requires_to_fake_the_exterior_interconnection_2():
    timestep = pd.Timestamp("2019-01-01 00:00:00")

    # Create network
    ch_zone = Zone("CH", pd.Series())
    fr_zone = Zone("FR", pd.Series())
    out_zone = Zone(OUT_ZONE_NAME, pd.Series())

    ch_fr_interconnection = Interconnection(fr_zone, ch_zone, power_rating=100,
                                            historical_power_flows=pd.Series(10, index=[timestep]))
    ch_outside_interconnection = ExteriorInterconnection(ch_zone, out_zone,
                                                         historical_power_flows=pd.Series(20, index=[timestep]))
    fr_outside_interconnection = ExteriorInterconnection(fr_zone, out_zone,
                                                         historical_power_flows=pd.Series(0, index=[timestep]))

    ch_zone._interconnections = [ch_fr_interconnection, ch_outside_interconnection]
    fr_zone._interconnections = [ch_fr_interconnection, fr_outside_interconnection]

    network = Network(opf_mode=True)
    network._zones = {'CH': ch_zone, 'FR': fr_zone}
    network._interconnections = [ch_fr_interconnection, ch_outside_interconnection, fr_outside_interconnection]

    # Fake feasible export per zone
    ch_feasible_export = (-10, 10)
    fr_feasible_export = (-10, 5)

    with patch.object(Zone, "reset_powers"), patch.object(Zone, "update_storages_availability"), \
            patch.object(Zone, "feasible_export_range", side_effect=[ch_feasible_export, fr_feasible_export]), \
            patch("warnings.warn") as warning_mock:
        network.initialise_opf(timestep)

    # Check warning message
    warning_mock.assert_called_with(
        f"At timestep {timestep}, zone CH export constraints could not be satisfied. "
        f"Interconnection with the outside zone is modified by -5, therefore "
        "simulation results cannot be compared with historical data", stacklevel=2
    )


def test_compare_power_series(network_setup):
    # --- Zone mock ---
    zone = network_setup["zone"]
    zone.compare_power_series.return_value = [
        {"zone": "FR", "sector": "solar", "error": 0.15},
        {"zone": "FR", "sector": "hydro pump storage", "error": 0.21},
    ]
    zones = {"FR": zone}

    # --- Interconnection mock ---
    interconnection = MagicMock(name="interconnection_mock")
    interconnection.compare_power_series.return_value = {"line": "FR-ES", "error": 0.07}
    interconnections = [interconnection]

    network = Network(opf_mode=True)
    network._zones = zones
    network._interconnections = interconnections

    fake_path = Path("fake_path")
    fake_dict = {"key": "value"}
    fake_list = [fake_dict]

    written_dfs = []

    def patch_to_excel(self, *args, **kwargs):
        written_dfs.append(self)

    with (
        patch("pandas.DataFrame.to_excel", autospec=True, side_effect=patch_to_excel) as mock_to_excel,
        patch("pandas.ExcelWriter") as mock_writer,
        patch.object(zone, "compare_power_series", return_value=fake_list) as mock_zone_check,
        patch.object(interconnection, "compare_power_series", return_value=fake_dict) as mock_line_check
    ):
        network.compare_power_series(fake_path)

    mock_zone_check.assert_called_once_with(fake_path / SECTORS_SIMULATION_ERRORS_DIR)
    mock_line_check.assert_called_once_with(fake_path / LINES_SIMULATION_ERRORS_DIR)

    mock_writer.assert_called_once()
    assert mock_to_excel.call_count == 2
    assert len(written_dfs) == 2

    expected_df_sectors = pd.DataFrame([{"key": "value"}])
    expected_df_lines = pd.DataFrame([{"key": "value"}])

    pd.testing.assert_frame_equal(written_dfs[0], expected_df_sectors)
    pd.testing.assert_frame_equal(written_dfs[1], expected_df_lines)