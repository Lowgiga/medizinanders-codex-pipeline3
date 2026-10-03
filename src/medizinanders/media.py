"""Read-only technical media QA; this module never approves or repairs media.

All subprocesses use argument lists and finite timeouts. Encoder *targets* are
not inferred from average VBR bitrates. Unavailable mandatory measurements are
reported as ``nicht_geprueft`` and prevent technical eligibility. Semantic QA,
subtitle synchronization, layout and the disclaimer wording need human review.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unicodedata
from collections import deque
from collections.abc import Iterable
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from .storage import Blocked, ensure_contained


PROBE_TIMEOUT = 180
DECODE_TIMEOUT = 600
FILTER_TIMEOUT = 600
VIDEO_SECONDS = 58
VIDEO_FRAMES = 1740
FPS = 30
SUBTITLE_FONT_SIZE = 52
SUBTITLE_WIDTH = 840  # x=90…930; Montserrat Bold at the actual export size.

VIDEO_CHECKS = (
    "datei_lesbar", "ffprobe", "videostream", "audiostream", "container_mp4",
    "mp4_faststart", "vollstaendiger_decode", "frame_daten", "framezahl_1740",
    "frame_timestamps_cfr", "dauer_58s", "start_bei_null", "aufloesung_1080x1920",
    "sar_1_1", "fps_30", "progressiv", "yuv420p", "sdr_bt709",
    "h264_high_level_4_1", "rotation_0", "video_packet_daten",
    "video_bitrate_max_16mbps", "video_bitrate_max_konfiguration", "video_bitrate_ziel_10mbps", "gop_max_60",
    "gop_geschlossen", "b_frames_2", "aac_lc", "audio_48000_hz",
    "audio_stereo", "audio_bitrate_ziel_384kbps", "audio_abdeckung_58s",
    "audio_loudness", "audio_true_peak", "disclaimer_messung_54_bis_58s",
    "disclaimer_audio_stille",
    "datei_unveraendert", "berichte_gespeichert",
)
SRT_CHECKS = (
    "datei_lesbar", "srt_utf8", "srt_syntax", "srt_max_2_zeilen",
    "srt_max_28_zeichen", "srt_max_18_cps", "srt_dauer_0_8_bis_4s",
    "srt_keine_ueberlappung", "srt_zeitgrenzen_0_bis_58s", "srt_pixelbreite",
    "datei_unveraendert",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


class _QA:
    def __init__(self, path: Path, required: tuple[str, ...]) -> None:
        self.path = path
        self.required = required
        self.checks: dict[str, dict[str, str]] = {}
        self.findings: list[dict[str, Any]] = []
        self.data: dict[str, Any] = {
            "datei": str(path), "datei_sha256": None,
            "geprueft_am": datetime.now(timezone.utc).isoformat(),
            "technischer_report": {}, "menschliche_pruefungen": [],
        }

    def check(
        self, name: str, passed: bool | None, expected: Any, actual: Any,
        *, problem: str | None = None, severity: str = "K1",
        route: str = "09_POSTPRODUKTION: Export korrigieren und erneut prüfen.",
    ) -> None:
        status = "nicht_geprueft" if passed is None else (
            "bestanden" if passed else "fehlgeschlagen"
        )
        self.checks[name] = {"name": name, "status": status}
        if passed is not True:
            self.findings.append({
                "datei": str(self.path),
                "problem": problem or (
                    f"{name}: Prüfung nicht vollständig möglich." if passed is None
                    else f"{name}: Vorgabe nicht erfüllt."
                ),
                "soll": _text(expected), "ist": _text(actual),
                "schwere": severity, "rueckweg": route, "offen": True,
            })

    def finish(self) -> dict[str, Any]:
        for name in self.required:
            if name not in self.checks:
                self.check(
                    name, None, "Messbare Pflichtprüfung mit belastbarem Nachweis",
                    "Nicht durchgeführt; fehlende Eingaben oder vorausgehende Prüfung.",
                    route="10_QA: Fehlende technische Messung/Nachweise nachholen.",
                )
        checks = [self.checks[name] for name in self.required]
        if any(check["status"] == "nicht_geprueft" for check in checks):
            result = "pruefung_unvollstaendig"
        elif any(check["status"] == "fehlgeschlagen" for check in checks):
            result = "nacharbeit_erforderlich"
        else:
            result = "freigabefaehig"
        return {
            **self.data, "ergebnis": result, "findings": self.findings,
            "pflichtpruefungen": checks,
        }


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _fraction(value: Any) -> Fraction | None:
    try:
        result = Fraction(str(value))
        return result if result > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def _known(value: Any) -> Any:
    return None if value in (None, "", "unknown", "unspecified", "N/A") else value


def _conjunction(values: Iterable[bool | None]) -> bool | None:
    """A measured failure wins over missing evidence in a composite check."""
    missing = False
    for value in values:
        if value is False:
            return False
        missing = missing or value is None
    return None if missing else True


def _equals(value: Any, expected: Any) -> bool | None:
    known = _known(value)
    return known == expected if known is not None else None


def _close(value: Any, expected: float, tolerance: float) -> bool | None:
    number = _number(value)
    return abs(number - expected) <= tolerance if number is not None else None


def _timestamp(frame: dict[str, Any], time_base: Fraction | None) -> float | None:
    for key in ("best_effort_timestamp", "pts"):
        ticks = _integer(frame.get(key))
        if ticks is not None and time_base is not None:
            return float(ticks * time_base)
    for key in ("best_effort_timestamp_time", "pts_time"):
        value = _number(frame.get(key))
        if value is not None:
            return value
    return None


def _frame_duration(frame: dict[str, Any], time_base: Fraction | None) -> float | None:
    for key in ("duration", "pkt_duration"):
        ticks = _integer(frame.get(key))
        if ticks is not None and time_base is not None:
            return float(ticks * time_base)
    for key in ("duration_time", "pkt_duration_time"):
        value = _number(frame.get(key))
        if value is not None:
            return value
    return None


def _run(
    args: list[str], report_dir: Path, name: str, timeout: int,
) -> dict[str, Any]:
    """Persist evidence without retaining an unbounded trace in memory."""
    stdout = report_dir / f"{name}.json" if name in {
        "ffprobe", "frames", "packets",
    } else report_dir / f"{name}.stdout.log"
    stderr = report_dir / f"{name}.log"
    stdout = ensure_contained(report_dir, stdout)
    stderr = ensure_contained(report_dir, stderr)
    result: dict[str, Any] = {
        "argumente": args, "timeout_sekunden": timeout,
        "stdout": str(stdout), "stderr": str(stderr), "returncode": None,
    }
    try:
        with stdout.open("wb") as output, stderr.open("wb") as errors:
            completed = subprocess.run(
                args, stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                timeout=timeout, check=False,
            )
        result["returncode"] = completed.returncode
        result["status"] = "bestanden" if completed.returncode == 0 else "fehlgeschlagen"
    except subprocess.TimeoutExpired:
        result.update(status="nicht_geprueft", problem="Zeitlimit überschritten.")
    except OSError as exc:
        result.update(status="nicht_geprueft", problem=str(exc))
    return result


def _verdict(run: dict[str, Any]) -> bool | None:
    return {"bestanden": True, "fehlgeschlagen": False}.get(run["status"])


def _load_json(run: dict[str, Any]) -> dict[str, Any] | None:
    if _verdict(run) is not True:
        return None
    try:
        value = json.loads(Path(run["stdout"]).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _tail(path: str, limit: int = 6000) -> str:
    try:
        with Path(path).open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - limit))
            return handle.read(limit).decode("utf-8", errors="replace")
    except OSError:
        return "Protokoll nicht lesbar."


def _mp4_layout(path: Path) -> dict[str, Any]:
    """Read top-level ISO-BMFF boxes, including extended and zero sizes."""
    boxes: list[dict[str, Any]] = []
    brands: list[str] = []
    length = path.stat().st_size
    with path.open("rb") as handle:
        offset = 0
        while offset < length:
            handle.seek(offset)
            header = handle.read(8)
            if len(header) != 8:
                raise ValueError("Unvollständiger MP4-Boxheader.")
            size, kind = struct.unpack(">I4s", header)
            header_size = 8
            if size == 1:
                extra = handle.read(8)
                if len(extra) != 8:
                    raise ValueError("Unvollständige 64-Bit-MP4-Boxgröße.")
                size = struct.unpack(">Q", extra)[0]
                header_size = 16
            elif size == 0:
                size = length - offset
            if size < header_size or offset + size > length:
                raise ValueError("MP4-Boxgröße reicht über das Dateiende.")
            label = kind.decode("latin-1")
            boxes.append({"typ": label, "offset": offset, "groesse": size})
            if kind == b"ftyp":
                payload_size = size - header_size
                if payload_size < 8 or payload_size > 65536 or payload_size % 4:
                    raise ValueError("Ungültiger MP4-ftyp-Block.")
                payload = handle.read(payload_size)
                brands = [payload[:4].decode("latin-1")] + [
                    payload[index:index + 4].decode("latin-1")
                    for index in range(8, len(payload), 4)
                ]
            offset += size
    moov = [box["offset"] for box in boxes if box["typ"] == "moov"]
    mdat = [box["offset"] for box in boxes if box["typ"] == "mdat"]
    mp4_brands = {"isom", "iso2", "iso3", "iso4", "iso5", "iso6", "avc1", "mp41", "mp42", "M4V ", "dash"}
    return {
        "boxen": boxes, "brands": brands,
        "mp4": bool(set(brands) & mp4_brands),
        "faststart": len(moov) == 1 and bool(mdat) and moov[0] < min(mdat),
    }


def _frame_metrics(frames: list[dict[str, Any]], stream: dict[str, Any]) -> dict[str, Any]:
    time_base = _fraction(stream.get("time_base"))
    tick = float(time_base) if time_base else 0.000001
    tolerance = max(tick / 2, 0.000001)
    times = [_timestamp(frame, time_base) for frame in frames]
    complete = bool(frames) and all(time is not None for time in times)
    metrics: dict[str, Any] = {
        "framezahl": len(frames), "timestamp_vollstaendig": complete,
        "zeitbasis": str(time_base) if time_base else None,
        "timestamp_toleranz_s": tolerance,
    }
    known_times = [(index, time) for index, time in enumerate(times) if time is not None]
    deviation = None
    raster_wrong = False
    if len(known_times) >= 2:
        anchor_index, anchor_time = known_times[0]
        deviation = max(abs(time - anchor_time - (index - anchor_index) / FPS)
                        for index, time in known_times)
        # A missing first timestamp also leaves its quantized phase unknown.
        raster_tolerance = tolerance if anchor_index == 0 else 2 * tolerance
        raster_wrong = deviation > raster_tolerance + 1e-9 or any(
            right[1] <= left[1] for left, right in zip(known_times, known_times[1:])
        )
    first = times[0] if times else None
    last = times[-1] if times else None
    last_duration = _frame_duration(frames[-1], time_base) if frames else None
    endpoint = last + last_duration if last is not None and last_duration is not None else None
    deltas = [right - left for left, right in zip(times, times[1:])
              if left is not None and right is not None]
    metrics.update(
        start_s=first, letzter_frame_s=last, letzter_frame_dauer_s=last_duration,
        ende_s=endpoint, dauer_s=endpoint - first if endpoint is not None and first is not None else None,
        max_abweichung_vom_30fps_raster_s=deviation,
        min_frame_abstand_s=min(deltas) if deltas else None,
        max_frame_abstand_s=max(deltas) if deltas else None,
        cfr=False if raster_wrong else (True if complete and len(frames) >= 2 else None),
    )
    key_indices = [index for index, frame in enumerate(frames) if frame.get("key_frame") == 1]
    key_gaps = [right - left for left, right in zip(key_indices, key_indices[1:])]
    if key_indices:
        key_gaps.append(len(frames) - key_indices[-1])
    key_complete = bool(frames) and all(frame.get("key_frame") in (0, 1) for frame in frames)
    zero_run = longest_zero_run = 0
    for frame in frames:
        zero_run = zero_run + 1 if frame.get("key_frame") == 0 else 0
        longest_zero_run = max(longest_zero_run, zero_run)
    metrics.update(
        keyframe_indices=key_indices, gop_max_frames=max(key_gaps) if key_gaps and key_complete else None,
        max_bekannte_nicht_keyframe_folge=longest_zero_run,
        gop_bekannt_zu_lang=longest_zero_run >= 60,
        erster_frame_key=_equals(frames[0].get("key_frame"), 1) if frames else None,
        gop_nachweis_vollstaendig=key_complete and bool(key_indices) and key_indices[0] == 0,
    )
    run = maximum = 0
    for frame in frames:
        run = run + 1 if frame.get("pict_type") == "B" else 0
        maximum = max(maximum, run)
    metrics["max_aufeinanderfolgende_b_frames"] = maximum
    metrics["bildtypen_vollstaendig"] = bool(frames) and all(
        frame.get("pict_type") in {"I", "P", "B"} for frame in frames
    )
    return metrics


def _packet_metrics(packets: list[dict[str, Any]]) -> dict[str, Any] | None:
    samples: list[tuple[float, float, int]] = []
    for packet in packets:
        timestamp = _number(packet.get("dts_time"))
        duration = _number(packet.get("duration_time"))
        size = _integer(packet.get("size"))
        if timestamp is None or duration is None or duration <= 0 or size is None or size < 0:
            return None
        samples.append((timestamp, duration, size))
    if not samples or any(right[0] <= left[0] for left, right in zip(samples, samples[1:])):
        return None
    pending: deque[tuple[float, int]] = deque()
    current = maximum = 0
    for timestamp, _, size in samples:
        while pending and timestamp - pending[0][0] >= 1 - 1e-9:
            current -= pending.popleft()[1]
        pending.append((timestamp, size))
        current += size
        maximum = max(maximum, current)
    coverage = samples[-1][0] + samples[-1][1] - samples[0][0]
    return {
        "paketzahl": len(samples), "zeitspanne_s": coverage,
        "mittelwert_bit_s": sum(size for _, _, size in samples) * 8 / coverage,
        "max_1s_fenster_bit_s": maximum * 8,
        "methode": "Video-Nutzdaten in gleitenden halboffenen 1-s-DTS-Fenstern; ohne Container/Audio.",
        "grenze": "Misst Paketlast; ersetzt keinen Nachweis des Encoder-VBV/HRD-Limits.",
    }


def _packet_data_verdict(packets: list[dict[str, Any]]) -> bool | None:
    evidence: list[bool | None] = [True if packets else None]
    times = []
    for packet in packets:
        timestamp = _number(packet.get("dts_time"))
        duration = _number(packet.get("duration_time"))
        size = _integer(packet.get("size"))
        evidence.extend((True if timestamp is not None else None,
                         duration > 0 if duration is not None else None,
                         size >= 0 if size is not None else None))
        if timestamp is not None:
            times.append(timestamp)
    evidence.append(all(right > left for left, right in zip(times, times[1:])))
    return _conjunction(evidence)


def _packet_peak(packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Known packets provide a lower bound even if another packet is unknown."""
    samples = []
    complete = bool(packets)
    maximum = 0
    for packet in packets:
        timestamp = _number(packet.get("dts_time"))
        size = _integer(packet.get("size"))
        valid_size = size is not None and size >= 0
        if valid_size:
            maximum = max(maximum, size)
        if timestamp is not None and valid_size:
            samples.append((timestamp, size))
        else:
            complete = False
    pending: deque[tuple[float, int]] = deque()
    current = 0
    for timestamp, size in sorted(samples):
        while pending and timestamp - pending[0][0] >= 1 - 1e-9:
            current -= pending.popleft()[1]
        pending.append((timestamp, size))
        current += size
        maximum = max(maximum, current)
    bits = maximum * 8
    return {
        "max_1s_fenster_bit_s": bits if complete else None,
        "belegte_untergrenze_max_1s_bit_s": bits,
        "vollstaendig": complete,
        "limit_ok": False if bits > 16_000_000 else (True if complete else None),
        "methode": "Gleitende halboffene 1-s-DTS-Fenster; bei fehlenden DTS/Größen nur belegte Untergrenze aus bekannten Paketen.",
    }


