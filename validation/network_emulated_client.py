import random
import time
from typing import Any

from coppeliasim_zmqremoteapi_client import RemoteAPIClient


class NetworkEmulatedRemoteAPI:
    def __init__(
        self,
        base_latency_ms: float = 50.0,
        jitter_ms: float = 10.0,
        packet_loss_probability: float = 0.02,
        maximum_retries: int = 3,
        seed: int = 42,
    ):
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms
        self.packet_loss_probability = packet_loss_probability
        self.maximum_retries = maximum_retries
        self.rng = random.Random(seed)

        self.commands_sent = 0
        self.commands_dropped = 0
        self.commands_retried = 0
        self.commands_succeeded = 0
        self.round_trip_times_ms = []

        client = RemoteAPIClient()
        self.sim = client.require("sim")

    def _emulate_transmission(self) -> None:
        latency_ms = self.base_latency_ms + self.rng.uniform(
            -self.jitter_ms,
            self.jitter_ms,
        )

        latency_ms = max(0.0, latency_ms)
        time.sleep(latency_ms / 1000.0)

    def call(self, function_name: str, *args: Any) -> Any:
        self.commands_sent += 1

        for attempt in range(self.maximum_retries + 1):
            self._emulate_transmission()

            if self.rng.random() < self.packet_loss_probability:
                self.commands_dropped += 1

                if attempt < self.maximum_retries:
                    self.commands_retried += 1
                    continue

                raise RuntimeError(
                    f"Network-emulated command failed after "
                    f"{self.maximum_retries} retries: {function_name}"
                )

            start_time = time.perf_counter()
            result = getattr(self.sim, function_name)(*args)
            round_trip_ms = (
                time.perf_counter() - start_time
            ) * 1000.0

            self.round_trip_times_ms.append(round_trip_ms)
            self.commands_succeeded += 1

            return result

        raise RuntimeError(
            f"Unreachable network-emulation state: {function_name}"
        )

    def summary(self) -> dict:
        if self.round_trip_times_ms:
            mean_rtt = sum(self.round_trip_times_ms) / len(
                self.round_trip_times_ms
            )

            minimum_rtt = min(self.round_trip_times_ms)
            maximum_rtt = max(self.round_trip_times_ms)
        else:
            mean_rtt = 0.0
            minimum_rtt = 0.0
            maximum_rtt = 0.0

        return {
            "commands_sent": self.commands_sent,
            "commands_succeeded": self.commands_succeeded,
            "commands_dropped": self.commands_dropped,
            "commands_retried": self.commands_retried,
            "mean_round_trip_ms": mean_rtt,
            "minimum_round_trip_ms": minimum_rtt,
            "maximum_round_trip_ms": maximum_rtt,
            "packet_loss_probability": self.packet_loss_probability,
            "base_latency_ms": self.base_latency_ms,
            "jitter_ms": self.jitter_ms,
        }
