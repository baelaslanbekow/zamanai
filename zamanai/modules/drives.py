from __future__ import annotations

from dataclasses import dataclass

from zamanai.config import Config


@dataclass
class DriveWeights:
    curiosity: float = 0.8
    helpfulness: float = 0.9
    coherence: float = 0.85
    caution: float = 0.7
    growth: float = 0.75


class DrivesSystem:
    """Мотивационные драйвы — влияют на глубину обработки."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.weights = DriveWeights()

    def should_imagine(self, urgency: str, input_length: int) -> bool:
        if not self.config.imagination_enabled:
            return False
        if urgency == "high":
            return input_length > 80
        return input_length > 20 or self.weights.curiosity > 0.7

    def depth_multiplier(self) -> float:
        return (self.weights.curiosity + self.weights.helpfulness) / 2