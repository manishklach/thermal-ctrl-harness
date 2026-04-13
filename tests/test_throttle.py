from unittest.mock import patch, MagicMock
import src.thermal_guard as tg

@patch('subprocess.check_output')
def test_get_hbm_temps(mock_check):
    mock_check.return_value = b"0, 72\n1, 84\n"
    tc = tg.ThermalController(tg.DEFAULT_CONFIG)
    assert tc.get_hbm_temps() == [(0, 72), (1, 84)]

@patch('time.time', return_value=10)
def test_get_hbm_temps_simulated(_mock_time):
    tc = tg.ThermalController(tg.DEFAULT_CONFIG)
    with patch.object(tg, 'SIMULATE', True):
        assert tc.get_hbm_temps() == [(0, 86)]

@patch('requests.post')
def test_set_vllm_batch(mock_post):
    mock_post.return_value.raise_for_status = MagicMock()
    tc = tg.ThermalController(tg.DEFAULT_CONFIG)
    assert tc.set_vllm_batch(16, 0.1) == True