def _parse_trace(path: Path) -> dict[str, Any]:
    packets: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    payload = bytearray()
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "Packet:" in line and "trace_headers" in line:
                if current is not None:
                    packets.append(current)
                match = re.search(r"\bpts (-?\d+)", line)
                current = {"key": "key frame" in line, "pts": int(match[1]) if match else None, "nal_types": []}
            match = re.search(r"\bnal_unit_type\s+\S+\s*=\s*(\d+)\s*$", line)
            if match and current is not None:
                current["nal_types"].append(int(match[1]))
            match = re.search(r"\buser_data_payload_byte(?:\[\d+\])?\s+\S+\s*=\s*(\d+)\s*$", line)
            if match and len(payload) < 65536:
                value = int(match[1])
                if value <= 255:
                    payload.append(value)
    if current is not None:
        packets.append(current)
    text = payload.decode("latin-1")
    settings: dict[str, int] = {}
    if "x264" in text and "options:" in text:
        options = text.split("options:", 1)[1]
        for key in ("bitrate", "vbv_maxrate", "bframes", "open_gop"):
            match = re.search(rf"(?:^|\s){key}=(\d+)(?=\s|\x00)", options)
            if match:
                settings[key] = int(match[1])
    return {"packets": packets, "x264_exportsettings": settings}


