# ADR-0004: YAML Scenarios with Strict Validation

- **Status:** Accepted
- **Context:** Scenarios are deeply nested, human-authored configuration and must be safe, portable, and reproducible.
- **Decision:** Author scenarios in YAML 1.2, disable executable tags, reject unknown fields, and validate references through a versioned typed schema. Persist a normalized JSON representation with every run. Secrets are referenced by environment-variable name and never embedded.
- **Consequences:** YAML stays readable while normalized JSON gives stable storage and comparison. Schema migrations will be required when incompatible versions are introduced.
