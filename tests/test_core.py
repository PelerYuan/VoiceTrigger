import contextlib
import io
import json
import os
import queue
import sys
import tempfile
import threading
import unittest
from array import array
from pathlib import Path
from unittest.mock import Mock, patch

from voice_trigger.audio import ffmpeg_command, rtsp_timeout_option
from voice_trigger.config import AudioConfig, DetectionConfig, InputConfig, load_config
from voice_trigger.detection import KeywordDetector
from voice_trigger.segmenter import Segmenter, pcm_rms
from voice_trigger.service import enqueue_latest, run_service


def pcm(amplitude=0):
    samples = array("h", [amplitude] * 1600)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


class DetectionTests(unittest.TestCase):
    def test_chinese_and_spacing(self):
        detector = KeywordDetector(DetectionConfig(["张三", "小王"], 0))
        self.assertEqual(detector.detect("你好，张 三！", now=0), ["张三"])

    def test_case_width_and_word_boundaries(self):
        detector = KeywordDetector(DetectionConfig(["Ann"], 0))
        self.assertEqual(detector.detect("banana", now=0), [])
        self.assertEqual(detector.detect("Hello ＡＮＮ!", now=0), ["Ann"])
        self.assertEqual(detector.detect("Annette", now=0), [])

    def test_multi_word_keyword(self):
        detector = KeywordDetector(DetectionConfig(["hello Peter"], 0))
        self.assertEqual(detector.detect("Hello   Peter!", now=0), ["hello Peter"])

    def test_independent_cooldown(self):
        detector = KeywordDetector(DetectionConfig(["张三", "小王"], 10))
        self.assertEqual(detector.detect("张三", now=0), ["张三"])
        self.assertEqual(detector.detect("张三和小王", now=1), ["小王"])
        self.assertEqual(detector.detect("张三", now=10), ["张三"])

    def test_reload_preserves_cooldown(self):
        detector = KeywordDetector(DetectionConfig(["张三"], 10))
        detector.detect("张三", now=0)
        detector.configure(DetectionConfig(["张三", "小王"], 10))
        self.assertEqual(detector.detect("张三和小王", now=1), ["小王"])
        detector.configure(DetectionConfig(["小王"], 10))
        self.assertEqual(detector.detect("张三", now=20), [])

    def test_duplicate_keywords_only_trigger_once(self):
        detector = KeywordDetector(DetectionConfig(["Ann", "ann"], 0))
        self.assertEqual(detector.detect("Ann", now=0), ["Ann"])


class SegmenterTests(unittest.TestCase):
    def test_silence_does_not_emit(self):
        segmenter = Segmenter(AudioConfig())
        for _frame in range(100):
            self.assertIsNone(segmenter.push(pcm()))
        self.assertIsNone(segmenter.finish())

    def test_pre_roll_and_silence_end(self):
        segmenter = Segmenter(AudioConfig())
        for _frame in range(4):
            segmenter.push(pcm())
        for _frame in range(3):
            segmenter.push(pcm(2000))
        emitted = []
        for _frame in range(7):
            segment = segmenter.push(pcm(), captured_at=123)
            if segment:
                emitted.append(segment)
        self.assertEqual(len(emitted), 1)
        self.assertAlmostEqual(emitted[0].duration, 1.3)
        self.assertEqual(emitted[0].captured_at, 123)

    def test_short_click_is_rejected(self):
        segmenter = Segmenter(AudioConfig())
        segmenter.push(pcm(2000))
        for _frame in range(7):
            self.assertIsNone(segmenter.push(pcm()))

    def test_long_speech_is_split_with_overlap(self):
        segmenter = Segmenter(AudioConfig(max_segment_seconds=1.5, overlap_seconds=0.3))
        emitted = []
        for _frame in range(27):
            segment = segmenter.push(pcm(2000))
            if segment:
                emitted.append(segment)
        self.assertEqual(len(emitted), 2)
        self.assertAlmostEqual(emitted[0].duration, 1.5)
        self.assertAlmostEqual(emitted[1].duration, 1.5)

    def test_finish_emits_final_speech(self):
        segmenter = Segmenter(AudioConfig())
        segmenter.push(pcm(2000))
        segmenter.push(pcm(2000))
        self.assertAlmostEqual(segmenter.finish().duration, 0.2)
        self.assertIsNone(segmenter.finish())

    def test_zero_overlap(self):
        segmenter = Segmenter(AudioConfig(max_segment_seconds=1, overlap_seconds=0))
        for _frame in range(10):
            emitted = segmenter.push(pcm(2000))
        self.assertAlmostEqual(emitted.duration, 1)
        self.assertFalse(segmenter.frames)

    def test_rms(self):
        self.assertEqual(pcm_rms(pcm()), 0)
        self.assertAlmostEqual(pcm_rms(pcm(16384)), 0.5)


