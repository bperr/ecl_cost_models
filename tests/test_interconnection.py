from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.interconnection import Interconnection


@pytest.fixture
def create_interconnection():
    zone_from = MagicMock()
    zone_from.name = 'FR'
    zone_to = MagicMock()
    zone_to.name = 'ES'
    power_rating = 150
    interconnection = Interconnection(zone_from, zone_to, power_rating, historical_power_flows=pd.Series())
    return interconnection


def test_store_simulated_power(create_interconnection):
    interconnection = create_interconnection
    timestep = pd.Timestamp("2015-01-01 12:00:00")

    interconnection._current_power = 150

    # tested method
    interconnection.store_simulated_power(timestep)

    # Verifications
    expected_series = pd.Series([150], index=[timestep])

    pd.testing.assert_series_equal(interconnection._simulated_powers, expected_series)

    assert interconnection._current_power == 0


@pytest.mark.parametrize(
    "historical, simulated, expected_corr, expected_mae, expected_max_rel, expected_mean_rel",
    [  # test 1 : Same series
        (pd.Series([1, 2, 3, 4, 5]),
         pd.Series([1, 2, 3, 4, 5]),
         1.0, 0.0, 0.0, 0.0),

        # test 2 : Opposite values
        (pd.Series([1, 2, 3, 4, 5]),
         pd.Series([-1, -2, -3, -4, -5]),
         -1.0, 6.0, 2.0, 2.0),

        # test 3 : Constant shift
        (pd.Series([1, 2, 3, 4, 5]),
         pd.Series([2, 3, 4, 5, 6]),
         1.0, 1.0, 1.0, (1 / 1 + 1 / 2 + 1 / 3 + 1 / 4 + 1 / 5) / 5),  # ≈ 0.456

        # test 4 : Noise
        (pd.Series([10, 20, 30, 40, 50]),
         pd.Series([12, 18, 29, 41, 48]),
         np.corrcoef([10, 20, 30, 40, 50], [12, 18, 29, 41, 48])[0, 1],
         np.mean(np.abs(np.array([10, 20, 30, 40, 50]) - np.array([12, 18, 29, 41, 48]))),
         np.max(np.abs(np.array([10, 20, 30, 40, 50]) - np.array([12, 18, 29, 41, 48])) / np.array(
             [10, 20, 30, 40, 50])),
         np.mean(np.abs(np.array([10, 20, 30, 40, 50]) - np.array([12, 18, 29, 41, 48])) / np.array(
             [10, 20, 30, 40, 50]))),
    ]
)
def test_compare_power_series_parametrized(historical, simulated, expected_corr, expected_mae, expected_max_rel,
                                           expected_mean_rel, create_interconnection):
    fake_path = Path("fake_path")
    interconnection = create_interconnection
    interconnection._historical_powers = historical
    interconnection._simulated_powers = simulated

    with patch.object(interconnection, "plot_power_errors", MagicMock()):
        result = interconnection.compare_power_series(fake_path)

    assert result["line"] == 'FR-ES'
    assert result["correlation_coefficient"] == round(float(expected_corr), 3)
    assert result["mean_absolute_error_MW"] == round(float(expected_mae), 3)
    assert result["max_relative_error"] == round(float(expected_max_rel), 3)
    assert result["mean_relative_error"] == round(float(expected_mean_rel), 3)


def test_plot_power_errors(create_interconnection):
    interconnection = create_interconnection
    idx = pd.date_range("2015-01-01", periods=10, freq="H")
    historical_powers = pd.Series(np.linspace(0, 1000, 10), index=idx)

    interconnection._historical_powers = historical_powers
    interconnection._simulated_powers = interconnection.historical_powers * 0.95

    errors_data = {
        "max_relative_error": 0.11,
        "mean_relative_error": 0.07
    }
    fake_path = Path("fake_path")
    expected_filename = "FR-ES_interconnection_comparison.png".replace(" ", "_")
    expected_path = fake_path / expected_filename

    with patch("matplotlib.pyplot.savefig") as mock_savefig, \
            patch("matplotlib.pyplot.close") as mock_close:
        interconnection.plot_power_errors(errors_data, fake_path)

    mock_savefig.assert_called_once_with(expected_path)
    mock_close.assert_called_once()
