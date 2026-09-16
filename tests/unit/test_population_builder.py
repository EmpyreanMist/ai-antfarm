from antfarm.population_builder import generate_agent_drafts


def test_generated_agent_drafts_are_reproducible_and_editable_profiles() -> None:
    first = generate_agent_drafts(count=3, seed=81, model="local:model")
    second = generate_agent_drafts(count=3, seed=81, model="local:model")
    changed = generate_agent_drafts(count=3, seed=82, model="local:model")

    assert first == second
    assert first != changed
    assert first[0].profile["identity"]
    assert first[0].profile["behavioral_traits"]
    assert first[0].model == "local:model"
