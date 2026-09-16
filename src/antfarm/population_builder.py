"""Deterministic editable population drafts at the configuration boundary."""

from random import Random

from antfarm.application.contracts import AgentDraftView
from antfarm.config.schema import AgentProfileConfig, ScenarioConfig
from antfarm.domain.json_values import freeze_object

NAMES = (
    "Alex", "Blair", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper",
    "Indigo", "Jordan", "Kai", "Logan", "Morgan", "Noor", "Oakley", "Parker",
    "Quinn", "River", "Sage", "Taylor",
)
QUALITIES = (
    "curious", "careful", "bold", "patient", "skeptical", "generous",
    "competitive", "diplomatic", "pragmatic", "idealistic",
)
GOALS = (
    "Build trust with the group.",
    "Protect personal resources.",
    "Find a fair and durable agreement.",
    "Learn what motivates the others.",
    "Become influential without causing collapse.",
)
BELIEFS = (
    "Cooperation is useful when commitments are credible.",
    "Scarcity reveals what people truly value.",
    "Clear evidence matters more than confidence.",
    "Reciprocity is the basis of stable groups.",
)
VALUES = ("fairness", "autonomy", "loyalty", "prosperity", "truth", "stability")
STYLES = ("warm and concise", "direct", "analytical", "diplomatic", "provocative")
TRAITS = (
    "generosity", "greed", "selfishness", "empathy", "assertiveness",
    "agreeableness", "honesty", "conformity", "patience", "impulsiveness",
    "risk_tolerance", "competitiveness", "envy", "aggression", "trust",
    "ambition", "materialism", "fairness", "forgiveness", "sociability",
)


def scenario_agent_drafts(config: ScenarioConfig) -> tuple[AgentDraftView, ...]:
    drafts: list[AgentDraftView] = []
    for agent in config.expand_agents():
        profile: dict[str, object]
        if agent.profile_ref is not None:
            profile = config.profiles[agent.profile_ref].model_dump(
                mode="json", exclude_none=True
            )
        else:
            description = (
                config.personalities[agent.personality_ref].description
                if agent.personality_ref is not None
                else "An adaptable participant."
            )
            profile = {
                "identity": {"display_name": agent.id.replace("-", " ").title()},
                "personality": {"description": description},
            }
        model = config.models[agent.model_ref].model
        drafts.append(
            AgentDraftView(
                id=agent.id,
                model=model,
                profile=freeze_object(profile),
                cognition_interval=agent.cognition_interval,
            )
        )
    return tuple(drafts)


def generate_agent_drafts(
    *, count: int, seed: int, model: str
) -> tuple[AgentDraftView, ...]:
    if not 1 <= count <= 10:
        raise ValueError("population size must be between 1 and 10")
    rng = Random(seed)
    names = list(NAMES)
    rng.shuffle(names)
    drafts: list[AgentDraftView] = []
    for index in range(count):
        name = names[index]
        qualities = tuple(rng.sample(QUALITIES, 3))
        profile = AgentProfileConfig.model_validate(
            {
                "identity": {
                    "display_name": name,
                    "description": (
                        f"A distinct participant generated with seed {seed}."
                    ),
                },
                "personality": {
                    "description": (
                        f"{qualities[0].title()}, {qualities[1]}, "
                        f"and {qualities[2]}."
                    ),
                    "qualities": qualities,
                },
                "goals": [rng.choice(GOALS)],
                "beliefs": [rng.choice(BELIEFS)],
                "values": rng.sample(VALUES, 2),
                "communication_preferences": {
                    "style": rng.choice(STYLES),
                    "preferences": ["Respond to committed public evidence."],
                },
                "behavioral_traits": {
                    trait: round(rng.random(), 3) for trait in TRAITS
                },
                "economics": {
                    "money": rng.randint(0, 100),
                    "resources": {"food": rng.randint(0, 5)},
                    "recurring_income": rng.randint(0, 10),
                    "occupation": rng.choice(
                        ("worker", "trader", "organizer", "researcher")
                    ),
                },
                "visibility": {
                    "wealth": "public",
                    "possessions": "public",
                    "occupation": "public",
                    "status": "private",
                    "reputation": "public",
                    "relationships": "public",
                    "health": "private",
                    "group_membership": "private",
                },
            }
        )
        drafts.append(
            AgentDraftView(
                id=f"agent-{index + 1}",
                model=model,
                profile=profile.model_dump(mode="json", exclude_none=True),
            )
        )
    return tuple(drafts)
