import importlib.metadata as m
import modekeeper

def test_version_matches_dist():
    assert modekeeper.__version__ == m.version("modekeeper")
