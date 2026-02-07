# %%
import datetime
import importlib
import sys
import types


def _install_fake_gw2_logs_models():
    """Install a minimal fake 'gw2_logs.models' module with a Player stub."""
    models_mod = types.ModuleType("gw2_logs.models")

    class DummyQS:
        def __init__(self, count=0):
            self._count = count

        def __len__(self):
            return self._count

    class DummyPlayerObjects:
        def filter(self, *args, **kwargs):
            return DummyQS(0)

    class Player:
        objects = DummyPlayerObjects()

    models_mod.Player = Player
    sys.modules["gw2_logs.models"] = models_mod


def test_defaults_from_metadata_basic():
    _install_fake_gw2_logs_models()
    dpslog_factory = importlib.import_module("scripts.model_interactions.dpslog_factory")

    metadata = {
        "encounter": {"duration": 120, "success": True, "numberOfPlayers": 5, "boss": "Test Boss", "isCm": False},
        "permalink": "http://dps.report/1",
        "id": "123",
        "players": {"1": {"display_name": "PlayerOne"}},
    }

    defaults = dpslog_factory.defaults_from_metadata(metadata, log_path=None)

    assert "duration" in defaults
    assert defaults["duration"].total_seconds() == 120
    assert defaults["player_count"] == 5
    assert defaults["boss_name"] == "Test Boss"
    assert defaults["url"] == "http://dps.report/1"
    assert isinstance(defaults["players"], list)


def test_defaults_from_parsedlog_basic():
    _install_fake_gw2_logs_models()
    dpslog_factory = importlib.import_module("scripts.model_interactions.dpslog_factory")

    class DummyParsed:
        json_detailed = {
            "players": [{"account": "gw2_1"}],
            "fightName": "Dummy Boss",
            "isCM": False,
            "isLegendaryCM": False,
            "buffMap": {},
            "success": True,
            "gW2Build": 12345,
        }

        def get_duration(self):
            return datetime.timedelta(seconds=42)

        def get_phasetime_str(self):
            return "0:42"

        def get_final_health_percentage(self):
            return 0.0

    parsed = DummyParsed()
    defaults = dpslog_factory.defaults_from_parsedlog(parsed, log_path=None)

    assert defaults["duration"].total_seconds() == 42
    assert defaults["player_count"] == 1
    assert defaults["boss_name"] == "Dummy Boss"
    assert defaults["players"] == ["gw2_1"]


if __name__ == "__main__":
    test_defaults_from_metadata_basic()
    test_defaults_from_parsedlog_basic()
