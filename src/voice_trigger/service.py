import json
import logging
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .audio import create_source
from .config import load_config
from .detection import KeywordDetector
from .recognition import Recognizer
from .segmenter import Segmenter

logger = logging.getLogger(__name__)


def enqueue_latest(target, segment):
    try:
        target.put_nowait(segment)
    except queue.Full:
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        target.put_nowait(segment)
        logger.warning("Recognition is behind: dropped oldest audio segment; consider a smaller model")


class CaptureWorker(threading.Thread):
    def __init__(self, config, segments, stop):
        super().__init__(name="audio-capture", daemon=True)
        self.config = config
        self.segments = segments
        self.stop = stop
        self.finished = threading.Event()
        self.source = None
        self.error = None

    def run(self):
        try:
            while not self.stop.is_set():
                segmenter = Segmenter(self.config.audio)
                try:
                    self.source = create_source(self.config.input, self.config.audio)
                    with self.source as source:
                        logger.info("Audio input connected (%s)", self.config.input.kind)
                        while not self.stop.is_set():
                            pcm = source.read()
                            if not pcm:
                                final_segment = segmenter.finish()
                                if final_segment:
                                    self.deliver(final_segment)
                                process = getattr(source, "process", None)
                                if process is not None and process.wait(timeout=3) != 0:
                                    raise RuntimeError("FFmpeg input failed; verify the input and its audio track")
                                break
                            segment = segmenter.push(pcm)
                            if segment:
                                self.deliver(segment)
                    if self.config.input.kind == "file":
                        break
                except Exception as error:
                    if self.stop.is_set():
                        break
                    if self.config.input.kind == "file":
                        self.error = error
                        break
                    logger.warning("Audio input unavailable (%s); retrying", type(error).__name__)
                if not self.stop.is_set():
                    self.stop.wait(self.config.input.reconnect_seconds)
        finally:
            self.finished.set()

    def deliver(self, segment):
        if self.config.input.kind != "file":
            enqueue_latest(self.segments, segment)
            return
        while not self.stop.is_set():
            try:
                self.segments.put(segment, timeout=0.2)
                return
            except queue.Full:
                continue


def run_service(config, config_path, stop):
    recognizer = Recognizer(config.recognition)
    detector = KeywordDetector(config.detection)
    segments = queue.Queue(maxsize=config.audio.queue_size)
    worker = CaptureWorker(config, segments, stop)
    event_file = None
    if config.output.events_file:
        event_path = Path(config.output.events_file)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_file = event_path.open("a", encoding="utf-8")
    try:
        last_modified = Path(config_path).stat().st_mtime_ns
        worker.start()
        logger.info("Listening for %d keywords; Ctrl+C to stop", len(config.detection.keywords))
        while not stop.is_set():
            try:
                modified = Path(config_path).stat().st_mtime_ns
                if modified != last_modified:
                    last_modified = modified
                    updated = load_config(config_path)
                    detector.configure(updated.detection)
                    logger.info("Reloaded detection settings; other setting changes require a restart")
            except (OSError, ValueError, TypeError) as error:
                logger.warning("Cannot reload configuration (%s); keeping previous keywords", type(error).__name__)
            try:
                segment = segments.get(timeout=0.5)
            except queue.Empty:
                if worker.finished.is_set():
                    if worker.error is not None:
                        raise worker.error
                    break
                continue
            started = time.monotonic()
            text = recognizer.transcribe(segment)
            elapsed = time.monotonic() - started
            if config.output.log_transcripts and text:
                logger.info("Transcript: %s", text)
            hits = detector.detect(text)
            if not hits:
                continue
            event = {
                "schema_version": 1,
                "type": "keyword_detected",
                "id": str(uuid.uuid4()),
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "audio_end_at": datetime.fromtimestamp(segment.captured_at, timezone.utc).isoformat(),
                "keywords": hits,
                "text": text,
                "audio_seconds": round(segment.duration, 3),
                "recognition_seconds": round(elapsed, 3),
            }
            serialized = json.dumps(event, ensure_ascii=False)
            print(serialized, flush=True)
            if event_file:
                event_file.write(serialized + "\n")
                event_file.flush()
    finally:
        stop.set()
        if worker.source is not None and config.input.kind != "microphone":
            worker.source.interrupt()
        if worker.ident is not None:
            worker.join(timeout=5)
        if event_file:
            event_file.close()
        logger.info("Listener stopped")
