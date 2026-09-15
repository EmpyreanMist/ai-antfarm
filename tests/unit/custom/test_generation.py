from pathlib import Path

import pytest

from antfarm.application import ApplicationError, ErrorCode
from antfarm.custom import load_custom_definition
from antfarm.custom.generation import (
    CustomGenerationService,
    GenerateCustomDefinitionCommand,
)

EXAMPLE = Path("scenarios/examples/custom-warehouse.yaml")


class StubGenerator:
    kind = "stub"

    def __init__(self, result: str = "", error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def generate(self, description: str) -> str:
        del description
        if self.error is not None:
            raise self.error
        return self.result

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_generation_returns_only_a_validated_definition_and_provenance() -> None:
    source = load_custom_definition(EXAMPLE)
    service = CustomGenerationService(StubGenerator(source.model_dump_json()))

    generated = await service.generate(
        GenerateCustomDefinitionCommand("A small warehouse simulation")
    )

    assert generated.definition == source
    assert generated.provenance["kind"] == "generated_proposal"
    assert "raw_output" not in generated.provenance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    ["not json", "```json\n{}\n```", "{}"],
)
async def test_generation_rejects_malformed_or_schema_invalid_output(
    result: str,
) -> None:
    service = CustomGenerationService(StubGenerator(result))

    with pytest.raises(ApplicationError) as raised:
        await service.generate(GenerateCustomDefinitionCommand("Build something"))

    assert raised.value.code is ErrorCode.INVALID_SCENARIO
    assert result not in raised.value.message


@pytest.mark.asyncio
async def test_generation_bounds_input_output_and_provider_failures() -> None:
    with pytest.raises(ApplicationError) as input_error:
        await CustomGenerationService(StubGenerator()).generate(
            GenerateCustomDefinitionCommand("x" * 4_001)
        )
    assert input_error.value.code is ErrorCode.INVALID_ARGUMENT

    with pytest.raises(ApplicationError) as output_error:
        await CustomGenerationService(StubGenerator("x" * 256_001)).generate(
            GenerateCustomDefinitionCommand("large")
        )
    assert output_error.value.code is ErrorCode.INVALID_SCENARIO

    with pytest.raises(ApplicationError) as provider_error:
        await CustomGenerationService(
            StubGenerator(error=ConnectionError("secret raw output"))
        ).generate(GenerateCustomDefinitionCommand("failure"))
    assert provider_error.value.code is ErrorCode.EXECUTION_FAILED
    assert "secret raw output" not in provider_error.value.message
