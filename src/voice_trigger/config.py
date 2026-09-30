import math
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@dataclass
class InputConfig:
    kind: str = "microphone"
    device: str | int = ""
    url: str = ""
    ffmpeg: str = "ffmpeg"
    input_args: list[str] = field(default_factory=list)
    reconnect_seconds: float = 3.0


@dataclass
class RecognitionConfig:
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "zh"
    download_root: str = "models"
    beam_size: int = 1
    cpu_threads: int = 4
    initial_prompt: str = ""
    min_log_probability: float = -1.0
    max_no_speech_probability: float = 0.6


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    frame_seconds: float = 0.1
    rms_threshold: float = 0.012
    pre_roll_seconds: float = 0.3
    silence_seconds: float = 0.7
    min_speech_seconds: float = 0.2
    max_segment_seconds: float = 8.0
    overlap_seconds: float = 0.5
    queue_size: int = 6


@dataclass
class DetectionConfig:
    keywords: list[str] = field(default_factory=lambda: ["张三"])
    cooldown_seconds: float = 10.0


@dataclass
class OutputConfig:
    events_file: str = "events/triggers.jsonl"
    log_transcripts: bool = False


@dataclass
class Config:
    input: InputConfig
    recognition: RecognitionConfig
    audio: AudioConfig
    detection: DetectionConfig
    output: OutputConfig


def positive(value, label, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} must be {'non-negative' if allow_zero else 'positive'}")


def validate(config):
    if config.input.kind not in {"microphone", "rtsp", "ffmpeg", "file"}:
        raise ValueError("input.kind must be microphone, rtsp, ffmpeg or file")
    if config.input.kind in {"rtsp", "file"} and not config.input.url:
        raise ValueError("input.url is required for rtsp/file input")
    if config.input.kind == "rtsp" and not config.input.url.startswith(("rtsp://", "rtsps://")):
        raise ValueError("RTSP input needs an rtsp:// or rtsps:// URL")
    if not isinstance(config.input.input_args, list) or not all(
        isinstance(argument, str) for argument in config.input.input_args
    ):
        raise ValueError("input.input_args must be an array of strings")
    if config.input.kind == "ffmpeg" and not config.input.input_args:
        raise ValueError("ffmpeg input requires input.input_args")
    positive(config.input.reconnect_seconds, "input.reconnect_seconds")
    if config.recognition.device not in {"cpu", "cuda"}:
        raise ValueError("recognition.device must be cpu or cuda")
    if config.audio.sample_rate != 16000:
        raise ValueError("audio.sample_rate must be 16000 for Whisper")
    for name in ("beam_size", "cpu_threads"):
        value = getattr(config.recognition, name)
        positive(value, f"recognition.{name}")
        if not isinstance(value, int):
            raise ValueError(f"recognition.{name} must be an integer")
    positive(config.audio.queue_size, "audio.queue_size")
    if not isinstance(config.audio.queue_size, int):
        raise ValueError("audio.queue_size must be an integer")
    for name in ("frame_seconds", "silence_seconds", "min_speech_seconds", "max_segment_seconds"):
        positive(getattr(config.audio, name), f"audio.{name}")
    for name in ("pre_roll_seconds", "overlap_seconds", "rms_threshold"):
        positive(getattr(config.audio, name), f"audio.{name}", allow_zero=True)
    if config.audio.rms_threshold > 1:
        raise ValueError("audio.rms_threshold must be between 0 and 1")
    frame_samples = config.audio.sample_rate * config.audio.frame_seconds
    if frame_samples < 1 or abs(frame_samples - round(frame_samples)) > 1e-6:
        raise ValueError("audio.frame_seconds must represent a whole number of samples")
    if config.audio.frame_seconds > min(config.audio.silence_seconds, config.audio.min_speech_seconds):
        raise ValueError("frame duration must not exceed silence/minimum speech duration")
    if config.audio.max_segment_seconds <= max(
        config.audio.overlap_seconds + config.audio.frame_seconds,
        config.audio.pre_roll_seconds + config.audio.min_speech_seconds,
        config.audio.silence_seconds,
    ):
        raise ValueError("max segment duration must exceed overlap, silence and minimum speech")
    positive(config.detection.cooldown_seconds, "detection.cooldown_seconds", allow_zero=True)
    if not isinstance(config.detection.keywords, list) or not config.detection.keywords or not all(
        isinstance(keyword, str) and keyword.strip() for keyword in config.detection.keywords
    ):
        raise ValueError("detection.keywords must be a non-empty array of non-empty strings")
    if not isinstance(config.output.log_transcripts, bool):
        raise ValueError("output.log_transcripts must be a boolean")
    if not math.isfinite(config.recognition.min_log_probability):
        raise ValueError("min_log_probability must be finite")
    if not 0 <= config.recognition.max_no_speech_probability <= 1:
        raise ValueError("max_no_speech_probability must be between 0 and 1")


def load_config(path):
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    sections = {
        "input": InputConfig,
        "recognition": RecognitionConfig,
        "audio": AudioConfig,
        "detection": DetectionConfig,
        "output": OutputConfig,
    }
    unknown = set(raw) - set(sections)
    if unknown:
        raise ValueError(f"Unknown config sections: {', '.join(sorted(unknown))}")
    config = Config(**{name: section(**raw.get(name, {})) for name, section in sections.items()})
    overrides = {
        "VOICE_INPUT_KIND": (config.input, "kind"),
        "VOICE_INPUT_URL": (config.input, "url"),
        "VOICE_DEVICE": (config.recognition, "device"),
        "VOICE_COMPUTE_TYPE": (config.recognition, "compute_type"),
        "VOICE_MODEL": (config.recognition, "model"),
        "VOICE_MODEL_CACHE": (config.recognition, "download_root"),
        "VOICE_EVENTS_FILE": (config.output, "events_file"),
    }
    for environment, (section, name) in overrides.items():
        if environment in os.environ:
            setattr(section, name, os.environ[environment])
    validate(config)
    return config
