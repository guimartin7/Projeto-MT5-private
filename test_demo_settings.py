import pytest
from demo_settings import DemoSettings

def test_settings_validate_and_roundtrip(tmp_path):
    path = tmp_path / 'settings.json'
    settings = DemoSettings(5, 50, 100, 200); settings.save(path)
    assert DemoSettings.load(path).max_entries == 5

def test_settings_reject_unsafe_values():
    with pytest.raises(ValueError): DemoSettings(max_entries=0).validate()
    with pytest.raises(ValueError): DemoSettings(max_daily_loss=1001).validate()