class ConfigTests(unittest.TestCase):
    def load(self, content):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                return load_config(config_path)

    def test_defaults(self):
        self.assertEqual(self.load("").recognition.compute_type, "int8")

    def test_empty_keyword_is_rejected(self):
        with self.assertRaises(ValueError):
            self.load('[detection]\nkeywords=[" "]')

    def test_bad_timing_is_rejected(self):
        with self.assertRaises(ValueError):
            self.load('[audio]\nmax_segment_seconds=0.5\noverlap_seconds=0.5')

    def test_rtsp_requires_url(self):
        with self.assertRaises(ValueError):
            self.load('[input]\nkind="rtsp"')

    def test_integer_queue_size(self):
        with self.assertRaises(ValueError):
            self.load('[audio]\nqueue_size=1.5')

    def test_nonfinite_values_rejected(self):
        with self.assertRaises(ValueError):
            self.load('[audio]\nrms_threshold=nan')

    def test_unknown_section_rejected(self):
        with self.assertRaises(ValueError):
            self.load('[detecton]\nkeywords=["张三"]')

    def test_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("", encoding="utf-8")
            with patch.dict(os.environ, {"VOICE_DEVICE": "cuda", "VOICE_COMPUTE_TYPE": "int8_float32"}, clear=True):
                config = load_config(config_path)
            self.assertEqual(config.recognition.device, "cuda")
            self.assertEqual(config.recognition.compute_type, "int8_float32")


class AudioCommandTests(unittest.TestCase):
    @patch("voice_trigger.audio.rtsp_timeout_option", return_value="-timeout")
    def test_rtsp_command(self, _timeout_probe):
        command = ffmpeg_command(InputConfig(kind="rtsp", url="rtsp://camera/stream"), AudioConfig())
        self.assertIn("-timeout", command)
        self.assertEqual(command[command.index("-map") + 1], "0:a:0")
        self.assertEqual(command[-1], "pipe:1")

    def test_file_path_is_a_single_argument(self):
        command = ffmpeg_command(InputConfig(kind="file", url="my audio & test.wav"), AudioConfig())
        self.assertEqual(command[command.index("-i") + 1], "my audio & test.wav")

    @patch("voice_trigger.audio.subprocess.run")
    def test_legacy_rtsp_timeout(self, process):
        process.return_value.returncode = 0
        process.return_value.stdout = "  -timeout maximum wait for incoming connections\n  -stimeout socket timeout in microseconds"
        self.assertEqual(rtsp_timeout_option("ffmpeg-old"), "-stimeout")

    @patch("voice_trigger.audio.subprocess.run")
    def test_modern_rtsp_timeout(self, process):
        process.return_value.returncode = 0
        process.return_value.stdout = "  -timeout set timeout (in microseconds) of socket I/O operations"
        self.assertEqual(rtsp_timeout_option("ffmpeg-new"), "-timeout")


class PipelineTests(unittest.TestCase):
    def test_bounded_live_queue_keeps_latest(self):
        target = queue.Queue(maxsize=1)
        target.put("old")
        with self.assertLogs("voice_trigger.service", level="WARNING"):
            enqueue_latest(target, "new")
        self.assertEqual(target.get_nowait(), "new")

    def test_file_pipeline_outputs_json_event_and_exits(self):
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        source.process = None
        source.read.side_effect = [pcm(2000), pcm(2000), b""]
        recognizer = Mock()
        recognizer.transcribe.return_value = "你好，张三！"
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            event_path = Path(directory) / "events.jsonl"
            config_path.write_text(
                '[input]\nkind="file"\nurl="test.wav"\n[output]\nevents_file=""', encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(config_path)
            config.output.events_file = str(event_path)
            output = io.StringIO()
            with patch("voice_trigger.service.create_source", return_value=source), patch(
                "voice_trigger.service.Recognizer", return_value=recognizer
            ), contextlib.redirect_stdout(output):
                run_service(config, config_path, threading.Event())
            event = json.loads(output.getvalue())
            self.assertEqual(event["schema_version"], 1)
            self.assertEqual(event["type"], "keyword_detected")
            self.assertEqual(event["keywords"], ["张三"])
            self.assertEqual(json.loads(event_path.read_text(encoding="utf-8")), event)
            self.assertAlmostEqual(event["audio_seconds"], 0.2)

    def test_file_failure_is_not_silently_ignored(self):
        source = Mock()
        source.__enter__ = Mock(side_effect=RuntimeError("bad input"))
        source.__exit__ = Mock()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                '[input]\nkind="file"\nurl="test.wav"\n[output]\nevents_file=""', encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(config_path)
            with patch("voice_trigger.service.create_source", return_value=source), patch(
                "voice_trigger.service.Recognizer"
            ), self.assertRaisesRegex(RuntimeError, "bad input"):
                run_service(config, config_path, threading.Event())


if __name__ == "__main__":
    unittest.main()
