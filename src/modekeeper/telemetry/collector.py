from __future__ import annotations

from modekeeper.telemetry.models import TelemetrySample
from modekeeper.telemetry.sources import TelemetrySource


class TelemetryCollector:
    def __init__(self, source: TelemetrySource) -> None:
        self.source = source

    def collect(self) -> list[TelemetrySample]:
        return list(self.source.read())
