import argparse
import importlib.metadata
import json
import logging
import signal
import sys
import threading

from .config import load_config, validate


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Continuous local speech recognition and keyword detection")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Start listening")
    run.add_argument("--config", default="config.local.toml")
    run.add_argument("--input-file", help="Process a file once instead of listening to a microphone")
    run.add_argument("--log-transcripts", action="store_true", help="Print all recognized text to stderr")
    commands.add_parser("devices", help="List local audio input/output devices")
    commands.add_parser("check", help="Report inference packages and supported CPU/GPU compute types")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if arguments.command == "devices":
            import sounddevice

            print(sounddevice.query_devices())
            return 0
        if arguments.command == "check":
            import ctranslate2

            report = {
                "packages": {name: importlib.metadata.version(name) for name in ("faster-whisper", "ctranslate2", "numpy", "sounddevice")},
                "cpu_compute_types": sorted(ctranslate2.get_supported_compute_types("cpu")),
            }
            try:
                report["cuda_compute_types"] = sorted(ctranslate2.get_supported_compute_types("cuda"))
            except Exception as error:
                report["cuda_error"] = str(error)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        config = load_config(arguments.config)
        if arguments.input_file:
            config.input.kind = "file"
            config.input.url = arguments.input_file
            config.input.input_args = []
        if arguments.log_transcripts:
            config.output.log_transcripts = True
        validate(config)
        stop = threading.Event()
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signal_number, lambda *_arguments: stop.set())
        from .service import run_service

        run_service(config, arguments.config, stop)
        return 0
    except Exception as error:
        logging.error("Cannot continue (%s): %s", type(error).__name__, error)
        return 1
