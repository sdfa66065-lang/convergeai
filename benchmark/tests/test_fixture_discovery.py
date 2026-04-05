from __future__ import annotations

from benchmark.config import BenchmarkConfig
from benchmark.fixtures.registry import FixtureRegistry

EXPECTED_FIXTURES = frozenset(
    {
        "01_telemetry_drop",
        "02_js_auth_request_object",
        "03_js_logic_abc_merge",
        "04_js_config_retry_limit",
        "05_js_database_ssl_nested",
        "06_js_api_axios_tracker",
        "07_js_index_imports_merge",
        "08_js_features_array_merge",
        "09_js_network_proxy_refactor",
        "10_js_cross_file_calculate",
        "11_js_cherrypick_server_port",
    }
)


def test_discovers_all_fixtures():
    c = BenchmarkConfig.from_defaults()
    names = {f.name for f in FixtureRegistry.discover(c.fixtures_dir)}
    missing = EXPECTED_FIXTURES - names
    assert not missing, f"Missing fixtures: {missing}"


def test_cross_file_fixture_skips_git_conflict_verify():
    c = BenchmarkConfig.from_defaults()
    fx = next(
        f
        for f in FixtureRegistry.discover(c.fixtures_dir)
        if f.name == "10_js_cross_file_calculate"
    )
    assert fx.verify_git_conflicts is False
