"""Fixed-timestep accumulator for the game loop."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FixedTimestep:
    step: float = 1.0 / 60.0
    max_steps: int = 5
    max_frame_time: float = 0.25
    accumulator: float = field(default=0.0)

    def advance(self, frame_time: float) -> int:
        """Consume a frame delta and return how many fixed updates to run."""
        frame_time = max(0.0, min(float(frame_time), self.max_frame_time))
        self.accumulator += frame_time
        steps = 0
        while self.accumulator >= self.step and steps < self.max_steps:
            self.accumulator -= self.step
            steps += 1
        if steps >= self.max_steps:
            # Do not build an ever-growing backlog after a slow frame.
            self.accumulator = min(self.accumulator, self.step)
        return steps
