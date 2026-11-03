"""Vellum Editor: the window.

Drop in a folder of clips and a song, type a title, pick Short or Long, click
Make edit. Everything slow runs on a background thread, so the window never
freezes, and the edit itself uses every CPU core.
"""
from __future__ import annotations

import base64
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import __version__, paths, pipeline
from . import settings as settings_mod
from .audio import SongAnalysis, analyze_song
from .looks import LOOKS
from .plan import EditPlan
from .probe import list_media

INK, BONE, RED, GRAPHITE, ASH, WELL = "#0D0D0F", "#EDEAE4", "#FF4D3D", "#2A2A2F", "#8E8B85", "#151518"
SONG_EXT = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".aif", ".aiff", ".ogg", ".mp4", ".mov", ".m4v"}

STYLE = f"""
QWidget {{ background: {INK}; color: {BONE}; font-family: 'Space Grotesk'; font-size: 14px; }}
QLabel#wordmark {{ font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }}
QLabel#step {{ font-size: 13px; font-weight: 700; color: {ASH}; }}
QLabel#mono, QLabel[mono="true"] {{ font-family: 'JetBrains Mono'; font-size: 12px; color: {ASH}; }}
QLabel#big {{ font-family: 'JetBrains Mono'; font-size: 15px; color: {BONE}; }}
QLabel#note {{ color: {ASH}; font-size: 12px; }}
QLabel#error {{ color: {RED}; font-size: 13px; }}
QLineEdit, QComboBox, QDoubleSpinBox {{ background: {WELL}; border: 1px solid {GRAPHITE}; border-radius: 3px; padding: 7px 9px; }}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{ border-color: {BONE}; }}
QComboBox QAbstractItemView {{ background: {WELL}; selection-background-color: {GRAPHITE}; }}
QPushButton {{ background: transparent; border: 1px solid #55555c; border-radius: 3px; padding: 7px 13px; }}
QPushButton:hover {{ border-color: {BONE}; }}
QPushButton:disabled {{ color: #55555c; border-color: {GRAPHITE}; }}
QPushButton#primary {{ background: {RED}; color: {INK}; border: none; font-size: 17px; font-weight: 700; padding: 14px; }}
QPushButton#primary:hover {{ background: #ff6a5c; }}
QPushButton#primary:disabled {{ background: {GRAPHITE}; color: {ASH}; }}
QPushButton#small {{ padding: 4px 9px; font-family: 'JetBrains Mono'; font-size: 12px; }}
QProgressBar {{ background: {GRAPHITE}; border: none; border-radius: 2px; max-height: 6px; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 2px; }}
QFrame#drop {{ border: 1px dashed #4a4a51; border-radius: 3px; background: {WELL}; }}
QFrame#drop[over="true"] {{ border: 1px solid {RED}; }}
QFrame#panel {{ background: {WELL}; border-radius: 3px; }}
QListWidget {{ background: {WELL}; border: 1px solid {GRAPHITE}; }}
QListWidget::item:selected {{ background: {GRAPHITE}; color: {BONE}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid #5a5a61; border-radius: 3px; background: {WELL}; }}
QCheckBox::indicator:checked {{ background: {RED}; border-color: {RED}; }}
QRadioButton::indicator {{ width: 15px; height: 15px; border: 1px solid #5a5a61; border-radius: 8px; background: {WELL}; }}
QRadioButton::indicator:checked {{ border: 4px solid {WELL}; background: {RED}; outline: 1px solid {RED}; }}
QScrollArea {{ border: none; }}
"""


def log_path() -> Path:
    return paths.app_support_dir() / "vellum-editor.log"


def log(text: str) -> None:
    try:
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + "\n")
    except OSError:
        pass


def friendly(exc: BaseException) -> str:
    if isinstance(exc, pipeline.Cancelled):
        return "cancelled"
    msg = str(exc).strip() or exc.__class__.__name__
    if exc.__class__.__name__ == "FFmpegError":
        return f"ffmpeg couldn't process a file. Details are in the log ({log_path().name}).\n\n{msg[-300:]}"
    if isinstance(exc, (ValueError, FileNotFoundError)):
        return msg
    return f"Something went wrong: {msg}\n\nThe full details are saved in {log_path()}"


