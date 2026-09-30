import logging
import re
import subprocess
import sys
import threading
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def rtsp_timeout_option(executable):
    result = subprocess.run(
        [executable, "-hide_banner", "-h", "demuxer=rtsp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Cannot inspect FFmpeg RTSP options")
    if re.search(r"(?m)^\s*-stimeout\b", result.stdout):
        return "-stimeout"
    if re.search(r"(?m)^\s*-timeout\b.*microseconds", result.stdout):
        return "-timeout"
    raise RuntimeError("FFmpeg does not expose a supported RTSP I/O timeout option")


def ffmpeg_command(input_config, audio_config):
    command = [input_config.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
    if input_config.kind == "rtsp":
        command += ["-rtsp_transport", "tcp", rtsp_timeout_option(input_config.ffmpeg), "15000000"]
    command += input_config.input_args
    if input_config.kind in {"rtsp", "file"}:
        command += ["-i", input_config.url]
    command += [
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(audio_config.sample_rate),
        "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1",
    ]
    return command


class MicrophoneSource:
    def __init__(self, input_config, audio_config):
        self.input_config = input_config
        self.audio_config = audio_config
        self.stream = None

    def __enter__(self):
        import sounddevice

        device = self.input_config.device
        self.stream = sounddevice.RawInputStream(
            samplerate=self.audio_config.sample_rate,
            blocksize=round(self.audio_config.sample_rate * self.audio_config.frame_seconds),
            channels=1,
            dtype="int16",
            device=None if device == "" else device,
        )
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            raise
        return self

    def read(self):
        buffer, overflowed = self.stream.read(round(self.audio_config.sample_rate * self.audio_config.frame_seconds))
        if overflowed:
            logger.warning("Microphone buffer overflow: some audio was lost")
        pcm = bytes(buffer)
        if sys.byteorder != "little":
            from array import array

            samples = array("h")
            samples.frombytes(pcm)
            samples.byteswap()
            pcm = samples.tobytes()
        return pcm

    def __exit__(self, *arguments):
        self.stream.close()


class FFmpegSource:
    def __init__(self, input_config, audio_config):
        self.input_config = input_config
        self.audio_config = audio_config
        self.process = None
        self.stderr_thread = None

    def __enter__(self):
        self.process = subprocess.Popen(
            ffmpeg_command(self.input_config, self.audio_config),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        self.stderr_thread = threading.Thread(target=self.drain_errors, daemon=True)
        self.stderr_thread.start()
        return self

    def drain_errors(self):
        for line in self.process.stderr:
            if line.strip():
                logger.warning("FFmpeg input/decoding error; verify the source and its audio track")

    def read(self):
        frame_bytes = round(self.audio_config.sample_rate * self.audio_config.frame_seconds) * 2
        chunks = bytearray()
        while len(chunks) < frame_bytes:
            chunk = self.process.stdout.read(frame_bytes - len(chunks))
            if not chunk:
                break
            chunks.extend(chunk)
        if len(chunks) % 2:
            raise RuntimeError("FFmpeg returned incomplete PCM samples")
        return bytes(chunks)

    def interrupt(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass

    def __exit__(self, *arguments):
        self.interrupt()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
        self.stderr_thread.join(timeout=1)
        self.process.stdout.close()
        self.process.stderr.close()


def create_source(input_config, audio_config):
    source_type = MicrophoneSource if input_config.kind == "microphone" else FFmpegSource
    return source_type(input_config, audio_config)
