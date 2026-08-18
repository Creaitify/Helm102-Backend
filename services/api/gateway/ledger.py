"""Budget ledger with reservations and reconciliation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from services.api.gateway.errors import BudgetExceededError, KillSwitchActiveError
from services.api.gateway.policy import GatewayPolicy


@dataclass(slots=True)
class BudgetReserve:
    """An active spend reservation."""

    reservation_id: str
    amount_microdollars: int
    created_at: datetime


class BudgetLedger:
    """Thread/async safe ledger tracking token spend and micro-dollar limits."""

    def __init__(self, policy: GatewayPolicy) -> None:
        self.policy = policy
        self._spent_today_microdollars: int = 0
        self._active_reservations: dict[str, BudgetReserve] = {}
        self._lock = asyncio.Lock()

    @property
    def spent_today_microdollars(self) -> int:
        return self._spent_today_microdollars

    @property
    def reserved_microdollars(self) -> int:
        return sum(r.amount_microdollars for r in self._active_reservations.values())

    async def reserve(self, reservation_id: str, estimated_microdollars: int) -> BudgetReserve:
        """Attempt to reserve budget for an in-flight request."""
        if self.policy.kill_switch_active:
            raise KillSwitchActiveError("LLM Egress Kill Switch is active. No model calls permitted.")

        async with self._lock:
            total_committed = self._spent_today_microdollars + self.reserved_microdollars + estimated_microdollars
            if total_committed > self.policy.daily_spend_limit_microdollars:
                raise BudgetExceededError(
                    f"Daily budget ceiling exceeded. Spent: {self._spent_today_microdollars}µ$, "
                    f"Reserved: {self.reserved_microdollars}µ$, "
                    f"Requested: {estimated_microdollars}µ$, "
                    f"Limit: {self.policy.daily_spend_limit_microdollars}µ$"
                )

            reserve = BudgetReserve(
                reservation_id=reservation_id,
                amount_microdollars=estimated_microdollars,
                created_at=datetime.now(timezone.utc),
            )
            self._active_reservations[reservation_id] = reserve
            return reserve

    async def reconcile(self, reservation_id: str, actual_microdollars: int) -> None:
        """Reconcile an active reservation with the actual provider cost."""
        async with self._lock:
            if reservation_id in self._active_reservations:
                del self._active_reservations[reservation_id]
            self._spent_today_microdollars += actual_microdollars

    async def release(self, reservation_id: str) -> None:
        """Release an unused reservation if a request failed before completion."""
        async with self._lock:
            if reservation_id in self._active_reservations:
                del self._active_reservations[reservation_id]

    def reset_daily_spend(self) -> None:
        """Reset daily spend counter (called on daily boundary or in tests)."""
        self._spent_today_microdollars = 0
        self._active_reservations.clear()
