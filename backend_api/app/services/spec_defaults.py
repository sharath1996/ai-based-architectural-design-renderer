from __future__ import annotations

from pydantic import BaseModel, Field


class Spec(BaseModel):
    key: str = Field(default="", description="Specification key in snake_case when possible.")
    value: str = Field(default="", description="Specification value.")


class Specifications(BaseModel):
    list_spec: list[Spec] = Field(
        default_factory=list,
        description="List of key-value specifications for generation.",
    )

    def to_dict(self) -> dict[str, str]:
        output: dict[str, str] = {}
        for item in self.list_spec:
            key = item.key.strip()
            if not key:
                continue
            output[key] = item.value.strip()
        return output

    def bullet_points(self) -> list[str]:
        return [f"{item.key}: {item.value}" for item in self.list_spec if item.key.strip()]

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "Specifications":
        specs = [Spec(key=str(k), value=str(v)) for k, v in data.items()]
        return cls(list_spec=specs)
