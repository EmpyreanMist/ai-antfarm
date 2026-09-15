from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from antfarm.adapters.api import create_app

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
