"""Receptionist persona: business profile (YAML) + prompt template -> LLM instructions.

Kept free of LiveKit imports so it can be unit-tested quickly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any

import yaml

PROMPT_PATH = Path(__file__).parent / "prompts" / "receptionist.md"
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass
class Persona:
    business: dict[str, Any]
    hours: dict[str, str]
    services: list[dict[str, Any]]
    receptionist: dict[str, Any]
    policies: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Persona:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        for key in ("business", "hours", "services", "receptionist"):
            if key not in data:
                raise ValueError(f"'{key}' section missing in {path}")
        return cls(
            business=data["business"],
            hours=data["hours"],
            services=data["services"],
            receptionist=data["receptionist"],
            policies=data.get("policies", []),
        )

    # ---------- derived values ----------
    @property
    def name(self) -> str:
        return self.receptionist["name"]

    @property
    def greeting(self) -> str:
        return self.receptionist["greeting"].format(
            business_name=self.business["name"], name=self.name
        )

    def _hours_text(self) -> str:
        lines = []
        for day in DAYS:
            value = str(self.hours.get(day, "closed"))
            lines.append(f"- {day.capitalize()}: {value}")
        return "\n".join(lines)

    def _services_text(self) -> str:
        return "\n".join(
            f"- {s['name']} ({s.get('duration_minutes', 30)} minutes)" for s in self.services
        )

    def instructions(self, capabilities: list[str]) -> str:
        template = Template(PROMPT_PATH.read_text(encoding="utf-8"))
        return template.substitute(
            receptionist_name=self.name,
            business_name=self.business["name"],
            business_type=self.business.get("type", "business"),
            address=self.business.get("address", "not provided"),
            phone=self.business.get("phone", "not provided"),
            timezone=self.business.get("timezone", "UTC"),
            hours=self._hours_text(),
            services=self._services_text(),
            policies="\n".join(f"- {p}" for p in self.policies) or "- None",
            capabilities="\n".join(f"- {c}" for c in capabilities),
            escalation=self.receptionist.get(
                "escalation", "Offer to take a message for the team."
            ),
        ).strip()
