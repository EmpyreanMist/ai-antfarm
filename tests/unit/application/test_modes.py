import pytest

from antfarm.application import ApplicationError, ErrorCode
from antfarm.facade import AntFarmApplication


def test_society_mode_exposes_immutable_capabilities_and_templates() -> None:
    application = AntFarmApplication()

    modes = application.list_modes()

    assert len(modes) == 1
    society = modes[0]
    assert society.id == "society"
    assert "economics" in society.capabilities
    assert "public_speech" in society.capabilities
    assert {template.id for template in society.templates} >= {
        "live-society-mock",
        "society-manual",
    }
    assert society.configuration_hints["runtime_options"] == (
        "seed",
        "active_agents",
        "run_id",
        "model",
        "model_assignments",
        "population",
        "profiles",
        "run_mode",
        "tick_seconds",
    )


def test_unknown_mode_and_template_use_stable_not_found_errors() -> None:
    application = AntFarmApplication()

    with pytest.raises(ApplicationError) as mode_error:
        application.get_mode("missing")
    assert mode_error.value.code is ErrorCode.NOT_FOUND
    assert mode_error.value.details["mode_id"] == "missing"

    with pytest.raises(ApplicationError) as template_error:
        application.mode_template_source("society", "missing")
    assert template_error.value.code is ErrorCode.NOT_FOUND
    assert template_error.value.details["template_id"] == "missing"
