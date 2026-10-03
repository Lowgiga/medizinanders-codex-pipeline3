"""Technical QA tests; real ffmpeg fixtures are generated only in temp dirs."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from medizinanders import media


def statuses(report: dict) -> dict[str, str]:
    return {check["name"]: check["status"] for check in report["pflichtpruefungen"]}


def box(kind: bytes, payload: bytes = b"", *, extended: bool = False) -> bytes:
    if extended:
        return struct.pack(">I4sQ", 1, kind, len(payload) + 16) + payload
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


def mp4_bytes(faststart: bool = True) -> bytes:
    ftyp = box(b"ftyp", b"isom" + bytes(4) + b"isommp42")
    moov, mdat = box(b"moov", extended=True), box(b"mdat", b"unit-test")
    return ftyp + (moov + mdat if faststart else mdat + moov)


def stream() -> dict:
    return {
        "codec_name": "h264", "profile": "High", "level": 41,
        "width": 1080, "height": 1920, "sample_aspect_ratio": "1:1",
        "time_base": "1/30000", "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
        "duration": "58.000000", "field_order": "progressive", "pix_fmt": "yuv420p",
        "color_primaries": "bt709", "color_transfer": "bt709", "color_space": "bt709",
        "nb_frames": "1740", "has_b_frames": 2,
    }


def frame_data(count: int = 1740) -> list[dict]:
    return [{
        "pts": index * 1000, "best_effort_timestamp": index * 1000,
        "pkt_duration": 1000, "key_frame": int(index % 60 == 0),
        "pict_type": "I" if index % 60 == 0 else ("P" if index % 3 == 0 else "B"),
        "width": 1080, "height": 1920, "sample_aspect_ratio": "1:1",
        "interlaced_frame": 0, "pix_fmt": "yuv420p",
        "color_primaries": "bt709", "color_transfer": "bt709", "color_space": "bt709",
    } for index in range(count)]


class MediaUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_required_missing_check_blocks_even_with_known_failure(self) -> None:
        qa = media._QA(self.root / "input.mp4", ("known", "missing"))
        qa.check("known", False, "correct", "incorrect")
        report = qa.finish()
        self.assertEqual(report["ergebnis"], "pruefung_unvollstaendig")
        self.assertEqual(statuses(report), {"known": "fehlgeschlagen", "missing": "nicht_geprueft"})
        self.assertEqual(len(report["findings"]), 2)
        self.assertTrue(all(finding["offen"] for finding in report["findings"]))

    def test_all_measured_checks_distinguish_eligibility_and_failure(self) -> None:
        qa = media._QA(self.root / "input.mp4", ("one",))
        qa.check("one", True, "value", "value")
        self.assertEqual(qa.finish()["ergebnis"], "freigabefaehig")
        qa = media._QA(self.root / "input.mp4", ("one",))
        qa.check("one", False, "value", "wrong")
        self.assertEqual(qa.finish()["ergebnis"], "nacharbeit_erforderlich")

    def test_missing_tools_persist_honest_report_without_changing_input(self) -> None:
        source = self.root / "input.mp4"
        source.write_bytes(mp4_bytes())
        before = source.read_bytes()
        with patch.object(media.shutil, "which", return_value=None):
            result = media.inspect_video(source, self.root / "reports")
        self.assertEqual(result["ergebnis"], "pruefung_unvollstaendig")
        self.assertEqual(result["datei_sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(statuses(result)["ffprobe"], "nicht_geprueft")
        self.assertEqual(statuses(result)["vollstaendiger_decode"], "nicht_geprueft")
        self.assertEqual(statuses(result)["framezahl_1740"], "nicht_geprueft")
        self.assertEqual(statuses(result)["mp4_faststart"], "bestanden")
        self.assertEqual(json.loads(Path(result["bericht_pfad"]).read_text()), result)
        self.assertEqual(len(result["pflichtpruefungen"]), len(media.VIDEO_CHECKS))

    def test_missing_source_is_not_given_a_fabricated_hash(self) -> None:
        result = media.inspect_video(self.root / "missing.mp4", self.root / "reports")
        self.assertEqual(statuses(result)["datei_lesbar"], "fehlgeschlagen")
        self.assertIsNone(result["datei_sha256"])
        self.assertTrue(Path(result["bericht_pfad"]).exists())
        self.assertEqual(result["ergebnis"], "pruefung_unvollstaendig")

    def test_report_directory_must_not_overwrite_source(self) -> None:
        source = self.root / "report.json"
        source.write_bytes(mp4_bytes())
        before = source.read_bytes()
        result = media.inspect_video(source, self.root)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(statuses(result)["berichte_gespeichert"], "nicht_geprueft")

    def test_evidence_symlink_must_not_overwrite_source(self) -> None:
        source = self.root / "source.mp4"
        source.write_bytes(mp4_bytes())
        (self.root / "decode.log").symlink_to(source)
        before = source.read_bytes()
        result = media.inspect_video(source, self.root)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(statuses(result)["berichte_gespeichert"], "nicht_geprueft")

    def test_process_timeout_is_an_uncompleted_check_and_has_no_shell(self) -> None:
        args = ["ffprobe", "-of", "json", "input with spaces.mp4"]
        with patch.object(media.subprocess, "run", side_effect=subprocess.TimeoutExpired(args, 10)) as run:
            result = media._run(args, self.root, "ffprobe", 10)
        self.assertEqual(result["status"], "nicht_geprueft")
        self.assertEqual(run.call_args.args[0], args)
        self.assertEqual(run.call_args.kwargs["timeout"], 10)
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertIsNone(result["returncode"])

    def test_mp4_faststart_checks_box_order_and_extended_sizes(self) -> None:
        source = self.root / "test.mp4"
        source.write_bytes(mp4_bytes(True))
        self.assertTrue(media._mp4_layout(source)["faststart"])
        source.write_bytes(mp4_bytes(False))
        self.assertFalse(media._mp4_layout(source)["faststart"])
        source.write_bytes(struct.pack(">I4sQ", 1, b"moov", 1000))
        with self.assertRaises(ValueError):
            media._mp4_layout(source)

    def test_frame_end_proves_58_seconds_not_last_timestamp(self) -> None:
        frames = frame_data()
        measured = media._frame_metrics(frames, stream())
        self.assertAlmostEqual(measured["letzter_frame_s"], 58 - 1 / 30)
        self.assertAlmostEqual(measured["dauer_s"], 58)
        self.assertTrue(measured["cfr"])
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58.000000"})
        result = qa.finish()
        for name in ("dauer_58s", "framezahl_1740", "frame_timestamps_cfr", "sar_1_1", "sdr_bt709", "gop_max_60"):
            self.assertEqual(statuses(result)[name], "bestanden", name)

    def test_cfr_uses_actual_timestamps_even_when_average_rate_is_30(self) -> None:
        frames = frame_data()
        for frame in frames[701:]:
            frame["pts"] += 500
            frame["best_effort_timestamp"] += 500
        measured = media._frame_metrics(frames, stream())
        self.assertFalse(measured["cfr"])
        self.assertGreater(measured["max_abweichung_vom_30fps_raster_s"], 0.016)

    def test_duplicate_timestamps_are_not_sorted_or_ignored(self) -> None:
        frames = frame_data()
        frames[30]["pts"] = frames[29]["pts"]
        frames[30]["best_effort_timestamp"] = frames[29]["best_effort_timestamp"]
        self.assertFalse(media._frame_metrics(frames, stream())["cfr"])

    def test_missing_middle_timestamp_blocks_cfr_but_not_proven_endpoint_duration(self) -> None:
        frames = frame_data()
        frames[30].pop("pts")
        frames[30].pop("best_effort_timestamp")
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58.000000"})
        result = statuses(qa.finish())
        self.assertEqual(result["frame_timestamps_cfr"], "nicht_geprueft")
        # First/last timestamps plus final frame duration independently prove 58 s.
        self.assertEqual(result["dauer_58s"], "bestanden")

    def test_missing_endpoint_blocks_duration_without_a_known_wrong_duration(self) -> None:
        for endpoint in ("first", "last_duration"):
            with self.subTest(endpoint=endpoint):
                frames = frame_data()
                if endpoint == "first":
                    frames[0].pop("pts")
                    frames[0].pop("best_effort_timestamp")
                else:
                    frames[-1].pop("pkt_duration")
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, stream(), {"duration": "58"})
                self.assertEqual(qa.checks["dauer_58s"]["status"], "nicht_geprueft")

    def test_timestamp_quantization_is_limited_to_half_a_clock_tick(self) -> None:
        metadata = stream()
        metadata["time_base"] = "1/1000"
        frames = frame_data()
        for index, frame in enumerate(frames):
            frame["pts"] = frame["best_effort_timestamp"] = round(index * 1000 / 30)
            frame["pkt_duration"] = 33
        measured = media._frame_metrics(frames, metadata)
        self.assertTrue(measured["cfr"])
        self.assertLessEqual(measured["max_abweichung_vom_30fps_raster_s"], 0.0005)

    def test_frame_count_does_not_trust_nb_frames_metadata(self) -> None:
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frame_data(1739), stream(), {"duration": "58.000000"})
        self.assertEqual(statuses(qa.finish())["framezahl_1740"], "fehlgeschlagen")

    def test_gop_limit_includes_final_gop(self) -> None:
        frames = frame_data(121)
        frames[-1]["key_frame"] = 0
        measured = media._frame_metrics(frames, stream())
        self.assertEqual(measured["gop_max_frames"], 61)

    def test_known_wrong_codec_is_failed_even_if_other_metadata_is_missing(self) -> None:
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._probe_stream(qa, {"codec_name": "hevc"}, {})
        self.assertEqual(statuses(qa.finish())["h264_high_level_4_1"], "fehlgeschlagen")

    def test_probe_composites_keep_known_failures_when_other_fields_are_missing(self) -> None:
        cases = (
            ("fps_30", {"r_frame_rate": "24/1"}, {}),
            ("fps_30", {"avg_frame_rate": "24/1"}, {}),
            ("audio_stereo", {}, {"channels": 1}),
            ("audio_stereo", {}, {"channel_layout": "mono"}),
            ("audio_abdeckung_58s", {}, {"start_time": "1"}),
            ("audio_abdeckung_58s", {}, {"duration": "57"}),
            ("rotation_0", {"side_data_list": [{"rotation": 90}, {"rotation": "unknown"}]}, {}),
            ("h264_high_level_4_1", {"profile": "Main"}, {}),
            ("aac_lc", {}, {"codec_name": "mp3"}),
            ("aac_lc", {}, {"profile": "HE-AAC"}),
        )
        for name, video, audio in cases:
            with self.subTest(name=name, video=video, audio=audio):
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._probe_stream(qa, video, audio)
                self.assertEqual(qa.checks[name]["status"], "fehlgeschlagen")
                self.assertTrue(any(finding["problem"].startswith(name + ":") for finding in qa.findings))

    def test_probe_composites_remain_unknown_without_a_known_failure(self) -> None:
        cases = (
            ("fps_30", {"r_frame_rate": "30/1"}, {}),
            ("audio_stereo", {}, {"channels": 2}),
            ("audio_abdeckung_58s", {}, {"start_time": "0"}),
            ("rotation_0", {"side_data_list": [{"rotation": 0}, {"rotation": "unknown"}]}, {}),
            ("h264_high_level_4_1", {"profile": "High"}, {}),
            ("aac_lc", {}, {"codec_name": "aac"}),
        )
        for name, video, audio in cases:
            with self.subTest(name=name):
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._probe_stream(qa, video, audio)
                self.assertEqual(qa.checks[name]["status"], "nicht_geprueft")

    def test_known_wrong_dimensions_survive_partial_metadata(self) -> None:
        cases = (
            ({"width": 1920, "height": None}, {}),
            ({"width": None}, {"width": 1280, "height": None}),
        )
        for metadata_changes, frame_changes in cases:
            with self.subTest(metadata=metadata_changes, frame=frame_changes):
                metadata, frames = stream(), frame_data()
                metadata.update(metadata_changes)
                frames[20].update(frame_changes)
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, metadata, {"duration": "58"})
                self.assertEqual(qa.checks["aufloesung_1080x1920"]["status"], "fehlgeschlagen")

    def test_known_interlacing_survives_missing_field_order_or_other_frames(self) -> None:
        for order, observed in ((None, 1), ("tt", None)):
            with self.subTest(order=order, observed=observed):
                metadata, frames = stream(), frame_data()
                metadata["field_order"] = order
                frames[20]["interlaced_frame"] = observed
                frames[21]["interlaced_frame"] = None
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, metadata, {"duration": "58"})
                self.assertEqual(qa.checks["progressiv"]["status"], "fehlgeschlagen")

    def test_known_wrong_pixel_format_survives_partial_metadata(self) -> None:
        for stream_format, observed in (("yuv422p", None), (None, "yuv420p10le")):
            with self.subTest(stream_format=stream_format, observed=observed):
                metadata, frames = stream(), frame_data()
                metadata["pix_fmt"] = stream_format
                frames[20]["pix_fmt"] = observed
                frames[21]["pix_fmt"] = None
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, metadata, {"duration": "58"})
                self.assertEqual(qa.checks["yuv420p"]["status"], "fehlgeschlagen")

    def test_frame_composites_remain_unknown_without_a_known_failure(self) -> None:
        for name, stream_key, frame_key in (
            ("aufloesung_1080x1920", "height", "height"),
            ("progressiv", "field_order", "interlaced_frame"),
            ("yuv420p", "pix_fmt", "pix_fmt"),
        ):
            with self.subTest(name=name):
                metadata, frames = stream(), frame_data()
                metadata[stream_key] = None
                frames[20][frame_key] = None
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, metadata, {"duration": "58"})
                self.assertEqual(qa.checks[name]["status"], "nicht_geprueft")

    def test_known_wrong_duration_is_not_hidden_by_missing_other_duration(self) -> None:
        cases = (("57", None, 1000), (None, "57", 1000), (None, None, 31000))
        for stream_duration, container_duration, final_frame_duration in cases:
            with self.subTest(stream=stream_duration, container=container_duration):
                metadata, frames = stream(), frame_data()
                metadata["duration"] = stream_duration
                frames[-1]["pkt_duration"] = final_frame_duration
                qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
                media._check_frames(qa, frames, metadata, {"duration": container_duration})
                self.assertEqual(qa.checks["dauer_58s"]["status"], "fehlgeschlagen")

    def test_known_bad_timestamps_survive_an_unrelated_missing_timestamp(self) -> None:
        frames = frame_data()
        frames[30].pop("pts")
        frames[30].pop("best_effort_timestamp")
        frames[70]["pts"] = frames[70]["best_effort_timestamp"] = frames[69]["pts"]
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58"})
        self.assertEqual(qa.checks["frame_timestamps_cfr"]["status"], "fehlgeschlagen")

    def test_known_wrong_start_survives_missing_middle_timestamp(self) -> None:
        frames = frame_data()
        frames[0]["pts"] = frames[0]["best_effort_timestamp"] = 500
        frames[30].pop("pts")
        frames[30].pop("best_effort_timestamp")
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58"})
        self.assertEqual(qa.checks["start_bei_null"]["status"], "fehlgeschlagen")

    def test_proven_long_gop_survives_an_unrelated_missing_key_flag(self) -> None:
        frames = frame_data(180)
        frames[60]["key_frame"] = 0
        frames[150].pop("key_frame")
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58"})
        self.assertEqual(qa.checks["gop_max_60"]["status"], "fehlgeschlagen")

    def test_unknown_keyframe_could_split_a_long_apparent_gop(self) -> None:
        frames = frame_data(100)
        for frame in frames[1:]:
            frame["key_frame"] = 0
        frames[50].pop("key_frame")
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58"})
        self.assertEqual(qa.checks["gop_max_60"]["status"], "nicht_geprueft")

    def test_known_non_key_start_survives_missing_other_key_flag(self) -> None:
        frames = frame_data()
        frames[0]["key_frame"] = 0
        frames[150].pop("key_frame")
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58"})
        self.assertEqual(qa.checks["gop_max_60"]["status"], "fehlgeschlagen")

    def test_known_non_idr_intra_survives_an_unrelated_missing_trace_packet(self) -> None:
        frames = [{"pts": 0, "pict_type": "I"}, {"pts": 1, "pict_type": None}, {"pts": 2, "pict_type": "I"}]
        trace = {"packets": [{"pts": 0, "nal_types": [5], "key": True},
                             {"pts": 2, "nal_types": [1], "key": True}]}
        self.assertFalse(media._closed_gop(trace, frames))

    def test_hdr_cannot_be_hidden_by_missing_other_color_tags(self) -> None:
        metadata = stream()
        metadata["color_primaries"] = "unknown"
        metadata["color_transfer"] = "smpte2084"
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frame_data(), metadata, {"duration": "58.000000"})
        self.assertEqual(statuses(qa.finish())["sdr_bt709"], "fehlgeschlagen")

    def test_frame_sar_change_is_detected(self) -> None:
        frames = frame_data()
        frames[100]["sample_aspect_ratio"] = "4:3"
        qa = media._QA(self.root / "test.mp4", media.VIDEO_CHECKS)
        media._check_frames(qa, frames, stream(), {"duration": "58.000000"})
        self.assertEqual(statuses(qa.finish())["sar_1_1"], "fehlgeschlagen")

    def test_packet_peak_does_not_use_average_bitrate(self) -> None:
        packets = [{"dts_time": str(index / 30), "duration_time": str(1 / 30),
                    "size": 90000 if index < 30 else 50} for index in range(120)]
        measured = media._packet_metrics(packets)
        self.assertIsNotNone(measured)
        self.assertGreater(measured["max_1s_fenster_bit_s"], 16_000_000)
        self.assertLess(measured["mittelwert_bit_s"], 10_000_000)
        packets[4].pop("duration_time")
        self.assertIsNone(media._packet_metrics(packets))

    def test_known_packet_peak_violation_survives_an_unknown_other_packet(self) -> None:
        packets = [{"dts_time": "0", "duration_time": "0.033333", "size": 2_000_001},
                   {"dts_time": "0.033333", "duration_time": None, "size": None}]
        measured = media._packet_peak(packets)
        self.assertFalse(measured["limit_ok"])
        self.assertFalse(measured["vollstaendig"])
        self.assertIsNone(measured["max_1s_fenster_bit_s"])
        self.assertGreater(measured["belegte_untergrenze_max_1s_bit_s"], 16_000_000)

    def test_partial_packet_data_cannot_invent_a_pass_below_limit(self) -> None:
        packets = [{"dts_time": "0", "duration_time": "0.033333", "size": 100},
                   {"dts_time": None, "duration_time": None, "size": None}]
        self.assertIsNone(media._packet_peak(packets)["limit_ok"])
        self.assertIsNone(media._packet_data_verdict(packets))

    def test_known_invalid_packet_data_survives_missing_other_fields(self) -> None:
        packets = [{"dts_time": "0", "duration_time": None, "size": -1}]
        self.assertFalse(media._packet_data_verdict(packets))

    def test_b_frame_failure_survives_missing_other_picture_types(self) -> None:
        cases = (
            ({"max_aufeinanderfolgende_b_frames": 3, "bildtypen_vollstaendig": False}, None, None),
            ({"bildtypen_vollstaendig": False}, None, 3),
            ({"bildtypen_vollstaendig": False}, 3, None),
        )
        for metrics, reorder, configured in cases:
            with self.subTest(metrics=metrics, reorder=reorder, configured=configured):
                self.assertFalse(media._b_frames_verdict(metrics, reorder, configured))
        self.assertIsNone(media._b_frames_verdict({"max_aufeinanderfolgende_b_frames": 2, "bildtypen_vollstaendig": False}, 2, 2))

    def test_known_decode_error_survives_timeout(self) -> None:
        source = self.root / "source.mp4"
        source.write_bytes(mp4_bytes())

        def incomplete_decode(args: list[str], report_dir: Path, name: str, timeout: int) -> dict:
            self.assertEqual(name, "decode")
            log = report_dir / "decode.log"
            log.write_text("[h264] Invalid NAL unit: actual observed decoder error\n")
            return {"status": "nicht_geprueft", "returncode": None, "stderr": str(log), "stdout": str(report_dir / "decode.stdout.log"), "problem": "Zeitlimit überschritten"}

        with patch.object(media.shutil, "which", side_effect=lambda name: "/test/ffmpeg" if name == "ffmpeg" else None), patch.object(media, "_run", side_effect=incomplete_decode):
            result = media.inspect_video(source, self.root / "partial-decode")
        self.assertEqual(statuses(result)["vollstaendiger_decode"], "fehlgeschlagen")

    def test_closed_gop_needs_all_intra_frames_to_be_idr(self) -> None:
        frames = [{"pts": 0, "pict_type": "I"}, {"pts": 1, "pict_type": "B"}, {"pts": 2, "pict_type": "I"}]
        packets = [{"pts": 0, "nal_types": [6, 5], "key": True},
                   {"pts": 1, "nal_types": [1], "key": False},
                   {"pts": 2, "nal_types": [1], "key": False}]
        self.assertFalse(media._closed_gop({"packets": packets}, frames))
        packets[2]["nal_types"] = [5]
        self.assertTrue(media._closed_gop({"packets": packets}, frames))
        self.assertIsNone(media._closed_gop({"packets": packets[:-1]}, frames))

    def test_x264_target_settings_are_only_taken_from_actual_sei_payload(self) -> None:
        payload = b"x264 - core - options: bitrate=10000 vbv_maxrate=16000 bframes=2 open_gop=0\0"
        lines = ["[trace_headers @ test] Packet: 800 bytes, key frame, pts 0, dts -2, duration 1.",
                 "[trace_headers @ test] 3 nal_unit_type 00101 = 5"]
        lines += [f"[trace_headers @ test] 8 user_data_payload_byte[{index}] 00000000 = {byte}" for index, byte in enumerate(payload)]
        logfile = self.root / "headers.log"
        logfile.write_text("\n".join(lines))
        parsed = media._parse_trace(logfile)
        self.assertEqual(parsed["x264_exportsettings"], {"bitrate": 10000, "vbv_maxrate": 16000, "bframes": 2, "open_gop": 0})
        self.assertEqual(parsed["packets"][0]["nal_types"], [5])

    def test_incomplete_sei_number_does_not_invent_an_export_setting(self) -> None:
        payload = b"x264 - core - options: bitrate=1000"
        logfile = self.root / "headers.log"
        logfile.write_text("\n".join(f"[trace_headers @ test] 8 user_data_payload_byte[{index}] 00000000 = {byte}" for index, byte in enumerate(payload)))
        self.assertNotIn("bitrate", media._parse_trace(logfile)["x264_exportsettings"])

    def test_loudness_parser_uses_integrated_and_true_peak_summary(self) -> None:
        logfile = self.root / "loudness.log"
        logfile.write_text("Summary:\nIntegrated loudness:\n I: -14.0 LUFS\nTrue peak:\n Peak: -2.0 dBFS\n")
        parsed = media._loudness(logfile)
        self.assertTrue(parsed["loudness_ok"])
        self.assertTrue(parsed["peak_ok"])
        logfile.write_text("Summary:\nIntegrated loudness:\n I: -12.0 LUFS\nTrue peak:\n Peak: -1.0 dBFS\n")
        parsed = media._loudness(logfile)
        self.assertFalse(parsed["loudness_ok"])
        self.assertFalse(parsed["peak_ok"])
        logfile.write_text("Summary:\nIntegrated loudness:\n I: -70.0 LUFS\nTrue peak:\n Peak: -inf dBFS\n")
        parsed = media._loudness(logfile)
        self.assertEqual(parsed["true_peak_dbtp"], "-inf")
        json.dumps(parsed, allow_nan=False)

    def test_known_loudness_failure_survives_missing_true_peak(self) -> None:
        logfile = self.root / "loudness.log"
        logfile.write_text("Summary:\nIntegrated loudness:\n I: -12.0 LUFS\n")
        parsed = media._loudness(logfile)
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed["loudness_ok"])
        self.assertIsNone(parsed["peak_ok"])

    def test_known_true_peak_failure_survives_missing_loudness(self) -> None:
        logfile = self.root / "loudness.log"
        logfile.write_text("Summary:\nTrue peak:\n Peak: -1.0 dBFS\n")
        parsed = media._loudness(logfile)
        self.assertIsNotNone(parsed)
        self.assertFalse(parsed["peak_ok"])
        self.assertIsNone(parsed["loudness_ok"])

    def test_good_loudness_does_not_invent_a_missing_peak(self) -> None:
        logfile = self.root / "loudness.log"
        logfile.write_text("Summary:\nIntegrated loudness:\n I: -14.0 LUFS\n")
        parsed = media._loudness(logfile)
        self.assertTrue(parsed["loudness_ok"])
        self.assertIsNone(parsed["peak_ok"])

    def test_disclaimer_silence_requires_full_coverage_without_a_gap(self) -> None:
        logfile = self.root / "disclaimer.log"
        logfile.write_text("silence_start: 0\nsilence_end: 4 | silence_duration: 4\nblack_start:0 black_end:3.96667 black_duration:3.96667\n")
        measured = media._disclaimer_measurements(logfile)
        self.assertTrue(measured["durchgehend_still"])
        self.assertEqual(len(measured["schwarz_intervalle"]), 1)
        logfile.write_text("silence_start: 0\nsilence_end: 2\nsilence_start: 2.1\nsilence_end: 4\n")
        self.assertFalse(media._disclaimer_measurements(logfile)["durchgehend_still"])
        logfile.write_text("silence_start: 0.010\nsilence_end: 4\n")
        self.assertFalse(media._disclaimer_measurements(logfile)["durchgehend_still"])


class _TestFont:
    """Synthetic widths exercise the QA decision, never real font selection."""
    def getbbox(self, line: str) -> tuple[int, int, int, int]:
        return (0, 0, int(self.getlength(line)), 52)

    def getlength(self, line: str) -> float:
        return sum(50 if char == "W" else 10 for char in line)


class SRTTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "subtitle.srt"
        self.font_file = self.root / "unit-test-font-only.ttf"
        self.font_file.write_bytes(b"Synthetic fixture for QA decisions, not a usable font.")

    def validate(self, text: str, *, font: bool = True) -> dict:
        self.source.write_text(text, encoding="utf-8")
        if font:
            with patch.object(media, "_load_montserrat", return_value=(_TestFont(), self.font_file)):
                return media.validate_srt(self.source)
        with patch.object(media, "_load_montserrat", side_effect=ValueError("Montserrat Bold fehlt")):
            return media.validate_srt(self.source)

    def test_valid_utf8_bom_and_adjacent_cues_preserve_bytes(self) -> None:
        text = "\ufeff1\r\n00:00:00,000 --> 00:00:00,800\r\nÄrztliche QA\r\n\r\n2\r\n00:00:00,800 --> 00:00:04,800\r\nZweite Zeile\r\n"
        result = self.validate(text)
        self.assertEqual(result["ergebnis"], "freigabefaehig")
        self.assertTrue(all(status == "bestanden" for status in statuses(result).values()))
        self.assertEqual(result["datei_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(result["menschliche_pruefungen"][0]["status"], "ausstehend")

    def test_missing_font_is_a_missing_mandatory_check(self) -> None:
        result = self.validate("1\n00:00:00,000 --> 00:00:02,000\nHallo Welt\n", font=False)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "nicht_geprueft")
        self.assertEqual(result["ergebnis"], "pruefung_unvollstaendig")

    def test_non_utf8_is_rejected(self) -> None:
        self.source.write_bytes(b"1\n00:00:00,000 --> 00:00:02,000\nGr\xfc\xdfen\n")
        result = media.validate_srt(self.source)
        self.assertEqual(statuses(result)["srt_utf8"], "fehlgeschlagen")

    def test_empty_file_and_invalid_timestamp_are_rejected(self) -> None:
        for text in ("", "1\n00:00:60,000 --> 00:00:62,000\nText\n", "1\n00:00:02,000 --> 00:00:01,000\nText\n"):
            with self.subTest(text=text):
                result = self.validate(text)
                self.assertEqual(statuses(result)["srt_syntax"], "fehlgeschlagen")

    def test_too_many_lines_and_characters_are_rejected(self) -> None:
        result = self.validate("1\n00:00:00,000 --> 00:00:04,000\n" + "a" * 29 + "\nzweite\ndritte\n")
        self.assertEqual(statuses(result)["srt_max_2_zeilen"], "fehlgeschlagen")
        self.assertEqual(statuses(result)["srt_max_28_zeichen"], "fehlgeschlagen")

    def test_reading_speed_counts_both_lines(self) -> None:
        result = self.validate("1\n00:00:00,000 --> 00:00:00,800\n123456789\n123456789\n")
        self.assertEqual(statuses(result)["srt_max_28_zeichen"], "bestanden")
        self.assertEqual(statuses(result)["srt_max_18_cps"], "fehlgeschlagen")
        self.assertEqual(result["technischer_report"]["cues"][0]["cps"], 22.5)

    def test_duration_limits_are_inclusive_and_outside_limits_fail(self) -> None:
        for end, expected in ((799, "fehlgeschlagen"), (800, "bestanden"), (4000, "bestanden"), (4001, "fehlgeschlagen")):
            with self.subTest(end=end):
                result = self.validate(f"1\n00:00:00,000 --> 00:00:{end // 1000:02d},{end % 1000:03d}\nText\n")
                self.assertEqual(statuses(result)["srt_dauer_0_8_bis_4s"], expected)

    def test_overlap_and_out_of_range_are_rejected(self) -> None:
        result = self.validate("1\n00:00:54,000 --> 00:00:56,000\nErster Cue\n\n2\n00:00:55,000 --> 00:00:59,000\nZweiter Cue\n")
        self.assertEqual(statuses(result)["srt_keine_ueberlappung"], "fehlgeschlagen")
        self.assertEqual(statuses(result)["srt_zeitgrenzen_0_bis_58s"], "fehlgeschlagen")

    def test_58_second_boundary_is_accepted(self) -> None:
        result = self.validate("1\n00:00:54,000 --> 00:00:58,000\nText\n")
        self.assertEqual(statuses(result)["srt_zeitgrenzen_0_bis_58s"], "bestanden")

    def test_pixel_width_can_fail_when_character_count_passes(self) -> None:
        result = self.validate("1\n00:00:00,000 --> 00:00:04,000\n" + "W" * 20 + "\n")
        self.assertEqual(statuses(result)["srt_max_28_zeichen"], "bestanden")
        self.assertEqual(statuses(result)["srt_pixelbreite"], "fehlgeschlagen")
        self.assertEqual(result["ergebnis"], "nacharbeit_erforderlich")

    def test_known_pixel_overflow_survives_a_later_glyph_measurement_error(self) -> None:
        class PartiallyMeasurableFont(_TestFont):
            def getbbox(self, line: str) -> tuple[int, int, int, int]:
                if line == "fehlend":
                    raise ValueError("Glyphenmessung nicht möglich")
                return super().getbbox(line)

        self.source.write_text("1\n00:00:00,000 --> 00:00:04,000\n" + "W" * 20 + "\nfehlend\n")
        with patch.object(media, "_load_montserrat", return_value=(PartiallyMeasurableFont(), self.font_file)):
            result = media.validate_srt(self.source)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "fehlgeschlagen")

    def test_known_pixel_overflow_survives_missing_font_hash(self) -> None:
        original = media._sha256

        def hash_file(path: Path) -> str:
            if path == self.font_file:
                raise OSError("Fontdatei nach Messung nicht mehr lesbar")
            return original(path)

        self.source.write_text("1\n00:00:00,000 --> 00:00:04,000\n" + "W" * 20 + "\n")
        with patch.object(media, "_load_montserrat", return_value=(_TestFont(), self.font_file)), patch.object(media, "_sha256", side_effect=hash_file):
            result = media.validate_srt(self.source)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "fehlgeschlagen")

    def test_partial_small_glyph_measurement_cannot_invent_a_pass(self) -> None:
        class MissingInkFont(_TestFont):
            def getbbox(self, line: str) -> tuple[int, int, int, int]:
                raise ValueError("Ink-Messung fehlt")

        self.source.write_text("1\n00:00:00,000 --> 00:00:04,000\nText\n")
        with patch.object(media, "_load_montserrat", return_value=(MissingInkFont(), self.font_file)):
            result = media.validate_srt(self.source)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "nicht_geprueft")

    def test_known_large_ink_width_survives_missing_advance_measurement(self) -> None:
        class MissingAdvanceFont(_TestFont):
            def getbbox(self, line: str) -> tuple[int, int, int, int]:
                return 0, 0, 1000, 52

            def getlength(self, line: str) -> float:
                raise ValueError("Advance-Messung fehlt")

        self.source.write_text("1\n00:00:00,000 --> 00:00:04,000\nText\n")
        with patch.object(media, "_load_montserrat", return_value=(MissingAdvanceFont(), self.font_file)):
            result = media.validate_srt(self.source)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "fehlgeschlagen")

    def test_real_pillow_glyph_metrics_are_used_by_width_check(self) -> None:
        font_file = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if not font_file.is_file():
            self.skipTest("No local real font fixture available")
        try:
            from PIL import ImageFont
        except ImportError:
            self.skipTest("Pillow not installed")
        font = ImageFont.truetype(str(font_file), 52)
        self.source.write_text("1\n00:00:00,000 --> 00:00:04,000\n" + "W" * 20 + "\n")
        # Font selection has its own rejection test; use real glyph geometry here.
        with patch.object(media, "_load_montserrat", return_value=(font, font_file)):
            result = media.validate_srt(self.source)
        self.assertGreater(result["technischer_report"]["schrift"]["zeilenbreiten"][0]["pixelbreite"], 840)
        self.assertEqual(statuses(result)["srt_pixelbreite"], "fehlgeschlagen")

    def test_non_montserrat_font_is_not_silently_substituted(self) -> None:
        font_file = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if not font_file.is_file():
            self.skipTest("No local non-Montserrat font fixture available")
        try:
            from PIL import ImageFont
        except ImportError:
            self.skipTest("Pillow not installed")
        with self.assertRaisesRegex(ValueError, "Montserrat"):
            media._load_montserrat(font_file)

    def test_semibold_is_not_accepted_as_the_required_bold_face(self) -> None:
        try:
            from PIL import ImageFont
        except ImportError:
            self.skipTest("Pillow not installed")

        class SemiBoldFont:
            def getname(self) -> tuple[str, str]:
                return "Montserrat", "SemiBold"

        with patch.object(ImageFont, "truetype", return_value=SemiBoldFont()):
            with self.assertRaisesRegex(ValueError, "Bold"):
                media._load_montserrat(self.font_file)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe not installed")
class RealFFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.video = cls.root / "profil falsch ü.mp4"
        command = [
            shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=64x96:rate=30",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "1",
            "-c:v", "libx264", "-threads", "1", "-profile:v", "baseline", "-level:v", "4.1",
            "-pix_fmt", "yuv420p", "-x264-params", "keyint=30:min-keyint=30:scenecut=0:bframes=0:colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-color_primaries:v", "bt709", "-color_trc:v", "bt709", "-colorspace:v", "bt709",
            "-c:a", "aac", "-b:a", "384k", "-movflags", "+faststart", str(cls.video),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        if result.returncode:
            cls.temporary.cleanup()
            if "Unknown encoder" in result.stderr:
                raise unittest.SkipTest("libx264/AAC unavailable")
            raise AssertionError(f"Failed to create ffmpeg fixture: {result.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_real_wrong_profile_is_rejected_but_full_decode_is_measured(self) -> None:
        before = self.video.read_bytes()
        result = media.inspect_video(self.video, self.root / "wrong-profile-report")
        checks = statuses(result)
        self.assertEqual(checks["h264_high_level_4_1"], "fehlgeschlagen")
        self.assertEqual(checks["vollstaendiger_decode"], "bestanden")
        self.assertEqual(checks["framezahl_1740"], "fehlgeschlagen")
        self.assertEqual(checks["mp4_faststart"], "bestanden")
        self.assertEqual(checks["sdr_bt709"], "bestanden")
        self.assertEqual(checks["sar_1_1"], "bestanden")
        self.assertNotEqual(result["ergebnis"], "freigabefaehig")
        self.assertEqual(self.video.read_bytes(), before)
        self.assertEqual(result["technischer_report"]["frames"]["framezahl"], 30)
        self.assertEqual(checks["audio_bitrate_ziel_384kbps"], "nicht_geprueft")
        self.assertEqual(json.loads(Path(result["bericht_pfad"]).read_text()), result)

    def test_corrupt_video_payload_fails_full_decode(self) -> None:
        result = subprocess.run([
            shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
            "-show_packets", "-show_entries", "packet=pos,size", "-of", "json", str(self.video),
        ], capture_output=True, text=True, timeout=30, check=True)
        first = json.loads(result.stdout)["packets"][0]
        start, length = int(first["pos"]), int(first["size"])
        corrupt = self.root / "corrupt.mp4"
        content = bytearray(self.video.read_bytes())
        content[start + 4:start + length] = b"\xff" * (length - 4)
        corrupt.write_bytes(content)
        report = media.inspect_video(corrupt, self.root / "corrupt-report")
        self.assertEqual(statuses(report)["vollstaendiger_decode"], "fehlgeschlagen")
        self.assertNotEqual(report["ergebnis"], "freigabefaehig")
        self.assertTrue(any(finding["schwere"] == "K0" and "decode" in finding["problem"] for finding in report["findings"]))
        self.assertNotEqual(report["technischer_report"]["prozesse"]["decode"]["returncode"], 0)

    def test_real_58_second_timestamps_and_disclaimer_silence(self) -> None:
        video = self.root / "58seconds-small.mp4"
        command = [
            shutil.which("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=black:size=64x96:rate=30",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "58",
            "-c:v", "libx264", "-threads", "1", "-profile:v", "high", "-level:v", "4.1",
            "-pix_fmt", "yuv420p", "-b:v", "10M", "-maxrate", "16M", "-bufsize", "32M",
            "-x264-params", "keyint=60:min-keyint=60:scenecut=0:open-gop=0:bframes=2:b-adapt=0:colorprim=bt709:transfer=bt709:colormatrix=bt709",
            "-c:a", "aac", "-b:a", "384k", "-movflags", "+faststart", str(video),
        ]
        subprocess.run(command, capture_output=True, text=True, timeout=60, check=True)
        report = media.inspect_video(video, self.root / "58seconds-report")
        checks = statuses(report)
        for name in ("framezahl_1740", "frame_timestamps_cfr", "dauer_58s", "audio_abdeckung_58s",
                     "gop_max_60", "gop_geschlossen", "b_frames_2", "h264_high_level_4_1",
                     "disclaimer_messung_54_bis_58s", "disclaimer_audio_stille", "video_bitrate_ziel_10mbps", "video_bitrate_max_konfiguration"):
            self.assertEqual(checks[name], "bestanden", name)
        self.assertTrue(report["technischer_report"]["disclaimer"]["durchgehend_still"])
        self.assertTrue(report["technischer_report"]["disclaimer"]["schwarz_intervalle"])
        self.assertEqual(checks["audio_loudness"], "fehlgeschlagen")  # Entire silent film is not a valid master.
        self.assertEqual(checks["aufloesung_1080x1920"], "fehlgeschlagen")
        self.assertNotEqual(report["ergebnis"], "freigabefaehig")


if __name__ == "__main__":
    unittest.main()