def _closed_gop(trace: dict[str, Any], frames: list[dict[str, Any]]) -> bool | None:
    packets = trace.get("packets", [])
    by_pts: dict[int, list[dict[str, Any]]] = {}
    for packet in packets:
        if packet.get("pts") is not None:
            by_pts.setdefault(packet["pts"], []).append(packet)
    # A known non-IDR random-access packet cannot be hidden by a later gap.
    if any(packet.get("key") and 1 in packet.get("nal_types", []) for packet in packets):
        return False
    intra = [frame for frame in frames if frame.get("pict_type") == "I"]
    decisions: list[bool | None] = []
    for frame in intra:
        pts = _integer(frame.get("pts"))
        if pts is None:
            pts = _integer(frame.get("best_effort_timestamp"))
        matching = by_pts.get(pts, []) if pts is not None else []
        if not matching:
            decisions.append(None)
        for packet in matching:
            nal_types = set(packet.get("nal_types", []))
            decisions.append(False if 1 in nal_types else (True if 5 in nal_types else None))
    complete = bool(intra) and len(packets) == len(frames) and len(by_pts) == len(frames) and all(
        frame.get("pict_type") in {"I", "P", "B"} for frame in frames
    )
    return _conjunction([*decisions, True if complete else None])


def _b_frames_verdict(metrics: dict[str, Any], reorder: int | None, configured: int | None) -> bool | None:
    observed = metrics.get("max_aufeinanderfolgende_b_frames")
    evidence = [observed <= 2 if observed is not None else None,
                True if metrics.get("bildtypen_vollstaendig") else None]
    if configured is not None:
        evidence.append(_equals(configured, 2))
    else:
        evidence.extend((_equals(reorder, 2), True if observed == 2 else None))
    return _conjunction(evidence)


def _loudness(path: Path) -> dict[str, Any] | None:
    log = _tail(str(path), 16000)
    if "Summary:" not in log:
        return None
    summary = log.rsplit("Summary:", 1)[1]

    def measurement(pattern: str) -> float | None:
        match = re.search(pattern, summary)
        if match:
            try:
                value = float(match[1])
                return value if not math.isnan(value) else None
            except ValueError:
                pass
        return None

    integrated = measurement(r"Integrated loudness:\s*I:\s*([-+\w.]+)\s*LUFS")
    peak = measurement(r"True peak:\s*Peak:\s*([-+\w.]+)\s*dBFS")
    if integrated is None and peak is None:
        return None

    def serializable(value: float | None) -> float | str | None:
        return value if value is None or math.isfinite(value) else str(value)

    return {
        "integriert_lufs": serializable(integrated), "true_peak_dbtp": serializable(peak),
        "loudness_ok": -15 <= integrated <= -13 if integrated is not None else None,
        "peak_ok": peak <= -1.5 if peak is not None else None,
        "methode": "ffmpeg ebur128=peak=true, gesamter erster Audiostream, keine Normalisierung.",
    }


