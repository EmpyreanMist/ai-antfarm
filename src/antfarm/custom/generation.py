"""Validated application workflow for AI-assisted definition proposals."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from antfarm.application.contracts import ApplicationError, ErrorCode
from antfarm.custom.schema import CustomSimulationDefinition
from antfarm.domain.json_values import JsonObject, freeze_object
from antfarm.ports.generation import CustomDefinitionGenerator

MAX_DESCRIPTION_CHARS = 4_000
MAX_GENERATED_CHARS = 256_000


@dataclass(frozen=True, slots=True)
class GenerateCustomDefinitionCommand:
    description: str


@dataclass(frozen=True, slots=True)
class GeneratedCustomDefinition:
    definition: CustomSimulationDefinition
    provenance: JsonObject


class CustomGenerationService:
    def __init__(self, generator: CustomDefinitionGenerator) -> None:
        self._generator = generator

    async def generate(
        self, command: GenerateCustomDefinitionCommand
    ) -> GeneratedCustomDefinition:
        description = command.description.strip()
        if not description:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT, "simulation description is required"
            )
        if len(description) > MAX_DESCRIPTION_CHARS:
            raise ApplicationError(
                ErrorCode.INVALID_ARGUMENT,
                f"simulation description exceeds {MAX_DESCRIPTION_CHARS} characters",
            )
        try:
            generated = await self._generator.generate(description)
        except Exception as error:
            raise ApplicationError(
                ErrorCode.EXECUTION_FAILED,
                "custom definition generation failed",
                details={"error_type": type(error).__name__},
            ) from error
        if len(generated) > MAX_GENERATED_CHARS:
            raise ApplicationError(
                ErrorCode.INVALID_SCENARIO,
                "generated custom definition exceeds the size limit",
            )
        try:
            raw = json.loads(generated)
            if not isinstance(raw, dict):
                raise TypeError("generated root is not an object")
            definition = CustomSimulationDefinition.model_validate(raw)
        except (json.JSONDecodeError, TypeError, ValidationError) as error:
            raise ApplicationError(
                ErrorCode.INVALID_SCENARIO,
                "generator returned an invalid custom definition",
                details={"error_type": type(error).__name__},
            ) from error
        return GeneratedCustomDefinition(
            definition=definition,
            provenance=freeze_object(
                {
                    "kind": "generated_proposal",
                    "generator": self._generator.kind,
                    "description_length": len(description),
                    "schema_version": definition.schema_version,
                }
            ),
        )

    async def close(self) -> None:
        await self._generator.close()
