from __future__ import annotations

import math
import random
from dataclasses import dataclass

from modekeeper.telemetry.models import TelemetrySample


class TelemetrySource:
    def read(self) -> list[TelemetrySample]:
        raise NotImplementedError


@dataclass
class SyntheticSource(TelemetrySource):
    scenario: str
    duration_ms: int
    seed: int = 42
    sample_interval_ms: int = 1000

    def read(self) -> list[TelemetrySample]:
        random.seed(self.seed)
        samples: list[TelemetrySample] = []
        steps = max(1, self.duration_ms // self.sample_interval_ms)
        for i in range(steps):
            t_ms = i * self.sample_interval_ms
            base_loss = 1.0 + 0.05 * math.sin(i / 5.0)
            base_latency = 120.0 + 10.0 * math.sin(i / 7.0)
            base_throughput = 1000.0 + 30.0 * math.cos(i / 6.0)

            loss = base_loss + random.uniform(-0.02, 0.02)
            latency = base_latency + random.uniform(-5.0, 5.0)
            throughput = base_throughput + random.uniform(-20.0, 20.0)

            if self.scenario == "drift":
                loss += (i / steps) * 0.3
            elif self.scenario == "burst" and i > steps * 0.6:
                latency *= 1.8
            elif self.scenario == "straggler":
                pass

            worker_latencies = [latency + random.uniform(-5.0, 5.0) for _ in range(4)]
            if self.scenario == "straggler" and i > steps * 0.4:
                worker_latencies[-1] *= 2.2

            samples.append(
                TelemetrySample(
                    timestamp_ms=t_ms,
                    loss=loss,
                    latency_ms=latency,
                    throughput=throughput,
                    worker_latencies_ms=worker_latencies,
                )
            )
        return samples