def _disclaimer_measurements(path: Path) -> dict[str, Any]:
    log = path.read_text(encoding="utf-8", errors="replace")
    silence_starts = [float(value) for value in re.findall(r"silence_start:\s*([-\d.e+]+)", log)]
    silence_ends = [float(value) for value in re.findall(r"silence_end:\s*([-\d.e+]+)", log)]
    black = [{"start_lokal_s": float(start), "ende_lokal_s": float(end), "dauer_s": float(duration)}
             for start, end, duration in re.findall(
                 r"black_start:([\d.e+-]+)\s+black_end:([\d.e+-]+)\s+black_duration:([\d.e+-]+)", log)]
    return {
        "fenster_start_s": 54, "fenster_ende_s": 58,
        "stille_schwelle_dbfs": -60, "stille_start_lokal_s": silence_starts,
        "stille_ende_lokal_s": silence_ends,
        "durchgehend_still": bool(silence_starts and silence_ends
                                  and silence_starts[0] <= 1 / 48000 + 0.000001
                                  and silence_ends[-1] >= 4 - 1 / 48000 - 0.000001
                                  and len(silence_starts) == len(silence_ends) == 1),
        "schwarz_intervalle": black,
        "schwarz_schwellen": {"pixel": 0.02, "bildanteil": 0.98, "mindestdauer_s": 0.02},
        "grenze": "Detektoren erkennen Stille/nahezu schwarze Bilder, nicht Disclaimertext, Lesbarkeit oder beabsichtigte Gestaltung.",
    }


def _probe_stream(qa: _QA, video: dict[str, Any], audio: dict[str, Any]) -> None:
    rates = [_fraction(video.get(key)) for key in ("r_frame_rate", "avg_frame_rate")]
    qa.check("fps_30", _conjunction(_equals(rate, 30) for rate in rates),
             "r_frame_rate und avg_frame_rate = 30/1; zusätzlich tatsächliche Frame-Zeitstempel",
             {key: video.get(key) for key in ("r_frame_rate", "avg_frame_rate")})
    profile = [_known(video.get(key)) for key in ("codec_name", "profile", "level")]
    profile_expected = ["h264", "High", 41]
    profile_ok = _conjunction(_equals(value, expected) for value, expected in zip(profile, profile_expected))
    qa.check("h264_high_level_4_1", profile_ok,
             "H.264, Profil High, Level 4.1 (41)", profile)
    rotations = [side.get("rotation") for side in video.get("side_data_list", []) if "rotation" in side]
    if "rotate" in video.get("tags", {}):
        rotations.append(video["tags"]["rotate"])
    angles = [_number(value) for value in rotations]
    qa.check("rotation_0", _conjunction(_equals(angle, 0) for angle in angles),
             "Keine Drehung der codierten 1080×1920-Bilder", rotations)
    for name, key, expected in (
        ("aac_lc", "profile", "LC"), ("audio_48000_hz", "sample_rate", 48000),
        ("audio_stereo", "channels", 2),
    ):
        value = audio.get(key)
        if key in {"sample_rate", "channels"}:
            value = _integer(value)
        if name == "aac_lc":
            codec = _known(audio.get("codec_name"))
            known = _known(value)
            passed = _conjunction((_equals(codec, "aac"), _equals(known, expected)))
            actual: Any = {"codec": codec, "profil": value}
        elif name == "audio_stereo":
            layout = _known(audio.get("channel_layout"))
            passed = _conjunction((_equals(value, 2), _equals(layout, "stereo")))
            actual = {"kanaele": value, "layout": layout}
        else:
            passed, actual = value == expected if value is not None else None, value
        qa.check(name, passed, expected if name != "audio_stereo" else "2 Kanäle, Layout stereo", actual)
    start, duration = _number(audio.get("start_time")), _number(audio.get("duration"))
    qa.check("audio_abdeckung_58s", _conjunction((_close(start, 0, 0.001), _close(duration, 58, 0.001))),
             "Audiopräsentation von 0 bis 58 s (1 ms Messauflösung)", {"start_s": start, "dauer_s": duration})
    qa.check("audio_bitrate_ziel_384kbps", None, "Belegte Encoder-Zielkonfiguration AAC 384 kbit/s",
             {"gemittelte_stream_bitrate_bit_s": audio.get("bit_rate"), "nachweis": "AAC enthält keinen verlässlichen Nachweis der Encoder-Zielbitrate."},
             route="10_QA: Technischer Experte belegt Export-Ziel384kbit/s für genau diesen Dateihash mit Exportsettings.")


def _check_frames(qa: _QA, frames: list[dict[str, Any]], video: dict[str, Any], container: dict[str, Any]) -> dict[str, Any]:
    metrics = _frame_metrics(frames, video)
    qa.data["technischer_report"]["frames"] = metrics
    qa.check("framezahl_1740", len(frames) == VIDEO_FRAMES, VIDEO_FRAMES, len(frames))
    qa.check("frame_timestamps_cfr", metrics.get("cfr"),
             "Alle präsentierten Frames monoton auf dem 30-fps-Raster; Toleranz höchstens halber Zeitbasistick",
             metrics)
    duration = metrics.get("dauer_s")
    declared = [_number(video.get("duration")), _number(container.get("duration"))]
    tolerance = metrics["timestamp_toleranz_s"] + 1e-9
    passed = _conjunction(_close(value, VIDEO_SECONDS, tolerance)
                          for value in [duration, metrics.get("ende_s"), *declared])
    qa.check("dauer_58s", passed, "58 s aus letztem Frame-Ende, Videostream und Container",
             {"gemessen_s": duration, "letzter_frame_ende_s": metrics.get("ende_s"), "stream_container_s": declared, "toleranz_s": tolerance})
    start = metrics.get("start_s")
    stream_start = _number(video.get("start_time"))
    qa.check("start_bei_null", _conjunction((_close(start, 0, tolerance), _close(stream_start, 0, tolerance) if stream_start is not None else True)),
             "Erster Video-Präsentationszeitstempel 0 s", {"frame_start_s": start, "stream_start_s": stream_start})
    dimensions = {(frame.get("width"), frame.get("height")) for frame in frames}
    metadata_dims = (video.get("width"), video.get("height"))
    dimension_checks = [_equals(width, 1080) for width, _ in [metadata_dims, *dimensions]]
    dimension_checks += [_equals(height, 1920) for _, height in [metadata_dims, *dimensions]]
    qa.check("aufloesung_1080x1920", _conjunction([*dimension_checks, True if frames else None]),
             "1080×1920 in Metadaten und jedem decodierten Frame", {"stream": metadata_dims, "frames": sorted(dimensions, key=str)})
    frame_sars = {_known(frame.get("sample_aspect_ratio")) for frame in frames}
    stream_sar = _known(video.get("sample_aspect_ratio"))
    qa.check("sar_1_1", _conjunction([_equals(value, "1:1") for value in [stream_sar, *frame_sars]] + [True if frames else None]),
             "SAR 1:1 im Stream und in jedem Frame", {"stream": stream_sar, "frames": sorted(frame_sars, key=str)})
    field = _known(video.get("field_order"))
    fields = {_known(frame.get("interlaced_frame")) for frame in frames}
    qa.check("progressiv", _conjunction([_equals(field, "progressive"), *[_equals(value, 0) for value in fields], True if frames else None]),
             "field_order=progressive; interlaced_frame=0 in jedem Frame", {"stream": field, "frames": sorted(fields, key=str)})
    formats = {_known(frame.get("pix_fmt")) for frame in frames}
    metadata_format = _known(video.get("pix_fmt"))
    qa.check("yuv420p", _conjunction([_equals(value, "yuv420p") for value in [metadata_format, *formats]] + [True if frames else None]),
             "8-Bit yuv420p in Stream und allen Frames", {"stream": metadata_format, "frames": sorted(formats, key=str)})
    colors = {key: {"stream": video.get(key), "frames": sorted({frame.get(key) for frame in frames}, key=str)}
              for key in ("color_primaries", "color_transfer", "color_space")}
    color_values = [value for entry in colors.values() for value in [entry["stream"], *entry["frames"]]]
    known_colors = bool(frames) and all(_known(value) is not None for value in color_values)
    hdr_side_data = [entry.get("side_data_type", "") for frame in frames for entry in frame.get("side_data_list", [])
                     if any(word in entry.get("side_data_type", "").lower() for word in ("mastering display", "content light", "dovi", "hdr"))]
    wrong_colors = any(_known(value) is not None and value != "bt709" for value in color_values)
    qa.check("sdr_bt709", False if wrong_colors or hdr_side_data else (True if known_colors else None),
             "SDR: Primärfarben, Transfer und Matrix BT.709; keine HDR-Sidedata", {"farben": colors, "hdr_sidedata": sorted(set(hdr_side_data))})
    qa.check("gop_max_60", _conjunction((
        metrics["erster_frame_key"], not metrics["gop_bekannt_zu_lang"],
        metrics["gop_max_frames"] <= 60 if metrics["gop_nachweis_vollstaendig"] else None,
    )), "Erster Frame Keyframe; Keyframe-Abstände und letzter GOP höchstens 60 Frames",
        {"max_frames": metrics["gop_max_frames"], "max_bekannte_nicht_keyframe_folge": metrics["max_bekannte_nicht_keyframe_folge"], "erster_frame_key": metrics["erster_frame_key"]})
    return metrics


