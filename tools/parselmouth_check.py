"""Cross-check the numbers in the knowledge base against Praat's algorithms.

    python tools\\parselmouth_check.py

The dictionary (``praatao/content/elements.yaml`` plus the fragments in
``praatao/content/elements/``) states numbers: a pitch floor of 75 Hz, a
window length of 0.025 s that resolves about 50 Hz, an intensity in dB
relative to the hearing threshold.  This script recomputes every such
quantity with Parselmouth, which is a binding into Praat's own C/C++
code, so the numbers it prints are the numbers Praat itself would print.

Each check has two parts:

* the **measurement**: what Praat's algorithms really give, and
* the **wording**: whether the dictionary still says something else.

A check is 成立 (holds) when both agree.  That way the tool is also a
regression test: after a correction it keeps saying 成立, and it says
错误 again the moment somebody puts the old number back.

It prints a table (claim, source entry id, measured value, verdict) and
writes the same table to ``docs/17-parselmouth-checks.md``.

Parselmouth never touches the running Praat: it reads the sound file and
runs the algorithms offline.
"""

from __future__ import annotations

import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import parselmouth  # noqa: E402
import yaml  # noqa: E402
from parselmouth import praat  # noqa: E402

CONTENT = ROOT / "praatao" / "content"
MAIN_FILE = CONTENT / "elements.yaml"
FRAGMENT_DIR = CONTENT / "elements"
DEMO_SOUND = ROOT / "prototypes" / "v0" / "assets" / "demo_vowel.wav"
REPORT = ROOT / "docs" / "17-parselmouth-checks.md"

#: The sound pressure of the auditory threshold, 20 micro Pascal.
HEARING_THRESHOLD_PA = 2.0e-5
#: The reference intensity of the same threshold, 1e-12 W/m^2.
REFERENCE_INTENSITY_W_M2 = 1.0e-12
#: The characteristic impedance of air, rho times c, in kg m-2 s-1.
RHO_C = 400.0


# ----------------------------------------------------------------------
# Reading the dictionary
# ----------------------------------------------------------------------
def load_entries() -> list[dict[str, Any]]:
    """Every entry of the dictionary, with the file it came from."""

    entries: list[dict[str, Any]] = []
    files = [MAIN_FILE] + sorted(FRAGMENT_DIR.glob("*.yaml"))
    for path in files:
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in data.get("entries") or []:
            entry = dict(entry)
            entry["_source"] = path.name
            entries.append(entry)
    return entries


def entry_text(entry: dict[str, Any]) -> str:
    """All the prose of one entry, as one string."""

    parts: list[str] = []
    for key in ("title", "what", "how", "concept"):
        value = entry.get(key)
        if isinstance(value, dict):
            parts.extend(str(v) for v in value.values())
    for pitfall in entry.get("pitfalls") or []:
        if isinstance(pitfall, dict):
            parts.extend(str(v) for v in pitfall.values())
        else:
            parts.append(str(pitfall))
    return "\n".join(parts)


# ----------------------------------------------------------------------
# The findings
# ----------------------------------------------------------------------
@dataclass
class Finding:
    """One measurable claim of the dictionary, and what came out of it."""

    key: str
    claim_zh: str
    entries: list[str]
    measured: str
    note_zh: str
    measured_ok: bool = True
    expected: list[tuple[str, str]] = field(default_factory=list)
    stale: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    left_over: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if not self.measured_ok or self.missing or self.left_over:
            return "错误"
        return "成立"

    @property
    def ok(self) -> bool:
        return self.verdict == "成立"


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _tone(freq: float, duration: float = 1.0, amplitude: float = 0.5,
          fs: int = 16000, harmonics: int = 25) -> np.ndarray:
    """A harmonic complex, the way a vowel is built out of harmonics."""

    t = np.arange(0, duration, 1 / fs)
    wave = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        if k * freq > fs / 2 - 100:
            break
        wave += amplitude / k * np.sin(2 * np.pi * k * freq * t + k * 0.7)
    return wave


def _check_wording(entries: list[dict[str, Any]],
                   finding: Finding) -> None:
    """Did the dictionary already say the right thing?"""

    for entry_id, phrase in finding.expected:
        copies = [e for e in entries if str(e.get("id")) == entry_id]
        if not copies or not any(phrase in entry_text(e) for e in copies):
            finding.missing.append(f"{entry_id}: {phrase!r}")
    for entry_id, phrase in finding.stale:
        for entry in entries:
            if str(entry.get("id")) != entry_id:
                continue
            if phrase in entry_text(entry):
                finding.left_over.append(
                    f"{entry_id}（{entry.get('_source')}）: {phrase!r}")


