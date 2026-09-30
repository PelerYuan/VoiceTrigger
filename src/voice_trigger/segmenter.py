import math
import sys
import time
from array import array
from collections import deque
from dataclasses import dataclass


@dataclass
class AudioSegment:
    pcm: bytes
    captured_at: float
    sample_rate: int = 16000

    @property
    def duration(self):
        return len(self.pcm) / (2 * self.sample_rate)


def pcm_rms(pcm):
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768


class Segmenter:
    def __init__(self, config):
        self.config = config
        self.pre_roll = deque(maxlen=math.ceil(config.pre_roll_seconds / config.frame_seconds))
        self.frames = []
        self.silent_seconds = 0.0
        self.speech_seconds = 0.0
        self.total_bytes = 0

    def push(self, pcm, captured_at=None):
        duration = len(pcm) / (2 * self.config.sample_rate)
        voiced = pcm_rms(pcm) >= self.config.rms_threshold
        entry = (pcm, voiced)
        if not self.frames:
            if not voiced:
                self.pre_roll.append(entry)
                return None
            self.frames = list(self.pre_roll)
            self.total_bytes = sum(len(frame) for frame, _voiced in self.frames)
            self.pre_roll.clear()
        self.frames.append(entry)
        self.total_bytes += len(pcm)
        self.speech_seconds += duration if voiced else 0
        self.silent_seconds = 0 if voiced else self.silent_seconds + duration
        total_seconds = self.total_bytes / (2 * self.config.sample_rate)
        if self.silent_seconds + 1e-9 >= self.config.silence_seconds:
            return self.finish(captured_at)
        if total_seconds + 1e-9 >= self.config.max_segment_seconds:
            segment = self.build(captured_at)
            overlap = math.ceil(self.config.overlap_seconds / self.config.frame_seconds)
            self.frames = self.frames[-overlap:] if overlap else []
            self.total_bytes = sum(len(frame) for frame, _voiced in self.frames)
            self.speech_seconds = sum(len(frame) for frame, voiced in self.frames if voiced) / (2 * self.config.sample_rate)
            self.silent_seconds = 0
            return segment
        return None

    def build(self, captured_at=None):
        if self.speech_seconds + 1e-9 < self.config.min_speech_seconds:
            return None
        return AudioSegment(
            b"".join(frame for frame, _voiced in self.frames),
            time.time() if captured_at is None else captured_at,
            self.config.sample_rate,
        )

    def finish(self, captured_at=None):
        segment = self.build(captured_at)
        self.pre_roll.extend(self.frames)
        self.frames = []
        self.speech_seconds = 0
        self.silent_seconds = 0
        self.total_bytes = 0
        return segment
