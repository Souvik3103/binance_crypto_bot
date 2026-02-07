from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class KillSwitchState:
    active: bool
    reason: str
    time: datetime


class KillSwitch:
    """
    Global kill switch.
    Once triggered, trading MUST stop.
    """

    def __init__(self):
        self.state: KillSwitchState | None = None

    def trigger(self, reason: str):
        if self.state is None:
            self.state = KillSwitchState(
                active=True,
                reason=reason,
                time=datetime.now(timezone.utc),
            )

    def is_active(self) -> bool:
        return self.state is not None and self.state.active

    def reason(self) -> str | None:
        return self.state.reason if self.state else None