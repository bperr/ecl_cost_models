import pandas as pd

from src.interconnection import Interconnection


def test_update_simulated_powers():
    # fake data
    interconnection = Interconnection('FR', 'ES', 200, pd.Series())
    timestep = pd.Timestamp("2015-01-01 12:00:00")

    interconnection._current_power = 150

    # tested method
    interconnection.update_simulated_powers(timestep)

    # Verifications
    expected_series = pd.Series([150], index=[timestep])

    pd.testing.assert_series_equal(interconnection._simulated_powers, expected_series)

    assert interconnection._current_power == 0