def inspect_video(path: Path, report_dir: Path) -> dict[str, Any]:
    """Inspect the existing video and write ``report.json`` plus raw evidence.

    ``freigabefaehig`` is technical eligibility, never a release decision.
    An unavailable mandatory check has priority over known failures in the
    summary; every measured failure remains visible and cannot be overridden.
    """
    path = Path(path).resolve()
    report_dir = ensure_contained(Path(report_dir), Path(report_dir))
    qa = _QA(path, VIDEO_CHECKS)
    qa.data["menschliche_pruefungen"] = [
        {"name": "disclaimer_semantik_und_layout", "status": "ausstehend", "soll": "54–58 s: vollständiger lesbarer Disclaimer, korrekter Inhalt/Gestaltung und beabsichtigtes Audio."},
        {"name": "sicht_und_hoerpruefung", "status": "ausstehend", "soll": "Kompletter Film: Bild-/Tonfehler, Quellen, Overlays, Rechte, medizinische/juristische Inhalte."},
    ]
    qa.data["grenzen"] = [
        "Keine semantische, medizinische, juristische oder Rechtefreigabe; keine Änderungen oder Reencodierung.",
        "BT.709/Progressiv werden an Deklaration und sämtlichen Frames geprüft; fehlerhaft deklarierte Bildinhalte brauchen Sichtprüfung.",
        "1-s-Paketlast belegt keine VBV/HRD-Encoderkonfiguration. VBR-Mittelwerte belegen keine Zielbitrate.",
        "Closed GOP wird nur belegt, wenn jeder decodierte I-Frame einem IDR-Access-Unit des vollständigen H.264-Traces entspricht.",
    ]
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
        names = ["report.json", *[f"{name}.{suffix}" for name in
                 ("ffprobe", "frames", "packets", "decode", "loudness", "disclaimer", "h264_headers")
                 for suffix in ("json", "log", "stdout.log")]]
        for name in names:
            destination = ensure_contained(report_dir, report_dir / name)
            if destination.resolve() == path or (destination.exists() and path.exists() and destination.samefile(path)):
                raise OSError("Berichtspfad würde die Quelldatei überschreiben; separaten report_dir wählen.")
        with tempfile.NamedTemporaryFile(dir=report_dir, delete=True):
            pass
    except (OSError, Blocked) as exc:
        qa.check("berichte_gespeichert", None, "Persistierte Messprotokolle und report.json", str(exc), route="10_QA: Schreibbaren Berichtspfad bereitstellen.")
        return qa.finish()
    try:
        initial_hash = _sha256(path)
        qa.data["datei_sha256"] = initial_hash
        qa.check("datei_lesbar", True, "Lesbare unveränderte Quelldatei", str(path))
    except OSError as exc:
        qa.check("datei_lesbar", False, "Lesbare Quelldatei", str(exc), severity="K0")
        return _save_report(qa, report_dir)
    try:
        layout = _mp4_layout(path)
        qa.data["technischer_report"]["mp4"] = layout
        qa.check("container_mp4", layout["mp4"], "MP4/ISO-BMFF mit MP4-kompatiblem ftyp", layout["brands"])
        qa.check("mp4_faststart", layout["faststart"], "Ein moov-Block vor allen mdat-Blöcken", layout["boxen"])
    except (OSError, ValueError) as exc:
        qa.check("container_mp4", False, "Lesbarer MP4/ISO-BMFF-Container", str(exc))
        qa.check("mp4_faststart", None, "moov vor mdat", "Kein vollständig lesbarer MP4-Boxbaum.")
    runs: dict[str, Any] = {}
    qa.data["technischer_report"]["prozesse"] = runs
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    video: dict[str, Any] = {}
    audio: dict[str, Any] = {}
    frames: list[dict[str, Any]] = []
    if ffprobe:
        runs["ffprobe"] = _run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], report_dir, "ffprobe", PROBE_TIMEOUT)
        probe = _load_json(runs["ffprobe"])
        qa.check("ffprobe", _verdict(runs["ffprobe"]) if probe is not None or _verdict(runs["ffprobe"]) is not True else None,
                 "Vollständige lesbare ffprobe-JSON-Metadaten", {**runs["ffprobe"], "diagnose": _tail(runs["ffprobe"]["stderr"])})
        if probe is not None:
            qa.data["technischer_report"]["streams"] = probe.get("streams", [])
            qa.data["technischer_report"]["format"] = probe.get("format", {})
            streams = [stream for stream in probe.get("streams", []) if isinstance(stream, dict)]
            videos = [stream for stream in streams if stream.get("codec_type") == "video"]
            audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
            qa.check("videostream", len(videos) == 1, "Genau ein Videostream", len(videos))
            qa.check("audiostream", len(audios) == 1, "Genau ein Audiostream", len(audios))
            video = videos[0] if videos else {}
            audio = audios[0] if audios else {}
            _probe_stream(qa, video, audio)
            if video:
                frame_fields = "best_effort_timestamp,best_effort_timestamp_time,pts,pts_time,duration,duration_time,pkt_duration,pkt_duration_time,key_frame,pict_type,interlaced_frame,width,height,sample_aspect_ratio,pix_fmt,color_space,color_primaries,color_transfer,side_data_list"
                runs["frames"] = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", f"frame={frame_fields}", "-of", "json", str(path)], report_dir, "frames", PROBE_TIMEOUT)
                frame_json = _load_json(runs["frames"])
                raw_frames = frame_json.get("frames") if frame_json else None
                frame_structure_valid = isinstance(raw_frames, list) and all(isinstance(frame, dict) for frame in raw_frames)
                frames = raw_frames if frame_structure_valid else []
                qa.check("frame_daten", bool(frames) if frame_structure_valid else (_verdict(runs["frames"]) if _verdict(runs["frames"]) is not True else None),
                         "Frame-für-Frame-Daten des vollständigen ersten Videostreams", {"framezahl": len(frames), "prozess": runs["frames"]})
                if frame_structure_valid:
                    _check_frames(qa, frames, video, probe.get("format", {}))
                runs["packets"] = _run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_entries", "packet=dts_time,pts_time,duration_time,size,flags", "-of", "json", str(path)], report_dir, "packets", PROBE_TIMEOUT)
                packet_json = _load_json(runs["packets"])
                packets = packet_json.get("packets") if packet_json else None
                packet_structure_valid = isinstance(packets, list) and all(isinstance(packet, dict) for packet in packets)
                metrics = _packet_metrics(packets) if packet_structure_valid else None
                qa.check("video_packet_daten", _packet_data_verdict(packets) if packet_structure_valid else (_verdict(runs["packets"]) if _verdict(runs["packets"]) is not True else None),
                         "Alle Video-Pakete mit DTS, Dauer und tatsächlicher Nutzdatengröße", runs["packets"])
                if packet_structure_valid:
                    peak = _packet_peak(packets)
                    qa.data["technischer_report"]["video_bitrate"] = {**(metrics or {}), **peak}
                    qa.check("video_bitrate_max_16mbps", peak["limit_ok"],
                             "Video-Nutzdaten ≤16 Mbit in jedem gleitenden halboffenen 1-s-Fenster", qa.data["technischer_report"]["video_bitrate"])
    else:
        qa.check("ffprobe", None, "Installiertes ffprobe", "ffprobe nicht gefunden.", route="10_QA: ffmpeg/ffprobe installieren und Messung wiederholen.")
    if ffmpeg:
        base = [ffmpeg, "-hide_banner", "-nostdin"]
        runs["decode"] = _run(base + ["-v", "error", "-xerror", "-err_detect", "explode", "-threads", "1", "-i", str(path), "-map", "0:v?", "-map", "0:a?", "-f", "null", "-"], report_dir, "decode", DECODE_TIMEOUT)
        decode_ok = _verdict(runs["decode"])
        if Path(runs["decode"]["stderr"]).is_file() and Path(runs["decode"]["stderr"]).stat().st_size:
            decode_ok = False
        qa.check("vollstaendiger_decode", decode_ok, "Vollständige Bild-/Audiodecodierung ohne Decoderfehler; -xerror -err_detect explode",
                 {**runs["decode"], "diagnose": _tail(runs["decode"]["stderr"])}, severity="K0")
        if video.get("codec_name") == "h264":
            runs["h264_headers"] = _run(base + ["-loglevel", "info", "-i", str(path), "-map", "0:v:0", "-an", "-c:v", "copy", "-bsf:v", "trace_headers", "-f", "null", "-"], report_dir, "h264_headers", FILTER_TIMEOUT)
            trace_complete = _verdict(runs["h264_headers"]) is True
            if Path(runs["h264_headers"]["stderr"]).is_file():
                trace = _parse_trace(Path(runs["h264_headers"]["stderr"]))
                settings = trace["x264_exportsettings"]
                qa.data["technischer_report"]["h264"] = {
                    "trace_paketzahl": len(trace["packets"]), "trace_vollstaendig": trace_complete, "x264_exportsettings": settings,
                    "idr_access_units": sum(5 in packet["nal_types"] for packet in trace["packets"]),
                }
                open_gop = settings.get("open_gop")
                qa.check("gop_geschlossen", _conjunction((
                    _closed_gop(trace, frames), True if trace_complete else None,
                    _equals(open_gop, 0) if open_gop is not None else True,
                )),
                         "Jeder I-Frame entspricht einer IDR-Access-Unit (NAL 5), keine Nicht-IDR-Intra-GOPs", qa.data["technischer_report"]["h264"])
                target = settings.get("bitrate")
                qa.check("video_bitrate_ziel_10mbps", target == 10000 if target is not None else None,
                         "Belegte Encoder-Zielbitrate 10000 kbit/s", {"eingebettete_x264_zielbitrate_kbit_s": target, "nachweis": "H.264-SEI-Encoderangabe" if target is not None else "Keine belegbare Encoder-Zielkonfiguration im Output."},
                         route="10_QA: Technischer Experte belegt Export-Ziel10Mbit/s für genau diesen Dateihash mit Exportsettings.")
                ceiling = settings.get("vbv_maxrate")
                qa.check("video_bitrate_max_konfiguration", 0 < ceiling <= 16000 if ceiling is not None else None,
                         "Belegte Encoder-VBV/HRD-Obergrenze ≤16000 kbit/s",
                         {"eingebettete_x264_vbv_maxrate_kbit_s": ceiling, "nachweis": "H.264-SEI-Encoderangabe" if ceiling is not None else "1-s-Paketmessung beweist keine Encoder-Obergrenze."},
                         route="10_QA: Technischer Experte belegt max16Mbit/s-Exportlimit für genau diesen Dateihash mit Exportsettings.")
        if audio:
            runs["loudness"] = _run(base + ["-loglevel", "info", "-i", str(path), "-map", "0:a:0", "-vn", "-af", "ebur128=peak=true:framelog=verbose", "-f", "null", "-"], report_dir, "loudness", FILTER_TIMEOUT)
            measured = _loudness(Path(runs["loudness"]["stderr"])) if _verdict(runs["loudness"]) is True else None
            qa.data["technischer_report"]["audio_messung"] = measured
            qa.check("audio_loudness", measured["loudness_ok"] if measured is not None else None,
                     "Integrierte Lautheit −15 bis −13 LUFS", measured or runs["loudness"])
            qa.check("audio_true_peak", measured["peak_ok"] if measured is not None else None,
                     "True Peak ≤−1,5 dBTP", measured or runs["loudness"])
        frame_duration = qa.data["technischer_report"].get("frames", {}).get("dauer_s")
        if video and audio and frame_duration is not None and frame_duration >= 58 - 0.000001:
            runs["disclaimer"] = _run(base + ["-loglevel", "info", "-threads", "1", "-ss", "54", "-i", str(path), "-t", "4", "-map", "0:v:0", "-map", "0:a:0", "-vf", "blackdetect=d=0.02:pix_th=0.02:pic_th=0.98", "-af", "silencedetect=noise=-60dB:d=0.02", "-f", "null", "-"], report_dir, "disclaimer", FILTER_TIMEOUT)
            if _verdict(runs["disclaimer"]) is True:
                qa.data["technischer_report"]["disclaimer"] = _disclaimer_measurements(Path(runs["disclaimer"]["stderr"]))
            qa.check("disclaimer_messung_54_bis_58s", _verdict(runs["disclaimer"]),
                     "Technische Stille-/Schwarzbildmessung des Fensters 54–58 s; Gestaltung menschlich bewerten", qa.data["technischer_report"].get("disclaimer", runs["disclaimer"]))
            disclaimer = qa.data["technischer_report"].get("disclaimer")
            qa.check("disclaimer_audio_stille", disclaimer["durchgehend_still"] if disclaimer else None,
                     "54–58 s durchgehend still (Detektor −60 dBFS); keine Stimme/Musik", disclaimer or runs["disclaimer"])
        elif frame_duration is not None and frame_duration < 58 - 0.000001:
            qa.check("disclaimer_messung_54_bis_58s", False, "Vollständiges Disclaimerfenster 54–58 s", {"videodauer_s": frame_duration})
            qa.check("disclaimer_audio_stille", None, "Stille im vollständigen Fenster 54–58 s", "Videofenster fehlt.")
    else:
        qa.check("vollstaendiger_decode", None, "Installiertes ffmpeg für vollständige Decodierung", "ffmpeg nicht gefunden.", severity="K0", route="10_QA: ffmpeg installieren und Messung wiederholen.")
    if video.get("codec_name") == "h264":
        frame_metrics = qa.data["technischer_report"].get("frames", {})
        settings = qa.data["technischer_report"].get("h264", {}).get("x264_exportsettings", {})
        configured = settings.get("bframes")
        reorder = _integer(video.get("has_b_frames"))
        qa.check("b_frames_2", _b_frames_verdict(frame_metrics, reorder, configured),
                 "Encoder maximal 2 B-Frames; tatsächlich keine Folge >2; ohne Exportsettings nur beobachtbare Evidenz",
                 {"export_max_b_frames": configured, "decoder_reorder_frames": reorder,
                  "max_beobachtete_b_folge": frame_metrics.get("max_aufeinanderfolgende_b_frames")})
    try:
        final_hash = _sha256(path)
        qa.check("datei_unveraendert", initial_hash == final_hash, initial_hash, final_hash, severity="K0")
    except OSError as exc:
        qa.check("datei_unveraendert", None, initial_hash, str(exc), severity="K0")
    return _save_report(qa, report_dir)


