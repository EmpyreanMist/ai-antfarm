import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from antfarm.adapters.api import create_app
from antfarm.custom import CustomSimulationDefinition, load_custom_definition
from antfarm.custom.runtime import compose_custom
from antfarm.domain import RunLimit

EXAMPLES = Path("scenarios/examples")


def _client() -> Iterator[TestClient]:
    with TestClient(create_app(scenario_directory=EXAMPLES)) as client:
        yield client


def _resolve(
    client: TestClient,
    scenario_id: str = "society-manual",
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/scenarios/{scenario_id}/resolve", json=overrides
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    return cast(dict[str, object], data)


def _wait_for_terminal(client: TestClient, run_id: str) -> dict[str, object]:
    for _ in range(100):
        response = client.get(f"/api/v1/runs/{run_id}/state")
        assert response.status_code == 200
        state = cast(dict[str, object], response.json())
        if state["status"] in {"completed", "stopped", "failed"}:
            return state
    raise AssertionError("run did not reach a terminal state")


def test_society_vertical_slice_resolves_runs_streams_and_inspects() -> None:
    for client in _client():
        modes = client.get("/api/v1/modes")
        assert modes.status_code == 200
        society = modes.json()["items"][0]
        assert society["id"] == "society"
        assert "economics" in society["capabilities"]
        assert {item["id"] for item in society["templates"]} >= {
            "live-society-mock",
            "society-manual",
        }

        catalog = client.get("/api/v1/modes/society/scenarios")
        assert catalog.status_code == 200
        ids = {item["id"] for item in catalog.json()["items"]}
        assert {"live-society-mock", "society-manual"}.issubset(ids)

        preview = _resolve(
            client,
            seed=73,
            profiles={"alice": {"economics": {"money": 101}}},
        )
        assert preview["mode"] == "society"
        assert preview["seed"] == 73
        agents = preview["agents"]
        assert isinstance(agents, list)
        assert len(agents) == 2
        alice = next(agent for agent in agents if agent["agent_id"] == "alice")
        assert alice["configuration"]["profile"]["economics"]["money"] == 101

        started = client.post(
            "/api/v1/runs",
            json={"resolution_id": preview["resolution_id"], "mode": "bounded"},
        )
        assert started.status_code == 201, started.text
        run_id = started.json()["run_id"]
        completed = _wait_for_terminal(client, run_id)
        assert completed["status"] == "completed"
        assert completed["tick"] == 2

        with client.websocket_connect(
            f"/api/v1/runs/{run_id}/events/stream?after=0"
        ) as websocket:
            messages: list[dict[str, object]] = []
            while True:
                message = cast(dict[str, object], websocket.receive_json())
                messages.append(message)
                state = message.get("state")
                if message["type"] == "state" and isinstance(state, dict) and (
                    state.get("status") == "completed"
                ):
                    break
        streamed = [message for message in messages if message["type"] == "event"]
        assert streamed
        streamed_events = [
            cast(dict[str, object], message["event"]) for message in streamed
        ]
        sequences = [cast(int, event["sequence"]) for event in streamed_events]
        assert sequences == sorted(sequences)
        assert any(event["kind"] == "action.applied" for event in streamed_events)

        snapshot = client.get(f"/api/v1/runs/{run_id}/snapshot")
        assert snapshot.status_code == 200
        assert snapshot.json()["tick"] == 2
        persisted_agents = client.get(f"/api/v1/runs/{run_id}/agents?limit=1")
        assert persisted_agents.status_code == 200
        assert len(persisted_agents.json()["items"]) == 1
        events = client.get(f"/api/v1/runs/{run_id}/events?limit=2")
        assert events.status_code == 200
        assert len(events.json()["items"]) == 2
        assert events.json()["next_after"] is not None


def test_continuous_run_can_be_stopped_through_http() -> None:
    for client in _client():
        preview = _resolve(client)
        started = client.post(
            "/api/v1/runs",
            json={
                "resolution_id": preview["resolution_id"],
                "mode": "continuous",
                "tick_seconds": 60,
            },
        )
        assert started.status_code == 201
        run_id = started.json()["run_id"]

        stopped = client.post(f"/api/v1/runs/{run_id}/stop")

        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["status"] == "stopped"


def test_api_maps_catalog_and_validation_failures_to_stable_errors() -> None:
    for client in _client():
        missing_mode = client.get("/api/v1/modes/not-a-mode")
        assert missing_mode.status_code == 404
        assert missing_mode.json()["error"]["code"] == "not_found"

        missing = client.post("/api/v1/scenarios/not-a-file/resolve", json={})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"

        invalid = client.post(
            "/api/v1/scenarios/society-manual/resolve",
            json={"active_agents": 99},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_argument"


def test_ollama_preflight_failure_prevents_run_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(_: object) -> None:
        raise ValueError("Ollama is unavailable for this test")

    monkeypatch.setattr("antfarm.adapters.api.app.preflight_ollama", unavailable)
    for client in _client():
        preview = _resolve(client, "live-society-ollama")

        response = client.post(
            "/api/v1/runs",
            json={"resolution_id": preview["resolution_id"]},
        )

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "execution_failed"
        assert "Ollama is unavailable" in response.json()["error"]["message"]


def test_custom_definition_validates_resolves_runs_and_inspects() -> None:
    for client in _client():
        starter = client.get("/api/v1/custom/starter")
        assert starter.status_code == 200
        definition = starter.json()

        validated = client.post("/api/v1/custom/validate", json=definition)
        assert validated.status_code == 200, validated.text
        worker = validated.json()["entities"][0]
        assert worker["public"]["state"] == {
            "completed": 0,
            "skills": ["packing"],
        }
        assert worker["configuration"]["state"]["quota"] == 2

        preview = client.post(
            "/api/v1/custom/resolve",
            json={"definition": definition, "run_id": "web-custom-test"},
        )
        assert preview.status_code == 200, preview.text
        started = client.post(
            "/api/v1/runs",
            json={"resolution_id": preview.json()["resolution_id"]},
        )
        assert started.status_code == 201, started.text
        completed = _wait_for_terminal(client, "web-custom-test")
        assert completed["status"] == "completed"

        entities = client.get("/api/v1/runs/web-custom-test/entities")
        assert entities.status_code == 200
        assert entities.json()["items"][1]["entity_id"] == "worker-b"
        snapshot = client.get("/api/v1/runs/web-custom-test/snapshot")
        assert snapshot.json()["world"]["world"]["orders_remaining"] == 0


def test_web_custom_definition_rejects_unsafe_storage_and_unknown_fields() -> None:
    for client in _client():
        definition = client.get("/api/v1/custom/starter").json()
        definition["unknown"] = True
        invalid = client.post("/api/v1/custom/validate", json=definition)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_argument"

        definition.pop("unknown")
        definition["storage"] = {"kind": "sqlite", "path": "browser.db"}
        unsafe = client.post("/api/v1/custom/validate", json=definition)
        assert unsafe.status_code == 422
        assert unsafe.json()["error"]["code"] == "invalid_argument"


def test_generation_returns_an_editable_proposal_without_starting_a_run() -> None:
    for client in _client():
        generated = client.post(
            "/api/v1/custom/generate",
            json={"description": "Workers process a queue of warehouse orders."},
        )

        assert generated.status_code == 200, generated.text
        assert generated.json()["definition"]["kind"] == "custom"
        assert generated.json()["provenance"]["kind"] == "generated_proposal"
        assert "resolution_id" not in generated.json()


def test_local_models_and_web_agent_builder_resolve_without_yaml() -> None:
    class Inventory:
        runtime = "ollama"

        async def list_installed(self) -> tuple[str, ...]:
            return ("gemma4:e2b", "qwen3.5:0.8b")

    with TestClient(
        create_app(scenario_directory=EXAMPLES, model_inventory=Inventory())
    ) as client:
        inventory = client.get("/api/v1/runtimes/local-models")
        drafts = client.post(
            "/api/v1/scenarios/live-society-ollama/agent-drafts/generate",
            json={"count": 2, "seed": 19, "model": "gemma4:e2b"},
        )
        assert inventory.json() == {
            "runtime": "ollama",
            "connected": True,
            "models": ["gemma4:e2b", "qwen3.5:0.8b"],
            "error": None,
        }
        assert drafts.status_code == 200, drafts.text
        agents = drafts.json()["items"]
        agents[0]["profile"]["identity"]["display_name"] = "Edited Agent"
        preview = client.post(
            "/api/v1/scenarios/live-society-ollama/resolve",
            json={"run_id": "web-built", "agents": agents},
        )

    assert preview.status_code == 200, preview.text
    assert preview.json()["active_agent_count"] == 2
    assert (
        preview.json()["agents"][0]["public"]["identity"]["display_name"]
        == "Edited Agent"
    )


def test_conversation_mode_resolves_editable_context_and_turns() -> None:
    for client in _client():
        modes = client.get("/api/v1/modes").json()["items"]
        conversation_mode = next(item for item in modes if item["id"] == "conversation")
        assert conversation_mode["templates"][0]["id"] == "conversation-ollama"

        response = client.post(
            "/api/v1/scenarios/conversation-ollama/resolve",
            json={
                "conversation": {
                    "topic": "Can rivals cooperate?",
                    "situation": "Both sides need a deal before sunrise.",
                    "turns": 7,
                    "memory_limit": 6,
                }
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ticks"] == 7
        assert body["runtime_overrides"]["conversation"]["topic"] == (
            "Can rivals cooperate?"
        )


def test_local_model_discovery_reports_unavailable_without_leaking_errors() -> None:
    class UnavailableInventory:
        runtime = "ollama"

        async def list_installed(self) -> tuple[str, ...]:
            raise ConnectionError("private endpoint detail")

    with TestClient(
        create_app(
            scenario_directory=EXAMPLES,
            model_inventory=UnavailableInventory(),
        )
    ) as client:
        response = client.get("/api/v1/runtimes/local-models")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert response.json()["models"] == []
    assert "private endpoint detail" not in response.text


def test_completed_runs_can_be_listed_replayed_and_compared() -> None:
    for client in _client():
        for run_id, seed in (("history-a", 41), ("history-b", 42)):
            preview = _resolve(client, run_id=run_id, seed=seed)
            started = client.post(
                "/api/v1/runs",
                json={"resolution_id": preview["resolution_id"]},
            )
            assert started.status_code == 201
            assert _wait_for_terminal(client, run_id)["status"] == "completed"

        history = client.get("/api/v1/runs?limit=1")
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1
        assert history.json()["next_offset"] == 1

        replay = client.get("/api/v1/runs/history-a/replay?limit=1")
        assert replay.status_code == 200, replay.text
        assert replay.json()["final_state_verified"] is True
        assert replay.json()["items"][0]["tick"] == 1
        assert replay.json()["next_offset"] == 1

        comparison = client.get(
            "/api/v1/runs/compare?baseline=history-a&candidate=history-b"
        )
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["compatible"] is True
        assert comparison.json()["baseline_run_id"] == "history-a"


def test_api_discovers_and_replays_configured_sqlite_history(
    tmp_path: Path,
) -> None:
    database = tmp_path / "durable-history.db"
    raw = load_custom_definition(
        EXAMPLES / "custom-warehouse.yaml"
    ).model_dump(mode="json")
    raw["run"]["id"] = "durable-custom"
    raw["storage"] = {"kind": "sqlite", "path": str(database)}
    definition = CustomSimulationDefinition.model_validate(raw)

    async def create_history() -> None:
        simulation = compose_custom(definition)
        await simulation.engine.run(RunLimit(definition.run.ticks))
        await simulation.close()

    asyncio.run(create_history())
    with TestClient(
        create_app(scenario_directory=EXAMPLES, history_database=database)
    ) as client:
        history = client.get("/api/v1/runs")
        replay = client.get("/api/v1/runs/durable-custom/replay")

    assert history.status_code == 200
    assert history.json()["items"][0]["run_id"] == "durable-custom"
    assert replay.status_code == 200, replay.text
    assert replay.json()["final_state_verified"] is True