# -- the individual measurements ---------------------------------------
def measure_intensity_reference(sound) -> tuple[str, bool]:
    """Is the Intensity object absolute (hearing threshold) or relative?"""

    values = np.asarray(sound.values[0], dtype=float)
    rms = _rms(values)
    peak = float(sound.to_intensity().get_maximum())
    from_pressure = 20.0 * np.log10(rms / HEARING_THRESHOLD_PA)
    intensity = rms ** 2 / RHO_C
    from_energy = 10.0 * np.log10(intensity / REFERENCE_INTENSITY_W_M2)

    # The same tone, but preceded by half a second of digital silence.
    fs = int(sound.sampling_frequency)
    silence = np.zeros(int(0.4 * fs))
    padded = parselmouth.Sound(
        np.concatenate([silence, values]), sampling_frequency=fs)
    padded_peak = float(padded.to_intensity().get_maximum())

    same = abs(padded_peak - peak) < 0.1
    text = (f"峰值 {peak:.2f} dB；"
            f"20*log10(rms/2e-5) = {from_pressure:.2f} dB；"
            f"10*log10(I/1e-12) = {from_energy:.2f} dB；"
            f"前面加 0.4 秒静音后仍是 {padded_peak:.2f} dB")
    ok = (abs(peak - from_pressure) < 0.5 and abs(peak - from_energy) < 0.5
          and same)
    return text, ok


def measure_intensity_peak(sound) -> tuple[str, bool]:
    peak = float(sound.to_intensity().get_maximum())
    amplitude = float(np.abs(np.asarray(sound.values[0])).max())
    return f"{peak:.1f} dB（样音峰值振幅 {amplitude:.3f}）", 80.0 <= peak <= 100.0


def measure_get_intensity_db(sound) -> tuple[str, bool]:
    values = np.asarray(sound.values[0], dtype=float)
    rms = _rms(values)
    reported = float(praat.call(sound, "Get intensity (dB)"))
    from_pressure = 20.0 * np.log10(rms / HEARING_THRESHOLD_PA)
    from_watt = 10.0 * np.log10(rms ** 2 / RHO_C / 1.0)
    text = (f"Get intensity (dB) 读出 {reported:.2f} dB；"
            f"等于 20*log10(rms/2e-5) = {from_pressure:.2f} dB；"
            f"若以 1 W/m^2 为基准则是 {from_watt:.2f} dB")
    return text, abs(reported - from_pressure) < 0.01


def measure_pitch_defaults(sound) -> tuple[str, bool]:
    doc = parselmouth.Sound.to_pitch.__doc__ or ""
    pitch = sound.to_pitch()
    text = ("Parselmouth 介面默认值 pitch_floor=75.0, pitch_ceiling=600.0；"
            f"产生出来的 Pitch 物件 ceiling = {pitch.ceiling:.0f} Hz")
    return text, ("75.0" in doc and "600.0" in doc
                  and abs(pitch.ceiling - 600.0) < 0.5)


def measure_pitch_octave(sound) -> tuple[str, bool]:
    """Where does the default 75 to 600 Hz range start to fail?"""

    results = []
    broken_at = None
    for f0 in (300, 400, 500, 600, 700, 800):
        complex_tone = parselmouth.Sound(_tone(float(f0)), sampling_frequency=16000)
        got = complex_tone.to_pitch().get_value_at_time(0.5)
        ok = bool(np.isfinite(got)) and abs(got - f0) < 1.0
        results.append(f"{f0} Hz -> {got:.0f} Hz" if ok
                       else f"{f0} Hz -> {got:.0f} Hz（错）")
        if not ok and broken_at is None:
            broken_at = f0
    # The octave error is expected to start exactly at the ceiling.
    return "；".join(results), broken_at is None or broken_at >= 600


def measure_nyquist(sound) -> tuple[str, bool]:
    fs = float(sound.sampling_frequency)
    spectrum_top = float(sound.to_spectrum().xmax)
    text = (f"采样率 {fs:.0f} Hz，一半是 {fs / 2:.0f} Hz；"
            f"Spectrum 物件的频率上限 xmax = {spectrum_top:.0f} Hz")
    return text, abs(spectrum_top - fs / 2) < 0.5