def _save_report(qa: _QA, report_dir: Path) -> dict[str, Any]:
    report_path = ensure_contained(report_dir, report_dir / "report.json")
    qa.data["bericht_pfad"] = str(report_path)
    qa.check("berichte_gespeichert", True, "Messprotokolle und report.json gespeichert", str(report_dir))
    result = qa.finish()
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=report_dir, prefix=".report-", suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, report_path)
    except OSError as exc:
        qa.check("berichte_gespeichert", None, "Persistierter report.json", str(exc), route="10_QA: Schreibfehler beheben und Prüfung vollständig wiederholen.")
        result = qa.finish()
    finally:
        if temporary:
            try:
                Path(temporary).unlink(missing_ok=True)
            except OSError:
                pass
    return result


_SRT_TIME = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2,}):([0-5]\d):([0-5]\d),(\d{3})$")


def _parse_srt(text: str) -> list[dict[str, Any]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized.strip():
        raise ValueError("SRT enthält keine Cues.")
    cues = []
    for position, block in enumerate(re.split(r"\n[ \t]*\n", normalized), 1):
        lines = block.split("\n")
        if len(lines) < 3 or not lines[0].isdigit() or int(lines[0]) != position:
            raise ValueError(f"Cue {position}: fortlaufende Nummer und Text erforderlich.")
        match = _SRT_TIME.fullmatch(lines[1])
        if not match:
            raise ValueError(f"Cue {position}: Zeitformat HH:MM:SS,mmm --> HH:MM:SS,mmm erforderlich.")
        values = [int(value) for value in match.groups()]
        start_ms = ((values[0] * 60 + values[1]) * 60 + values[2]) * 1000 + values[3]
        end_ms = ((values[4] * 60 + values[5]) * 60 + values[6]) * 1000 + values[7]
        if end_ms <= start_ms or not all(line.strip() for line in lines[2:]):
            raise ValueError(f"Cue {position}: positive Dauer und nichtleere Textzeilen erforderlich.")
        cues.append({"nummer": position, "start_ms": start_ms, "ende_ms": end_ms,
                     "zeilen": lines[2:], "dauer_s": (end_ms - start_ms) / 1000})
    return cues


def _load_montserrat(font_path: Path | str | None) -> tuple[Any, Path]:
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise ValueError("Pillow fehlt; keine reale Pixelbreitenmessung möglich.") from exc
    candidate = Path(font_path).expanduser() if font_path is not None else None
    if candidate is None:
        fc_match = shutil.which("fc-match")
        if fc_match:
            try:
                result = subprocess.run([fc_match, "-f", "%{file}\n", "Montserrat:style=Bold"],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                        timeout=5, check=False)
                if result.returncode == 0 and result.stdout.strip():
                    candidate = Path(result.stdout.strip().splitlines()[0])
            except (OSError, subprocess.TimeoutExpired):
                pass
    if candidate is None:
        raise ValueError("Montserrat Bold nicht gefunden; expliziten font_path angeben.")
    try:
        font = ImageFont.truetype(str(candidate), size=SUBTITLE_FONT_SIZE)
        family, style = font.getname()
        if "montserrat" not in family.casefold():
            raise ValueError(f"Schrift ist {family} {style}, erforderlich ist Montserrat Bold.")
        if style.casefold() != "bold":
            try:
                variants = font.get_variation_names()
                bold = next(name for name in variants if (name.decode() if isinstance(name, bytes) else name).casefold() == "bold")
                font.set_variation_by_name(bold)
            except (AttributeError, OSError, StopIteration) as exc:
                raise ValueError(f"Schriftschnitt ist {style}, erforderlich ist Bold.") from exc
    except (OSError, ValueError) as exc:
        raise ValueError(f"Montserrat-Bold-Messung nicht möglich: {exc}") from exc
    return font, candidate.resolve()


def _glyph_width(font: Any, line: str) -> dict[str, Any]:
    values: list[float] = []
    errors: list[str] = []
    for metric in ("ink", "advance"):
        try:
            if metric == "ink":
                bounds = font.getbbox(line)
                value = float(bounds[2] - bounds[0])
            else:
                value = float(font.getlength(line))
            if not math.isfinite(value) or value < 0:
                raise ValueError("Ungültige Glyphenbreite.")
            values.append(value)
        except (ValueError, OSError, AttributeError, TypeError, IndexError) as exc:
            errors.append(f"{metric}: {exc}")
    return {
        "pixelbreite": max(values) if values else None,
        "vollstaendig": not errors, "messfehler": errors,
        "pixelbreite_ist_untergrenze": bool(errors),
    }


def validate_srt(path: Path, font_path: Path | str | None = None) -> dict[str, Any]:
    """Validate SRT timing/text and true glyph widths at Montserrat Bold 52 px.

    White text, actual placement/burn-in and synchronization (≤100 ms) cannot
    be established by the SRT file alone and are separate human checks.
    """
    path = Path(path).resolve()
    qa = _QA(path, SRT_CHECKS)
    qa.data["menschliche_pruefungen"] = [
        {"name": "srt_sync", "status": "ausstehend", "soll": "Mit Sprach-/Video-Referenz jeden Cue auf maximal 100 ms Abweichung prüfen; keine Referenz im Funktionsinterface."},
        {"name": "srt_export_layout", "status": "ausstehend", "soll": "Montserrat Bold 52 px, weiß, x=90…930, y=192…1536; Untertitelunterkante 1520, Quellen y=1200…1320; am tatsächlich gerenderten Video prüfen."},
    ]
    qa.data["grenzen"] = [
        "SRT trägt keine zuverlässige Export-Schrift, Textfarbe oder Bildschirmposition.",
        "Pixelbreite wird mit realen Font-Glyphen gemessen; Export-Outline/Schatten und Layout brauchen eine Sichtprüfung.",
        "Ohne Montserrat Bold und Pillow ist Pixelbreite eine fehlende Pflichtprüfung, niemals ein geschätzter Pass.",
        "Zeichenzahl verwendet NFC-normalisierte Unicode-Codepoints einschließlich Leerzeichen; CPS zählt alle Zeilen ohne Zeilenumbruch.",
    ]
    try:
        raw = path.read_bytes()
        initial_hash = hashlib.sha256(raw).hexdigest()
        qa.data["datei_sha256"] = initial_hash
        qa.check("datei_lesbar", True, "Lesbare SRT-Datei", str(path))
    except OSError as exc:
        qa.check("datei_lesbar", False, "Lesbare SRT-Datei", str(exc), severity="K0")
        return qa.finish()
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        qa.check("srt_utf8", True, "UTF-8 (BOM erlaubt)", "UTF-8")
    except UnicodeDecodeError as exc:
        qa.check("srt_utf8", False, "UTF-8", str(exc))
        _check_unchanged(qa, initial_hash)
        return qa.finish()
    try:
        cues = _parse_srt(text)
        qa.check("srt_syntax", True, "Fortlaufende SRT-Cues mit korrekten Zeitstempeln und Text", len(cues))
    except ValueError as exc:
        qa.check("srt_syntax", False, "Gültige SRT-Syntax", str(exc))
        _check_unchanged(qa, initial_hash)
        return qa.finish()
    measured = []
    for cue in cues:
        normalized_lines = [unicodedata.normalize("NFC", line) for line in cue["zeilen"]]
        lengths = [len(line) for line in normalized_lines]
        measured.append({**cue, "zeichen_pro_zeile": lengths, "cps": sum(lengths) / cue["dauer_s"]})
    qa.data["technischer_report"]["cues"] = measured
    checks = (
        ("srt_max_2_zeilen", lambda cue: len(cue["zeilen"]) <= 2, "Höchstens 2 Textzeilen pro Cue"),
        ("srt_max_28_zeichen", lambda cue: max(cue["zeichen_pro_zeile"]) <= 28, "Höchstens 28 Zeichen je Zeile einschließlich Leerzeichen"),
        ("srt_max_18_cps", lambda cue: cue["cps"] <= 18, "Höchstens 18 Zeichen/s; beide Zeilen zusammen"),
        ("srt_dauer_0_8_bis_4s", lambda cue: 0.8 <= cue["dauer_s"] <= 4, "Cue-Dauer 0,8–4 s (einschließlich Grenzen)"),
        ("srt_zeitgrenzen_0_bis_58s", lambda cue: 0 <= cue["start_ms"] < cue["ende_ms"] <= 58000, "Alle Cues vollständig innerhalb 0–58 s"),
    )
    for name, predicate, expected in checks:
        invalid = [cue for cue in measured if not predicate(cue)]
        qa.check(name, not invalid, expected, invalid or "Alle Cues erfüllen die Vorgabe.", route="09_POSTPRODUKTION: SRT-Cues korrigieren und erneut prüfen.")
    overlaps = [{"cue": right["nummer"], "vorheriger_cue": left["nummer"], "ueberlappung_ms": left["ende_ms"] - right["start_ms"]}
                for left, right in zip(measured, measured[1:]) if right["start_ms"] < left["ende_ms"]]
    qa.check("srt_keine_ueberlappung", not overlaps, "Chronologische Cues ohne Überlappung; angrenzende Zeitgrenzen erlaubt", overlaps or "Keine Überlappung.", route="09_POSTPRODUKTION: Zeitstempel korrigieren und erneut prüfen.")
    try:
        font, font_file = _load_montserrat(font_path)
    except (ValueError, OSError, AttributeError) as exc:
        qa.check("srt_pixelbreite", None, "Pillow und echte Montserrat Bold, 52 px; jede Zeile ≤840 px", str(exc),
                 route="10_QA: Montserrat Bold/Pillow bereitstellen, font_path angeben und reale Pixelbreite erneut messen.")
    else:
        widths = []
        for cue in measured:
            for index, line in enumerate(cue["zeilen"], 1):
                widths.append({"cue": cue["nummer"], "zeile": index, **_glyph_width(font, line)})
        font_hash = None
        font_hash_error = ""
        try:
            font_hash = _sha256(font_file)
        except OSError as exc:
            font_hash_error = str(exc)
        qa.data["technischer_report"]["schrift"] = {
            "pfad": str(font_file), "sha256": font_hash, "hash_messfehler": font_hash_error,
            "familie": "Montserrat", "schnitt": "Bold", "groesse_px": 52,
            "nutzbare_breite_px": SUBTITLE_WIDTH, "zeilenbreiten": widths,
        }
        width_checks = [entry["pixelbreite"] <= SUBTITLE_WIDTH if entry["pixelbreite"] is not None else None for entry in widths]
        width_checks += [True if entry["vollstaendig"] else None for entry in widths]
        width_checks.append(True if font_hash is not None else None)
        qa.check("srt_pixelbreite", _conjunction(width_checks),
                 "Reale Montserrat-Bold-Glyphen bei 52 px passen in 840 px (x=90…930)", qa.data["technischer_report"]["schrift"],
                 route="09_POSTPRODUKTION: Umbrüche/Text korrigieren; Export-Schrift und Platzierung gegenprüfen.")
    _check_unchanged(qa, initial_hash)
    return qa.finish()


def _check_unchanged(qa: _QA, initial_hash: str) -> None:
    try:
        final_hash = _sha256(qa.path)
        qa.check("datei_unveraendert", initial_hash == final_hash, initial_hash, final_hash, severity="K0")
    except OSError as exc:
        qa.check("datei_unveraendert", None, initial_hash, str(exc), severity="K0")
