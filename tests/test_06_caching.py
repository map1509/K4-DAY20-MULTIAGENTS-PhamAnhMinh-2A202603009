"""Bonus 6c: invalidation, isolation, TTL, bounds, and side-effect bypass."""
import asyncio
import pytest
from agents import DataAgent, CodeAgent
from coordinator import CachingCoordinator


REQUEST = {"task_type": "data_analysis", "parameters": {
    "operation": "analyze_csv", "path": "sales.csv", "column": "revenue"}}


def setup(tmp_path, **kwargs):
    (tmp_path / "sales.csv").write_text("revenue\n100\n150\n250\n", encoding="utf-8")
    return CachingCoordinator(worker_agents=[DataAgent(workspace=tmp_path), CodeAgent(workspace=tmp_path)], **kwargs)


def test_cache_hit_copy_and_file_invalidation(tmp_path):
    coord = setup(tmp_path)
    async def run():
        first = await coord.handle_request(REQUEST)
        assert first["data"]["value"] == 500 and not first["cache"]["hit"]
        first["data"]["value"] = -1
        second = await coord.handle_request(REQUEST)
        assert second["data"]["value"] == 500 and second["cache"]["hit"]
        (tmp_path / "sales.csv").write_text("revenue\n900\n", encoding="utf-8")
        third = await coord.handle_request(REQUEST)
        assert third["data"]["value"] == 900 and not third["cache"]["hit"]
        assert coord.cache_stats == {"hits": 1, "misses": 2, "bypasses": 0}
    asyncio.run(run())


def test_cache_ttl_and_lru_bound(tmp_path, monkeypatch):
    coord = setup(tmp_path, cache_max_entries=1)
    async def run():
        await coord.handle_request(REQUEST)
        expires = next(iter(coord.cache.entries.values()))[0]
        monkeypatch.setattr("coordinator.perf_counter", lambda: expires + 1)
        assert not (await coord.handle_request(REQUEST))["cache"]["hit"]
        other = {"task_type": "data_analysis", "parameters": {**REQUEST["parameters"], "aggregation": "mean"}}
        assert (await coord.handle_request(other))["data"]["value"] == pytest.approx(500 / 3)
        assert len(coord.cache.entries) == 1
        coord.clear_cache()
        assert not coord.cache.entries
    asyncio.run(run())


def test_errors_and_file_writes_are_not_cached(tmp_path):
    coord = setup(tmp_path)
    async def run():
        (tmp_path / "sales.csv").write_text("revenue\ninvalid\n", encoding="utf-8")
        assert (await coord.handle_request(REQUEST))["status"] == "error"
        assert (await coord.handle_request(REQUEST))["status"] == "error"
        assert not coord.cache.entries
        writing = {"task_type": "code_generation", "parameters": {
            "operation": "write_file", "path": "test.py", "code": "print(1)"}}
        assert (await coord.handle_request(writing))["status"] == "success"
        # Repeated write must execute again and fail on the existing file.
        assert (await coord.handle_request(writing))["status"] == "error"
        assert coord.cache_stats["bypasses"] == 2
    asyncio.run(run())


def test_cache_configuration_and_hit_deadline_validation(tmp_path):
    for options in ({"cache_ttl": 0}, {"cache_ttl": float("inf")}, {"cache_max_entries": False}):
        with pytest.raises(ValueError):
            setup(tmp_path, **options)
    coord = setup(tmp_path)
    async def run():
        await coord.handle_request(REQUEST)
        with pytest.raises(ValueError):
            await coord.handle_request(REQUEST, timeout=0)
    asyncio.run(run())