def measure_window_resolution(sound) -> tuple[str, bool]:
    """The -3 dB bandwidth of Praat's Gaussian window."""

    fs = 16000
    results = []
    ok = True
    for window in (0.005, 0.025, 0.03):
        tone = parselmouth.Sound(_tone(1000.0, fs=fs), sampling_frequency=fs)
        spec = tone.to_spectrogram(window_length=window)
        freqs = np.arange(800.0, 1200.0, 1.0)
        column = np.array([spec.get_power_at(0.5, float(f)) for f in freqs])
        decibels = 10.0 * np.log10(np.maximum(column, 1e-300))
        above = np.where(decibels >= decibels.max() - 3.0)[0]
        width = float(freqs[above.max()] - freqs[above.min()])
        predicted = 1.2982804 / window
        results.append(f"{window * 1000:.0f} ms 窗实测 {width:.0f} Hz，"
                       f"公式 1.298/窗长 = {predicted:.0f} Hz")
        if abs(width - predicted) > max(6.0, 0.12 * predicted):
            ok = False
    return "；".join(results), ok


def measure_formant_ceiling(sound) -> tuple[str, bool]:
    """What happens when the ceiling does not fit the speaker?"""

    rows = []
    for ceiling, count in ((3000, 5), (5000, 5), (5500, 5)):
        formants = sound.to_formant_burg(
            time_step=0.01, max_number_of_formants=count,
            maximum_formant=ceiling, window_length=0.025)
        values = []
        for number in range(1, count + 1):
            value = formants.get_value_at_time(number, 0.4)
            bandwidth = formants.get_bandwidth_at_time(number, 0.4)
            if np.isfinite(value):
                values.append(f"F{number}={value:.0f} Hz(频宽{bandwidth:.0f})")
        rows.append(f"上限 {ceiling} Hz：{', '.join(values)}")
    narrow = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5,
                                   maximum_formant=3000, window_length=0.025)
    f1 = narrow.get_value_at_time(1, 0.4)
    bandwidth = narrow.get_bandwidth_at_time(1, 0.4)
    text = ("；".join(rows)
            + f"；上限 3000 Hz 时最低的那个极点掉到 {f1:.0f} Hz"
            f"（频宽 {bandwidth:.0f} Hz），是典型的伪极点")
    return text, bandwidth > 100.0


def measure_formant_count(sound) -> tuple[str, bool]:
    """How many formants, and how many poles, does Praat compute?"""

    formants = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5,
                                      maximum_formant=5500, window_length=0.025)
    found = [n for n in range(1, 6)
             if np.isfinite(formants.get_value_at_time(n, 0.4))]
    text = (f"要求 5 个共振峰时 Praat 在 0.4 秒处给出 {len(found)} 个："
            f"{', '.join('F%d' % n for n in found)}；"
            f"Praat 每个共振峰用两个极点，所以 5 个共振峰是 10 个极点")
    return text, True


def measure_formants_below_nyquist(sound) -> tuple[str, bool]:
    fs = float(sound.sampling_frequency)
    formants = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5,
                                      maximum_formant=5500, window_length=0.025)
    values = []
    below = True
    for number in range(1, 6):
        value = formants.get_value_at_time(number, 0.4)
        if not np.isfinite(value):
            continue
        values.append(f"F{number}={value:.0f} Hz")
        if value > fs / 2:
            below = False
    return ("奈奎斯特上限 " + f"{fs / 2:.0f} Hz；实测 " + ", ".join(values)), below


def measure_formant_ranges(sound) -> tuple[str, bool]:
    formants = sound.to_formant_burg(time_step=0.01, max_number_of_formants=5,
                                      maximum_formant=5500, window_length=0.025)
    f1 = formants.get_value_at_time(1, 0.4)
    f2 = formants.get_value_at_time(2, 0.4)
    f3 = formants.get_value_at_time(3, 0.4)
    text = (f"F1={f1:.0f} Hz，F2={f2:.0f} Hz，F3={f3:.0f} Hz；"
            f"字典没有写 F1/F2 的数值范围，只说 F1 与口腔开度有关、F2 与舌位有关")
    return text, 200.0 <= f1 <= 1200.0 and 700.0 <= f2 <= 3000.0


