import logging

logger = logging.getLogger(__name__)


class Recognizer:
    def __init__(self, config):
        import ctranslate2
        from faster_whisper import WhisperModel

        supported = ctranslate2.get_supported_compute_types(config.device)
        if config.compute_type not in supported:
            raise ValueError(f"Compute type {config.compute_type!r} is unsupported on {config.device}; supported: {sorted(supported)}")
        self.config = config
        logger.info("Loading model=%s device=%s compute_type=%s", config.model, config.device, config.compute_type)
        self.model = WhisperModel(
            config.model,
            device=config.device,
            compute_type=config.compute_type,
            cpu_threads=config.cpu_threads,
            download_root=config.download_root,
        )

    def transcribe(self, segment):
        import numpy

        audio = numpy.frombuffer(segment.pcm, dtype="<i2").astype(numpy.float32) / 32768
        segments, _info = self.model.transcribe(
            audio,
            language=self.config.language or None,
            beam_size=self.config.beam_size,
            temperature=0,
            condition_on_previous_text=False,
            initial_prompt=self.config.initial_prompt or None,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
            no_speech_threshold=self.config.max_no_speech_probability,
            log_prob_threshold=self.config.min_log_probability,
        )
        accepted = [
            result.text.strip()
            for result in segments
            if result.avg_logprob >= self.config.min_log_probability
            and result.no_speech_prob <= self.config.max_no_speech_probability
        ]
        return " ".join(accepted).strip()
