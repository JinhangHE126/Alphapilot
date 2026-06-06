from __future__ import annotations

import os
from typing import Optional

from tools.providers.base import DataProvider

_DEFAULT_ENABLED = "yfinance,sec_edgar"
_DEFAULT_PRIORITY = "sec_edgar:100,yfinance:40"
_COLLECTOR_TIMEOUT = 15


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}
        self._cooldown: dict[str, float] = {}
        self._failure_threshold: int = 3
        self._cooldown_seconds: float = 300.0

    def register(self, provider: DataProvider) -> None:
        enabled_str = os.getenv("ENABLED_DATA_PROVIDERS", _DEFAULT_ENABLED)
        enabled_names = {n.strip() for n in enabled_str.split(",") if n.strip()}

        if enabled_names and provider.name not in enabled_names:
            provider.enabled = False

        priority_str = os.getenv("PROVIDER_PRIORITY", _DEFAULT_PRIORITY)
        for entry in priority_str.split(","):
            entry = entry.strip()
            if ":" in entry:
                name, prio = entry.split(":", 1)
                if name.strip() == provider.name:
                    try:
                        provider.priority = int(prio.strip())
                    except ValueError:
                        pass

        self._providers[provider.name] = provider

    def get_enabled(self) -> list[DataProvider]:
        import time

        now = time.time()
        enabled = []
        for p in self._providers.values():
            if not p.enabled:
                continue
            if p.name in self._cooldown:
                if now - self._cooldown[p.name] < self._cooldown_seconds:
                    continue
                del self._cooldown[p.name]
            if p.failure_count >= self._failure_threshold:
                self._cooldown[p.name] = now
                print(f"   ⚠️ Provider {p.name} entered cooldown ({self._cooldown_seconds}s)")
                continue
            enabled.append(p)
        enabled.sort(key=lambda p: p.priority, reverse=True)
        return enabled

    def record_result(self, provider_name: str, success: bool) -> None:
        p = self._providers.get(provider_name)
        if p is None:
            return
        if success:
            p.record_success()
        else:
            p.record_failure()


_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _init_defaults(_registry)
    return _registry


def _init_defaults(registry: ProviderRegistry) -> None:
    from tools.providers.yfinance_provider import YFinanceProvider
    from tools.providers.sec_edgar_provider import SecEdgarProvider

    registry.register(YFinanceProvider())
    registry.register(SecEdgarProvider())

    try:
        from tools.providers.alpha_vantage_provider import AlphaVantageProvider
        registry.register(AlphaVantageProvider())
    except Exception:
        pass


__all__ = ["ProviderRegistry", "get_registry"]