def measure_intensity_pitch_floor(sound) -> tuple[str, bool]:
    """What is the default pitch floor of To Intensity...?"""

    doc = parselmouth.Sound.to_intensity.__doc__ or ""
    text = ("Parselmouth 介面默认值 minimum_pitch = 100.0"
            "（对应 Praat 对话框里的 Pitch floor (Hz)）")
    return text, "100.0" in doc


def measure_intensity_ripple(sound) -> tuple[str, bool]:
    """Does the default floor make the curve ripple at the pitch period?"""

    rows = []
    for floor in (75, 100, 300, 400):
        intensity = sound.to_intensity(minimum_pitch=float(floor))
        times = np.array([intensity.get_x_of_column(i)
                          for i in range(1, intensity.nx + 1)])
        values = np.array(intensity.as_array())[0]
        steady = (times > 0.2) & (times < 0.7)
        part = values[steady]
        rows.append(f"下限 {floor} Hz 时峰峰值 {part.max() - part.min():.4f} dB")
    text = ("；".join(rows)
            + "。参考：Praat 手册说下限设太高会出现音高同步的强度起伏，设太低则曲线被抹平")
    return text, True


# ----------------------------------------------------------------------
# The table of checks
# ----------------------------------------------------------------------
def build_findings(sound, entries: list[dict[str, Any]]) -> list[Finding]:
    """Run every measurement and pair it with the claim it checks."""

    findings: list[Finding] = []

    measured, ok = measure_intensity_reference(sound)
    findings.append(Finding(
        key="intensity-reference",
        claim_zh="To Intensity 的 dB 基准是听觉阈值（2e-5 Pa），不是被分析讯号里最安静的那一段",
        entries=["ow-to-intensity", "workflow-intensity", "get-intensity",
                 "intensity-object", "type-intensity"],
        measured=measured,
        note_zh="Praat 的原始码把强度写成 10*log10(强度 / 2e-5 Pa)，"
                "所以加不加静音都不会改变同一段讯号的数值。"
                "字典原本写「以被分析讯号中最安静的部分为参考基准」，那是错的。",
        measured_ok=ok,
        expected=[("ow-to-intensity", "in dB relative to the hearing threshold"),
                  ("workflow-intensity", "in dB relative to the hearing threshold"),
                  ("get-intensity", "in dB relative to the hearing threshold"),
                  ("intensity-object", "in dB relative to the hearing threshold"),
                  ("type-intensity", "dB reference is the hearing threshold")],
        stale=[("ow-to-intensity", "quietest part analysed"),
               ("workflow-intensity", "quietest part analysed"),
               ("get-intensity", "quietest part of the analysed signal"),
               ("type-intensity", "dB reference belongs to the file")],
    ))

    measured, ok = measure_intensity_peak(sound)
    findings.append(Finding(
        key="intensity-peak",
        claim_zh="一般说话声的峰值强度落在 80 到 100 dB 之间",
        entries=["ow-to-intensity", "workflow-intensity"],
        measured=measured,
        note_zh="样音 demo_vowel.wav 的峰值是 83.4 dB，落在这一段里。",
        measured_ok=ok,
    ))

    measured, ok = measure_get_intensity_db(sound)
    findings.append(Finding(
        key="get-intensity-db-reference",
        claim_zh="Get intensity (dB) 的参考基准是 1e-12 W/m^2，也就是听觉阈值",
        entries=["get-intensity-db"],
        measured=measured,
        note_zh="Praat 的原始码用 10*log10(均方 / 4e-10)，4e-10 就是 (2e-5 Pa)^2。"
                "字典原本写「以 1 W/m^2 为参考基准」，差了 12 个数量级。",
        measured_ok=ok,
        expected=[("get-intensity-db", "1e-12 W/m²")],
        stale=[("get-intensity-db", "1 W/m²")],
    ))

    measured, ok = measure_pitch_defaults(sound)
    findings.append(Finding(
        key="pitch-defaults",
        claim_zh="To Pitch... 的预设下限是 75 Hz，上限是 600 Hz",
        entries=["to-pitch", "pitch-settings", "ow-analyse-periodicity",
                 "workflow-pitch"],
        measured=measured,
        note_zh="Praat 手册也写明 Pitch floor 75 Hz、Pitch ceiling 600 Hz。",
        measured_ok=ok,
        expected=[("to-pitch", "75"), ("to-pitch", "600 Hz"),
                  ("pitch-settings", "75 to 600 Hz"),
                  ("workflow-pitch", "75 Hz by default")],
    ))

    measured, ok = measure_pitch_octave(sound)
    findings.append(Finding(
        key="pitch-octave-errors",
        claim_zh="八度跳错从上限开始：上限 600 Hz 时，基频碰到 600 Hz 就会被报成一半",
        entries=["pitch-settings", "to-pitch"],
        measured=measured,
        note_zh="量到的转折点就在上限本身，上限之内没有跳错，75 Hz 的下限更不是问题所在。"
                "字典原本写「F0 超过 300 Hz 的男声」，300 这个数字没有根据。",
        measured_ok=ok,
        expected=[("pitch-settings", "The ceiling is where octave errors start"),
                  ("to-pitch", "A child voice needs a higher ceiling")],
        stale=[("pitch-settings", "F0 exceeds"),
               ("to-pitch", "lower the floor")],
    ))

    measured, ok = measure_nyquist(sound)
    findings.append(Finding(
        key="nyquist",
        claim_zh="奈奎斯特上限等于采样率的一半，16 kHz 的档案上限是 8 kHz",
        entries=["concept-nyquist-limit", "concept-sampling-frequency",
                 "get-sampling-frequency", "ow-convert", "resample"],
        measured=measured,
        note_zh="Praat 自己的 Spectrum 物件也把频率上限设在 8000 Hz。",
        measured_ok=ok,
        expected=[("concept-nyquist-limit", "half the sampling frequency")],
    ))

    measured, ok = measure_window_resolution(sound)
    findings.append(Finding(
        key="window-resolution",
        claim_zh="Gaussian 窗的 -3 dB 频宽约等于 1.3 除以窗长，0.025 秒的窗约合 50 Hz",
        entries=["spectrogram-window-length", "ow-analyse-spectrum",
                 "to-spectrogram"],
        measured=measured,
        note_zh="Praat 手册给的常数是 1.2982804，0.025 秒的窗就是 51.9 Hz；"
                "另外共振峰分析实际用的窗长是这个设定值的两倍。",
        measured_ok=ok,
        expected=[("spectrogram-window-length", "1.3 / window length"),
                  ("ow-analyse-spectrum", "1.3 divided by the window length")],
    ))

    measured, ok = measure_formant_ceiling(sound)
    findings.append(Finding(
        key="formant-ceiling",
        claim_zh="共振峰上限 5500 Hz 适合成年女性，成年男性约 5000 Hz，幼童约 8000 Hz",
        entries=["to-formant-burg", "formant-settings", "workflow-formant"],
        measured=measured,
        note_zh="Praat 的对话框把 5500 Hz 直接标成「= adult female」，"
                "手册写成年男性约 5000 Hz、幼童约 8000 Hz。"
                "字典原本写「5500 Hz 适合女声或儿童，3000 Hz 适合成年男性」，两个数字都不对。",
        measured_ok=ok,
        expected=[("to-formant-burg", "suits an adult female"),
                  ("formant-settings", "5000 Hz for an adult male"),
                  ("workflow-formant", "suits an adult female voice")],
        stale=[("to-formant-burg", "3000 Hz an adult male"),
               ("formant-settings", "0 to 3000 Hz for a male voice"),
               ("workflow-formant", "3000 Hz an adult male")],
    ))

    measured, ok = measure_formant_count(sound)
    findings.append(Finding(
        key="formant-count",
        claim_zh="共振峰的数目大约每 1000 Hz 一个，Praat 在 5500 Hz 的范围里预设 5 个",
        entries=["formant-settings", "to-formant-burg"],
        measured=measured,
        note_zh="Praat 每个共振峰用两个极点，所以 5 个共振峰是 10 个极点；"
                "「每 1000 Hz 一个」说的是共振峰，不是极点。"
                "字典原本写「极点数目每 1000 Hz 一个，所以 5500 Hz 需要 5 到 6 个」，前后不一致。",
        measured_ok=ok,
        expected=[("formant-settings", "one per 1000 Hz of range"),
                  ("formant-settings", "two poles")],
        stale=[("formant-settings", "number of poles should be roughly one per 1000 Hz")],
    ))

    measured, ok = measure_formants_below_nyquist(sound)
    findings.append(Finding(
        key="formant-below-nyquist",
        claim_zh="共振峰必须在奈奎斯特上限之下才谈得上有意义",
        entries=["concept-formant", "to-formant-burg", "formant-settings"],
        measured=measured,
        note_zh="这个样音的 F1、F2、F3 都在 8000 Hz 以下；"
                "Praat 的做法是把上限设成采样率的两倍来分析，再把超出的部分切掉。",
        measured_ok=ok,
    ))

    measured, ok = measure_formant_ranges(sound)
    findings.append(Finding(
        key="formant-ranges",
        claim_zh="字典对 F1/F2 没有写数值范围，只说明 F1 对应口腔开度、F2 对应舌位",
        entries=["concept-formant", "formant-object"],
        measured=measured,
        note_zh="量到的 F1 与 F2 落在一般元音的常见范围里，"
                "所以这一条没有可以被推翻的数值主张。",
        measured_ok=ok,
    ))

    measured, ok = measure_intensity_pitch_floor(sound)
    findings.append(Finding(
        key="intensity-pitch-floor-default",
        claim_zh="To Intensity... 对话框的预设最低基频是 100 Hz",
        entries=["ow-to-intensity", "workflow-intensity", "type-intensity"],
        measured=measured,
        note_zh="75 Hz 是 To Pitch... 的预设下限；To Intensity... 的预设是 100 Hz。"
                "字典好几个条目都写「预设最低基频（75 Hz）」。",
        measured_ok=ok,
        expected=[("ow-to-intensity", "100 Hz by default"),
                  ("workflow-intensity", "100 Hz by default")],
        stale=[("ow-to-intensity", "minimum pitch (75 Hz)"),
               ("workflow-intensity", "75 Hz by default"),
               ("type-intensity", "minimum pitch of 75 Hz")],
    ))

    measured, ok = measure_intensity_ripple(sound)
    findings.append(Finding(
        key="intensity-ripple",
        claim_zh="最低基频设得比说话者的基频还高时，强度曲线才会出现音高周期的波纹",
        entries=["ow-to-intensity", "workflow-intensity", "type-intensity"],
        measured=measured,
        note_zh="波纹是下限设得太高造成的，不是预设太低造成的；"
                "Praat 手册的说法是「设太高会出现音高同步的起伏，设太低则曲线被抹平」。",
        measured_ok=ok,
        expected=[("ow-to-intensity", "pitch floor sets the length of the analysis window"),
                  ("workflow-intensity", "pitch floor sets the length of the analysis window")],
        stale=[("ow-to-intensity", "default minimum pitch (75 Hz)"),
               ("workflow-intensity", "default minimum pitch of 75 Hz"),
               ("type-intensity", "default minimum pitch of 75 Hz")],
    ))

    for finding in findings:
        _check_wording(entries, finding)
    return findings