def eta_text(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds < 50:
        return f"about {max(5, int(round(seconds / 5) * 5))} s left"
    return f"about {int(round(seconds / 60)) or 1} min left"


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:05.2f}"


# ---------------------------------------------------------------------------- background jobs

class Job(QObject):
    """Runs work on a plain Python thread; Qt queues the signals back onto the window's thread."""

    progress = Signal(float, str, str, object)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.cancel = threading.Event()

    def start(self):
        threading.Thread(target=self._run, name="vellum-job", daemon=True).start()

    def _run(self):
        try:
            result = self.fn(self)
        except BaseException as exc:  # noqa: BLE001 - everything must reach the window
            log(traceback.format_exc())
            self.failed.emit(friendly(exc))
        else:
            self.done.emit(result)

    def report(self, frac: float, stage: str, msg: str, eta: float | None):
        self.progress.emit(frac, stage, msg, eta)


# ---------------------------------------------------------------------------- widgets

class DropZone(QFrame):
    chosen = Signal(str)

    def __init__(self, prompt: str, want_folder: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("drop")
        self.want_folder = want_folder
        self.setAcceptDrops(True)
        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.title = QLabel(prompt)
        self.title.setStyleSheet("background: transparent; font-weight: 700;")
        self.detail = QLabel("or click to choose")
        self.detail.setObjectName("note")
        self.detail.setStyleSheet("background: transparent;")
        lay.addWidget(self.title)
        lay.addWidget(self.detail)

    def _accept(self, path: str) -> bool:
        p = Path(path)
        if self.want_folder:
            return p.is_dir()
        return p.is_file() and p.suffix.lower() in SONG_EXT

    def dragEnterEvent(self, e):
        urls = e.mimeData().urls()
        if urls and self._accept(urls[0].toLocalFile()):
            self.setProperty("over", True)
            self.style().polish(self)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.setProperty("over", False)
        self.style().polish(self)

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        path = e.mimeData().urls()[0].toLocalFile()
        if self._accept(path):
            self.chosen.emit(path)

    def mousePressEvent(self, e):
        if self.want_folder:
            path = QFileDialog.getExistingDirectory(self, "Choose the folder of clips")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Choose the song", "", "Audio (*.mp3 *.m4a *.wav *.aac *.flac *.aif *.aiff *.ogg *.mp4 *.mov)")
        if path:
            self.chosen.emit(path)

    def show_choice(self, title: str, detail: str):
        self.title.setText(title)
        self.detail.setText(detail)


class Waveform(QWidget):
    """Loudness overview of the song: the drop in red, the part the edit uses highlighted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(54)
        self.song: SongAnalysis | None = None
        self.window: tuple[float, float] | None = None

    def set_song(self, song: SongAnalysis | None, window: tuple[float, float] | None):
        self.song, self.window = song, window
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(WELL))
        if not self.song or not self.song.envelope:
            return
        w, h = self.width(), self.height()
        dur = self.song.duration
        if self.window:
            a, b = self.window
            p.fillRect(int(a / dur * w), 0, max(1, int((b - a) / dur * w)), h, QColor(GRAPHITE))
        env = np.asarray(self.song.envelope)
        p.setPen(QPen(QColor(ASH), 1))
        for x in range(w):
            v = env[min(len(env) - 1, int(x / w * len(env)))]
            hh = max(1, int(v * (h - 8)))
            p.drawLine(x, (h - hh) // 2, x, (h + hh) // 2)
        x = int(self.song.drop / dur * w)
        p.setPen(QPen(QColor(RED), 2))
        p.drawLine(x, 0, x, h)


# ---------------------------------------------------------------------------- dialogs

class SettingsDialog(QDialog):
    def __init__(self, s: settings_mod.AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.s = s
        form = QFormLayout(self)
        form.setSpacing(12)

        def chooser(line: QLineEdit, folder: bool, filt: str = ""):
            row = QHBoxLayout()
            row.addWidget(line, 1)
            pick = QPushButton("Choose…")
            clear = QPushButton("Clear")
            row.addWidget(pick)
            row.addWidget(clear)

            def do_pick():
                if folder:
                    path = QFileDialog.getExistingDirectory(self, "Choose a folder")
                else:
                    path, _ = QFileDialog.getOpenFileName(self, "Choose a file", "", filt)
                if path:
                    line.setText(path)

            pick.clicked.connect(do_pick)
            clear.clicked.connect(lambda: line.setText(""))
            return row

        self.sfx = QLineEdit(s.sfx_folder)
        self.sfx.setPlaceholderText("built-in sounds")
        form.addRow("Sound effects folder", chooser(self.sfx, True))
        hint = QLabel("Files named click, click_loud, shutter1–shutter4, riser, whoosh, impact, flash, ring, glitch\n"
                      "(.wav, .mp3, .aif…) replace the built-in sound with the same name.")
        hint.setObjectName("note")
        form.addRow("", hint)
        self.lut = QLineEdit(s.lut_path)
        self.lut.setPlaceholderText("no LUT")
        form.addRow("LUT for log footage (.cube)", chooser(self.lut, False, "LUT (*.cube)"))
        self.lut_apply = QComboBox()
        self.lut_apply.addItems(["Off", "DJI clips only", "All clips"])
        self.lut_apply.setCurrentIndex({"off": 0, "dji": 1, "all": 2}.get(s.lut_apply, 0))
        form.addRow("Apply the LUT to", self.lut_apply)
        self.masks = QCheckBox("Find people (title behind the person, cut-out effects)")
        self.masks.setChecked(s.use_masks)
        form.addRow("", self.masks)
        self.quality = QComboBox()
        self.quality.addItems(["Best quality", "Smaller files"])
        self.quality.setCurrentIndex(0 if s.quality == "best" else 1)
        form.addRow("Files", self.quality)
        self.cores = QCheckBox("Use every CPU core (fastest)")
        self.cores.setChecked(s.all_cores)
        form.addRow("", self.cores)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_settings(self) -> settings_mod.AppSettings:
        s = self.s
        s.sfx_folder = self.sfx.text().strip()
        s.lut_path = self.lut.text().strip()
        s.lut_apply = ["off", "dji", "all"][self.lut_apply.currentIndex()]
        s.use_masks = self.masks.isChecked()
        s.quality = "best" if self.quality.currentIndex() == 0 else "smaller"
        s.all_cores = self.cores.isChecked()
        return s


def thumb_icon(b64: str) -> QIcon:
    if not b64:
        return QIcon()
    img = QImage.fromData(base64.b64decode(b64), "JPG")
    return QIcon(QPixmap.fromImage(img))


class SwapDialog(QDialog):
    """Pick a segment, pick a different clip."""

    def __init__(self, plan: EditPlan, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Swap a shot")
        self.resize(860, 560)
        self.plan = plan
        lay = QVBoxLayout(self)
        tip = QLabel("Pick the shot to replace (numbers match review.html), then the clip to use instead. Clips not in the edit yet are at the top.")
        tip.setWordWrap(True)
        tip.setObjectName("note")
        lay.addWidget(tip)
        row = QHBoxLayout()
        self.segs = QListWidget()
        self.segs.setIconSize(QSize(96, 54))
        self.clips = QListWidget()
        self.clips.setIconSize(QSize(96, 54))
        used = {sh.clip for s in plan.segments for sh in s.all_shots()}
        for i, seg in enumerate(plan.segments, 1):
            shots = seg.all_shots()
            if not shots:
                continue
            f0, _ = plan.frames_of(seg)
            name = shots[0].clip
            item = QListWidgetItem(thumb_icon(plan.clips.get(name, {}).get("thumb", "")), f"#{i}   {f0 // 24 // 60}:{f0 // 24 % 60:02d}   {name}")
            item.setData(Qt.UserRole, i)
            self.segs.addItem(item)
        names = sorted(plan.clips, key=lambda n: (n in used, -plan.clips[n].get("score", 0)))
        for name in names:
            d = plan.clips[name]
            tag = "in the edit" if name in used else "not used yet"
            item = QListWidgetItem(thumb_icon(d.get("thumb", "")), f"{name}   ({tag})")
            item.setData(Qt.UserRole, name)
            self.clips.addItem(item)
        row.addWidget(self.segs, 1)
        row.addWidget(self.clips, 1)
        lay.addLayout(row, 1)
        buttons = QDialogButtonBox()
        self.go = buttons.addButton("Swap and re-render", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def choice(self) -> tuple[int, str] | None:
        s, c = self.segs.currentItem(), self.clips.currentItem()
        if s is None or c is None:
            return None
        return int(s.data(Qt.UserRole)), str(c.data(Qt.UserRole))


# ---------------------------------------------------------------------------- main window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vellum Editor")
        self.resize(720, 900)
        self.settings = settings_mod.load()
        self.clips_dir: str | None = None
        self.song_path: str | None = None
        self.song_base: SongAnalysis | None = None
        self.song: SongAnalysis | None = None
        self.result: pipeline.EditResult | None = None
        self._jobs: list[Job] = []
        self.running: Job | None = None
        self.player: subprocess.Popen | None = None

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(14)

        header = QHBoxLayout()
        mark = QLabel(f"<span style='color:{RED}'>●</span>&nbsp; VELLUM <span style='color:{ASH}'>/</span> STUDIO "
                      f"<span style='color:{ASH}; font-weight:500'>&nbsp;editor</span>")
        mark.setObjectName("wordmark")
        header.addWidget(mark)
        header.addStretch(1)
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        header.addWidget(self.settings_btn)
        outer.addLayout(header)

        # 1 clips
        outer.addWidget(self._step("1   CLIPS"))
        self.clips_zone = DropZone("Drop the folder of clips here", want_folder=True)
        self.clips_zone.chosen.connect(self.set_clips)
        outer.addWidget(self.clips_zone)

        # 2 song
        outer.addWidget(self._step("2   SONG"))
        self.song_zone = DropZone("Drop the song here", want_folder=False)
        self.song_zone.chosen.connect(self.set_song)
        outer.addWidget(self.song_zone)
        self.song_panel = QFrame()
        self.song_panel.setObjectName("panel")
        sp = QGridLayout(self.song_panel)
        sp.setContentsMargins(12, 10, 12, 10)
        sp.setHorizontalSpacing(8)
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(50, 220)
        self.bpm.setDecimals(2)
        self.bpm.setSingleStep(0.1)
        self.bpm.setSuffix(" bpm")
        self.bpm.valueChanged.connect(self.on_bpm)
        half = QPushButton("÷2")
        half.setObjectName("small")
        half.clicked.connect(lambda: self.bpm.setValue(self.bpm.value() / 2))
        dbl = QPushButton("×2")
        dbl.setObjectName("small")
        dbl.clicked.connect(lambda: self.bpm.setValue(self.bpm.value() * 2))
        self.drop_label = QLabel("drop at –")
        self.drop_label.setObjectName("big")
        back_bar, back, fwd, fwd_bar = (QPushButton(t) for t in ("◀◀ bar", "◀ beat", "beat ▶", "bar ▶▶"))
        for b, n in ((back_bar, -4), (back, -1), (fwd, 1), (fwd_bar, 4)):
            b.setObjectName("small")
            b.clicked.connect(lambda _=False, n=n: self.nudge_drop(n))
        self.listen = QPushButton("▶ hear the drop")
        self.listen.setObjectName("small")
        self.listen.clicked.connect(self.play_drop)
        self.listen.setVisible(platform.system() == "Darwin")
        self.reset_song = QPushButton("reset")
        self.reset_song.setObjectName("small")
        self.reset_song.clicked.connect(self.reset_song_nudges)
        sp.addWidget(self.bpm, 0, 0)
        sp.addWidget(half, 0, 1)
        sp.addWidget(dbl, 0, 2)
        sp.addWidget(self.drop_label, 0, 3, 1, 2)
        sp.addWidget(back_bar, 1, 0)
        drop_row = QHBoxLayout()
        for b in (back, fwd, fwd_bar):
            drop_row.addWidget(b)
        drop_row.addStretch(1)
        drop_row.addWidget(self.listen)
        drop_row.addWidget(self.reset_song)
        sp.addLayout(drop_row, 1, 1, 1, 4)
        self.wave = Waveform()
        sp.addWidget(self.wave, 2, 0, 1, 5)
        self.song_note = QLabel("")
        self.song_note.setObjectName("note")
        self.song_note.setWordWrap(True)
        sp.addWidget(self.song_note, 3, 0, 1, 5)
        self.song_panel.setVisible(False)
        outer.addWidget(self.song_panel)

        # 3 details
        outer.addWidget(self._step("3   THE EDIT"))
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.addWidget(QLabel("Title"), 0, 0)
        self.title = QLineEdit()
        self.title.setPlaceholderText("e.g. Tokyo")
        self.title.textChanged.connect(self.update_ready)
        form.addWidget(self.title, 0, 1, 1, 3)
        form.addWidget(QLabel("Length"), 1, 0)
        self.short = QRadioButton("Short (30 s)")
        self.long = QRadioButton("Long (60 s)")
        grp = QButtonGroup(self)
        grp.addButton(self.short)
        grp.addButton(self.long)
        (self.long if self.settings.last_length == "long" else self.short).setChecked(True)
        form.addWidget(self.short, 1, 1)
        form.addWidget(self.long, 1, 2)
        form.addWidget(QLabel("Look"), 2, 0)
        self.look = QComboBox()
        for key, look in LOOKS.items():
            self.look.addItem(look.name, key)
        self.look.setCurrentIndex(max(0, self.look.findData(self.settings.last_look)))
        form.addWidget(self.look, 2, 1, 1, 2)
        self.strict = QCheckBox("Never reuse a clip (fewer cuts if clips run out)")
        self.strict.setChecked(self.settings.strict)
        form.addWidget(self.strict, 3, 1, 1, 3)
        outer.addLayout(form)

        self.make_btn = QPushButton("Make edit")
        self.make_btn.setObjectName("primary")
        self.make_btn.clicked.connect(self.make_edit)
        outer.addWidget(self.make_btn)

        # progress
        prow = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        prow.addWidget(self.progress, 1)
        prow.addWidget(self.cancel_btn)
        self.progress_row = QWidget()
        self.progress_row.setLayout(prow)
        self.progress_row.setVisible(False)
        outer.addWidget(self.progress_row)
        self.status = QLabel("")
        self.status.setObjectName("mono")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

        # results
        self.result_panel = QFrame()
        self.result_panel.setObjectName("panel")
        rp = QVBoxLayout(self.result_panel)
        rp.setContentsMargins(14, 12, 14, 14)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        rp.addWidget(self.result_label)
        rrow = QHBoxLayout()
        self.open_folder = QPushButton("Open folder")
        self.open_folder.clicked.connect(lambda: self.reveal(self.result.out_dir if self.result else None))
        self.open_review = QPushButton("Open review")
        self.open_review.clicked.connect(lambda: self.reveal(self.result.files.get("review") if self.result else None))
        self.swap_btn = QPushButton("Swap a shot…")
        self.swap_btn.clicked.connect(self.swap_shot)
        for b in (self.open_folder, self.open_review, self.swap_btn):
            rrow.addWidget(b)
        rrow.addStretch(1)
        rp.addLayout(rrow)
        hooks_title = QLabel("Hook versions")
        hooks_title.setStyleSheet("font-weight:700; margin-top: 10px; background: transparent;")
        rp.addWidget(hooks_title)
        hint = QLabel("Two lines each, shown over the start of the vertical until the drop. Leave a row empty to skip it.")
        hint.setObjectName("note")
        hint.setWordWrap(True)
        rp.addWidget(hint)
        self.hook_fields: list[tuple[QLineEdit, QLineEdit]] = []
        grid = QGridLayout()
        examples = [("POV: you send me", "your trip clips"), ("24 random clips", "→ this"), ("rate this edit", "out of 10")]
        for i, (a, b) in enumerate(examples):
            l1, l2 = QLineEdit(), QLineEdit()
            l1.setPlaceholderText(a)
            l2.setPlaceholderText(b)
            grid.addWidget(QLabel(f"HOOK {i + 2}"), i, 0)
            grid.addWidget(l1, i, 1)
            grid.addWidget(l2, i, 2)
            self.hook_fields.append((l1, l2))
        rp.addLayout(grid)
        self.hooks_btn = QPushButton("Make hook versions")
        self.hooks_btn.clicked.connect(self.make_hooks)
        rp.addWidget(self.hooks_btn, 0, Qt.AlignLeft)
        self.result_panel.setVisible(False)
        outer.addWidget(self.result_panel)
        outer.addStretch(1)
        foot = QLabel(f"v{__version__}")
        foot.setObjectName("mono")
        outer.addWidget(foot, 0, Qt.AlignRight)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        self.update_ready()

    # ------------------------------------------------------------------ helpers
    def _step(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("step")
        return lab

    def start_job(self, fn, on_done, on_fail, show_progress: bool = True) -> Job:
        job = Job(fn)
        job.done.connect(on_done)
        job.failed.connect(on_fail)
        if show_progress:
            job.progress.connect(self.on_progress)

        def forget(*_):
            # never drop a job from inside its own signal: wait for the event loop to come round
            QTimer.singleShot(0, lambda: self._jobs.remove(job) if job in self._jobs else None)

        job.done.connect(forget)
        job.failed.connect(forget)
        self._jobs.append(job)
        job.start()
        return job

    def busy(self) -> bool:
        return self.running is not None

    def update_ready(self):
        ready = bool(self.clips_dir and self.song and self.title.text().strip()) and not self.busy()
        self.make_btn.setEnabled(ready)
        for w in (self.clips_zone, self.song_zone, self.settings_btn):
            w.setEnabled(not self.busy())
        if self.result is not None:
            for b in (self.hooks_btn, self.swap_btn):
                b.setEnabled(not self.busy())

    def reveal(self, path):
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def error(self, text: str):
        if text == "cancelled":
            self.status.setText("cancelled.")
            return
        QMessageBox.warning(self, "Vellum Editor", text)

    # ------------------------------------------------------------------ inputs
    def set_clips(self, folder: str):
        self.clips_dir = folder
        files = list_media(folder)
        videos = sum(1 for f in files if f.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"})
        detail = f"{len(files)} files ({videos} videos, {len(files) - videos} photos)"
        if len(files) < 6:
            detail += ": that's not many, the edit will be short on variety"
        self.clips_zone.show_choice(Path(folder).name, detail)
        if not self.title.text().strip():
            self.title.setText(Path(folder).name.replace("_", " ").strip()[:40])
        self.update_ready()

    def set_song(self, path: str):
        self.song_path = path
        self.song_zone.show_choice(Path(path).name, "reading the beat…")
        self.song = None
        self.update_ready()

        def work(job: Job):
            return analyze_song(path)

        def done(song: SongAnalysis):
            if self.song_path != path:
                return
            self.song_base = song
            self.apply_song(song)
            self.song_zone.show_choice(Path(path).name, f"{song.duration // 60:.0f}:{song.duration % 60:02.0f} long")

        def fail(msg: str):
            self.song_zone.show_choice(Path(path).name, "couldn't read this song")
            self.error(msg)

        self.start_job(work, done, fail, show_progress=False)

    def apply_song(self, song: SongAnalysis):
        self.song = song
        self.bpm.blockSignals(True)
        self.bpm.setValue(song.bpm)
        self.bpm.blockSignals(False)
        self.drop_label.setText(f"drop at {mmss(song.drop)}")
        self.song_panel.setVisible(True)
        from .planner import grid_beat

        beat = grid_beat(song)
        start = max(0.0, song.drop - 8 * beat)
        length = 60.0 if self.long.isChecked() else 30.0
        self.wave.set_song(song, (start, min(song.duration, start + length)))
        sure = "sure" if song.confidence > 0.6 else "not totally sure"
        half = " (fast song: cuts follow every other beat)" if song.bpm > 150 else ""
        self.song_note.setText(f"I'm {sure} about the beat{half}. If the drop is off, move it with the buttons. "
                               "The edit starts two bars before the drop.")
        self.update_ready()

    def on_bpm(self, value: float):
        if self.song is not None and abs(value - self.song.bpm) > 1e-6:
            self.apply_song(self.song.with_bpm(value))

    def nudge_drop(self, beats: int):
        if self.song is not None:
            self.apply_song(self.song.with_drop(max(0.0, self.song.drop + beats * self.song.beat)))

    def reset_song_nudges(self):
        if self.song_base is not None:
            self.apply_song(self.song_base)

    def play_drop(self):
        """Play 3 s before to 4 s after the drop, with a click on every beat (macOS)."""
        if self.song is None or not self.song_path:
            return
        try:
            self._play_drop()
        except Exception as err:  # never fail silently: say what went wrong
            import logging
            logging.getLogger(__name__).exception("hear the drop failed")
            self.status.setText(f"couldn't play the drop: {err}")

    def _play_drop(self):
        from .ffmpeg import read_audio, write_wav
        from .sfx import SR, builtin_bank

        start = max(0.0, self.song.drop - 3.0)
        audio = read_audio(self.song_path, sr=SR, channels=2, offset=start, duration=7.0) * 0.7
        click = builtin_bank()["click_loud"] * 0.5
        t = self.song.drop - 4 * self.song.beat
        while t < start + 7.0:
            if t >= start:
                i = int((t - start) * SR)
                j = min(len(audio), i + len(click))
                audio[i:j] += click[: j - i] * (1.6 if abs(t - self.song.drop) < 1e-3 else 1.0)
            t += self.song.beat
        tmp = Path(tempfile.gettempdir()) / "vellum-drop-preview.wav"
        write_wav(tmp, audio)
        if self.player and self.player.poll() is None:
            self.player.terminate()
        afplay = "/usr/bin/afplay" if Path("/usr/bin/afplay").exists() else "afplay"
        self.player = subprocess.Popen([afplay, str(tmp)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.status.setText("playing 3 s before the drop to 4 s after, with a click on every beat…")

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.settings = dlg.result_settings()
            settings_mod.save(self.settings)

    # ------------------------------------------------------------------ make edit
    def edit_settings(self) -> pipeline.EditSettings:
        s = self.settings
        return pipeline.EditSettings(
            clips_dir=self.clips_dir or "",
            song=self.song_path or "",
            title=self.title.text().strip(),
            length="long" if self.long.isChecked() else "short",
            look=self.look.currentData(),
            scale=float(os.environ.get("VELLUM_SCALE", "1.0")),
            lut_path=s.lut_path or None,
            lut_apply=s.lut_apply,
            sfx_folder=s.sfx_folder or None,
            use_masks=s.use_masks and os.environ.get("VELLUM_NO_MASKS") != "1",
            strict=self.strict.isChecked(),
            workers=s.workers,
            crf=s.crf,
            preset=os.environ.get("VELLUM_PRESET", "medium"),
        )

    def make_edit(self):
        if not (self.clips_dir and self.song and self.title.text().strip()):
            return
        settings = self.edit_settings()
        self.settings.last_look = settings.look
        self.settings.last_length = settings.length
        self.settings.strict = settings.strict
        settings_mod.save(self.settings)
        song = self.song
        self.result_panel.setVisible(False)
        self.begin("starting…")

        def work(job: Job):
            return pipeline.make_edit(settings, on_progress=job.report, cancel=job.cancel, song=song)

        self.running = self.start_job(work, self.edit_done, self.job_failed)
        self.update_ready()

    def begin(self, text: str):
        self.progress.setValue(0)
        self.progress_row.setVisible(True)
        self.cancel_btn.setEnabled(True)
        self.status.setText(text)
        self.t_start = time.time()

    def on_progress(self, frac: float, stage: str, msg: str, eta):
        self.progress.setValue(int(frac * 1000))
        left = eta_text(eta)
        self.status.setText(f"{msg}{'   ·   ' + left if left else ''}")

    def cancel(self):
        if self.running is not None:
            self.running.cancel.set()
            self.cancel_btn.setEnabled(False)
            self.status.setText("stopping…")

    def edit_done(self, result: pipeline.EditResult):
        self.running = None
        self.result = result
        self.progress_row.setVisible(False)
        mins, secs = divmod(int(result.seconds), 60)
        cuts = len(result.plan.segments)
        rejected = len(result.rejected)
        notes = " ".join(result.plan.notes)
        self.result_label.setText(
            f"<b>Done in {mins}:{secs:02d}.</b> {cuts} cuts, {result.plan.total_frames / 24:.1f} s, "
            f"{result.plan.song['bpm']:.1f} bpm.<br>Saved in <b>{result.out_dir.name}</b> next to your clips."
            + (f"<br>{rejected} file{'s' if rejected != 1 else ''} skipped (see the review for why)." if rejected else "")
            + (f"<br><span style='color:{ASH}'>{notes}</span>" if notes else "")
        )
        self.status.setText("")
        self.result_panel.setVisible(True)
        self.update_ready()

    def job_failed(self, msg: str):
        self.running = None
        self.progress_row.setVisible(False)
        self.update_ready()
        self.error(msg)

    # ------------------------------------------------------------------ after the edit
    def make_hooks(self):
        if self.result is None:
            return
        hooks = [(a.text().strip(), b.text().strip()) for a, b in self.hook_fields]
        if not any(a or b for a, b in hooks):
            self.error("Type at least one hook first (two short lines).")
            return
        res = self.result
        names = pipeline.output_names(res.plan.title)
        self.begin("burning in hooks…")
        self.cancel_btn.setEnabled(False)

        def work(job: Job):
            from .hooks import make_hooks

            job.report(0.2, "files", "burning in hooks…", None)
            return make_hooks(res.files["vertical_post"] if "vertical_post" in res.files else res.out_dir / names["vertical_post"],
                              pipeline.safe_title(res.plan.title), hooks, res.plan.drop_edit, res.out_dir)

        def done(made):
            self.running = None
            self.progress_row.setVisible(False)
            self.status.setText("made " + ", ".join(p.name for p in made))
            self.update_ready()

        self.running = self.start_job(work, done, self.job_failed)
        self.update_ready()

    def swap_shot(self):
        if self.result is None:
            return
        plan_path = self.result.files["plan"]
        plan = EditPlan.load(plan_path)
        dlg = SwapDialog(plan, self)
        if not dlg.exec():
            return
        choice = dlg.choice()
        if choice is None:
            self.error("Pick a shot on the left and a clip on the right.")
            return
        seg, clip = choice
        note = pipeline.swap_shot(plan, seg, clip)
        plan.save(plan_path)
        self.begin(f"re-rendering with {clip} in shot #{seg}…")

        def work(job: Job):
            return pipeline.rerender(plan_path, on_progress=job.report, cancel=job.cancel)

        def done(res: pipeline.EditResult):
            self.edit_done(res)
            if note:
                self.status.setText(f"heads up: {note}")

        self.running = self.start_job(work, done, self.job_failed)
        self.update_ready()


def load_fonts() -> None:
    for f in (paths.GROTESK, paths.JETBRAINS):
        if Path(f).exists():
            QFontDatabase.addApplicationFont(str(f))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Vellum Editor")
    load_fonts()
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Space Grotesk", 13))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