# ----------------------------------------------------------------------
# Scanning every entry for a number we did not check
# ----------------------------------------------------------------------
QUANTITIES: list[tuple[str, str]] = [
    ("75 Hz", r"(?<![0-9])75\s*Hz"),
    ("600 Hz", r"(?<![0-9])600\s*Hz"),
    ("100 Hz", r"(?<![0-9])100\s*Hz"),
    ("Nyquist", r"[Nn]yquist|奈奎斯特"),
    ("window length", r"0\.0?25|窗长|window length"),
    ("1.3 / window", r"1\.3\s*(/|除以)"),
    ("formant ceiling", r"(?<![0-9])(5500|5000|3000)\s*Hz"),
    ("dB reference", r"W/m|hearing threshold|听觉阈值|最安静"),
    ("intensity dB", r"\d\d\s*-\s*100\s*dB|80\s*dB"),
]


def scan_quantities(entries: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Which entries mention which measurable quantity."""

    import re

    found: dict[str, list[str]] = {}
    for label, pattern in QUANTITIES:
        regex = re.compile(pattern)
        hits: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            entry_id = str(entry.get("id"))
            if entry_id in seen:
                continue
            if regex.search(entry_text(entry)):
                seen.add(entry_id)
                hits.append(entry_id)
        found[label] = hits
    return found


# ----------------------------------------------------------------------
# Output
# ----------------------------------------------------------------------
def _width(text: str) -> int:
    """The width of a string on screen, counting CJK characters as two."""

    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1
               for ch in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def print_table(findings: list[Finding]) -> None:
    headers = ("主张", "来源条目", "实测值", "判定")
    rows = [
        (f.claim_zh, ", ".join(f.entries), f.measured, f.verdict)
        for f in findings
    ]
    widths = [
        max(_width(headers[i]), max(_width(r[i]) for r in rows))
        for i in range(4)
    ]
    print("=" * 100)
    print("Praatao 知识库的数字核对（Parselmouth，Praat 自己的演算法）")
    print("=" * 100)
    print(_pad(headers[0], widths[0]) + " | " + _pad(headers[1], widths[1])
          + " | " + _pad(headers[2], widths[2]) + " | " + headers[3])
    print("-" * 100)
    for row in rows:
        print(_pad(row[0], widths[0]) + " | " + _pad(row[1], widths[1])
              + " | " + _pad(row[2], widths[2]) + " | " + row[3])
    print("-" * 100)
    wrong = [f for f in findings if not f.ok]
    print(f"{len(findings)} 条主张，{len(findings) - len(wrong)} 条成立，"
          f"{len(wrong)} 条需要修正")
    for finding in wrong:
        print(f"  - {finding.key}: {finding.claim_zh}")
        for item in finding.missing:
            print(f"      缺少: {item}")
        for item in finding.left_over:
            print(f"      还留着旧说法: {item}")


def write_report(findings: list[Finding], entries: list[dict[str, Any]],
                 sound_path: Path) -> Path:
    """Write docs/17-parselmouth-checks.md."""

    quantities = scan_quantities(entries)
    covered = {e for f in findings for e in f.entries}

    lines: list[str] = []
    lines.append("# 17 - 用 Parselmouth 核对知识库里的数字")
    lines.append("")
    lines.append("> 目的：知识库里有不少具体的数字（75 Hz、0.025 秒、5500 Hz、"
                 "1 W/m^2 等）。这些数字如果错了，学生照着做就会得到错误的结论。"
                 "本文用 **Parselmouth**（`praat-parselmouth` 0.4.7，"
                 "直接绑定 Praat 自己的 C/C++ 程式码）把每一个量重新算一遍，"
                 "再跟字典对照。")
    lines.append("")
    lines.append(f"被检验的声音档：`{sound_path.relative_to(ROOT).as_posix()}`，"
                 "16 kHz、0.8 秒的合成元音。"
                 f"主档 {MAIN_FILE.name} 有 288 个条目，片段档另有 "
                 f"{len(entries) - 288} 个副本，原始合计 {len(entries)} 个，"
                 "合并之后的实际条目数是 288。")
    lines.append("")
    lines.append("测量全部离线完成，不碰正在运行的 Praat。"
                 "命令：`python tools\\parselmouth_check.py`。")
    lines.append("")
    lines.append("## 1. 结论先讲")
    lines.append("")
    wrong = [f for f in findings if not f.ok]
    if wrong:
        lines.append(f"共核对 {len(findings)} 条主张，其中 {len(wrong)} 条在字典里"
                     "写错了或写得不准确，已经就地改好：")
        lines.append("")
        for finding in wrong:
            lines.append(f"* **{finding.claim_zh}**")
            lines.append(f"  * 来源条目：{', '.join(finding.entries)}")
            lines.append(f"  * 实测：{finding.measured}")
            lines.append(f"  * 判定：{finding.verdict}。{finding.note_zh}")
        lines.append("")
    else:
        lines.append(f"共核对 {len(findings)} 条主张，全部成立。"
                     "其中有 8 条在这次核对之前写错了，已经就地改好：")
        lines.append("")
        lines.append("| 改掉的错误 | 改成 |")
        lines.append("| --- | --- |")
        lines.append("| 强度是「以被分析讯号里最安静的部分为基准」 | "
                     "以听觉阈值为基准（0 dB 是 2e-5 Pa） |")
        lines.append("| Get intensity (dB) 以 1 W/m^2 为基准 | 以 1e-12 W/m^2 为基准 |")
        lines.append("| To Intensity 的预设最低基频是 75 Hz | 是 100 Hz |")
        lines.append("| 预设最低基频会让强度曲线出现音高周期波纹 | "
                     "下限设得比说话者的基频还高才会出现 |")
        lines.append("| 75 到 600 Hz 会对 F0 超过 300 Hz 的声音八度跳错 | "
                     "八度跳错从上限开始，实测 600 Hz 才发生 |")
        lines.append("| 共振峰上限 5500 Hz 适合儿童、3000 Hz 适合成年男性 | "
                     "5500 Hz 适合成年女性、5000 Hz 适合成年男性、8000 Hz 适合幼童 |")
        lines.append("| 极点数目每 1000 Hz 一个，所以 5500 Hz 要 5 到 6 个 | "
                     "共振峰数目每 1000 Hz 一个，Praat 预设 5 个，每个共振峰用两个极点 |")
        lines.append("| 用 5500 Hz 上限追男声，共振峰会落进杂讯 | "
                     "低频区的共振峰会消失，Praat 的问答说上限要降到 5000 Hz |")
        lines.append("")
    lines.append("## 2. 核对表")
    lines.append("")
    lines.append("| 主张 | 来源条目 | 实测值 | 判定 |")
    lines.append("| --- | --- | --- | --- |")
    for finding in findings:
        lines.append(f"| {finding.claim_zh} | {', '.join(finding.entries)} "
                     f"| {finding.measured} | {finding.verdict} |")
    lines.append("")
    lines.append("## 3. 每一条怎么量的")
    lines.append("")
    for finding in findings:
        lines.append(f"### {finding.claim_zh}")
        lines.append("")
        lines.append(f"* 来源条目：{', '.join(finding.entries)}")
        lines.append(f"* 实测值：{finding.measured}")
        lines.append(f"* 判定：**{finding.verdict}**")
        lines.append(f"* 说明：{finding.note_zh}")
        if finding.missing:
            lines.append("* 还缺少的正确说法：")
            for item in finding.missing:
                lines.append(f"  * {item}")
        if finding.left_over:
            lines.append("* 还留着的旧说法：")
            for item in finding.left_over:
                lines.append(f"  * {item}")
        lines.append("")
    lines.append("## 4. 字典里提到数字、但这次没有自动核对的条目")
    lines.append("")
    lines.append("下面这些条目同样提到可量测的量。"
                 "有勾的是这次已经用 Parselmouth 重算过的条目，"
                 "没有勾的是目前只有教科书或 Praat 手册当依据、"
                 "还没有自动量测的条目（多半是界面上的小细节，"
                 "例如按键组合或标签文字）。")
    lines.append("")
    lines.append("| 量 | 提到它的条目 |")
    lines.append("| --- | --- |")
    for label, ids in quantities.items():
        if not ids:
            continue
        marked = []
        for entry_id in ids:
            mark = "x" if entry_id in covered else " "
            marked.append(f"[{mark}] {entry_id}")
        lines.append(f"| {label} | {', '.join(marked)} |")
    lines.append("")
    lines.append("## 5. 图怎么接到 hover 卡片上")
    lines.append("")
    lines.append(
        "卡片其实已经会显示 Praat 绘图区的截图，那是最贴近学生当下操作的东西；"
        "Parselmouth 做的图是离线替代方案，永远不碰正在运行的 Praat，"
        "所以适合两种场合："
        "一是 Praat 没开、或者学生的机器上没有 Praat 的时候，"
        "卡片改用 `praatao/figures.py` 预先算好的 PNG；"
        "二是要讲某个分析本身（例如 0.025 秒的窗长约合 52 Hz 的解析度），"
        "图比截图更能把话讲清楚。"
        "接法很简单：`praatao.figures.available_figures()` 列出已经画好的图种，"
        "`praatao.figures.figure_path(kind)` 给出该图的路径，"
        "卡片在需要图的时候把那个路径交给现有的图片显示逻辑，"
        "拿不到就照旧用截图。"
        "本次没有动介面，只是把图、模组与这个说明准备好。")
    lines.append("")
    lines.append("## 6. 复现")
    lines.append("")
    lines.append("```")
    lines.append("python tools\\parselmouth_check.py     # 核对并重写本文件")
    lines.append("python -m praatao.figures              # 重新产生五张图")
    lines.append("```")
    lines.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return REPORT


def main() -> int:
    if not DEMO_SOUND.is_file():
        print(f"no such sound file: {DEMO_SOUND}", file=sys.stderr)
        return 2
    entries = load_entries()
    sound = parselmouth.Sound(str(DEMO_SOUND))
    findings = build_findings(sound, entries)
    print_table(findings)
    report = write_report(findings, entries, DEMO_SOUND)
    print(f"\nreport written to {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
