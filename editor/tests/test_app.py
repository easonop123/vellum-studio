"""Drive the real app window (headless) through a whole job: folder, song, Make edit, hooks, swap a shot."""
import os
import shutil
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
    except Exception as exc:  # no display libraries on this machine
        pytest.skip(f"Qt can't start here: {exc}")
    from vellum_editor.app import STYLE, load_fonts

    load_fonts()
    app.setStyleSheet(STYLE)
    return app


def wait_until(app, cond, timeout):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.03)
    app.processEvents()
    return cond()


@pytest.mark.slow
def test_app_full_job(qapp, media, tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_SCALE", "0.25")
    monkeypatch.setenv("VELLUM_PRESET", "ultrafast")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    from PySide6.QtWidgets import QMessageBox

    from vellum_editor import app as app_mod

    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a[2] if len(a) > 2 else "")))

    clips = tmp_path / "bali_trip"
    shutil.copytree(media["clips"], clips)
    w = app_mod.MainWindow()
    w.show()
    assert not w.make_btn.isEnabled()

    w.set_clips(str(clips))
    assert w.title.text() == "bali trip"
    w.title.setText("Bali")
    w.set_song(str(media["song"].path))
    assert wait_until(qapp, lambda: w.song is not None, 90), warnings
    assert abs(w.bpm.value() - 120) < 0.5
    assert w.song_panel.isVisible()

    d0 = w.song.drop
    w.nudge_drop(1)
    assert abs(w.song.drop - (d0 + w.song.beat)) < 1e-6
    w.reset_song_nudges()
    assert w.song.drop == d0
    w.bpm.setValue(60.0)
    assert abs(w.song.beat - 1.0) < 1e-9
    w.reset_song_nudges()

    assert w.texture.isChecked() and w.edit_settings().texture  # old film texture is on by default
    w.texture.setChecked(False)  # render this one clean
    assert w.edit_settings().texture is False

    assert w.make_btn.isEnabled()
    w.make_btn.click()
    assert w.busy() and not w.make_btn.isEnabled()
    assert wait_until(qapp, lambda: not w.busy(), 600), warnings
    assert not warnings, warnings
    assert w.result is not None and w.result_panel.isVisible()
    out = clips / "Vellum Edit - Bali"
    for name in ["Bali - vertical (post this).mp4", "Bali - 16x9 (preview with song).mp4", "review.html", "edit-plan.json"]:
        assert (out / name).exists(), name

    # hook versions
    w.hook_fields[0][0].setText("POV: you send me")
    w.hook_fields[0][1].setText("your bali clips")
    w.hooks_btn.click()
    assert wait_until(qapp, lambda: not w.busy(), 300), warnings
    assert (out / "Bali - vertical HOOK 2 (post this).mp4").exists()

    # swap a shot (the dialog is modal, so pick for it)
    def fake_exec(dlg):
        dlg.segs.setCurrentRow(10)
        dlg.clips.setCurrentRow(0)
        return 1

    monkeypatch.setattr(app_mod.SwapDialog, "exec", fake_exec)
    before = (out / "edit-plan.json").stat().st_mtime
    w.swap_shot()
    assert wait_until(qapp, lambda: not w.busy(), 600), warnings
    assert (out / "edit-plan.json").stat().st_mtime > before
    assert not warnings, warnings
    w.close()


def test_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from vellum_editor import settings

    s = settings.load()
    s.lut_apply = "dji"
    s.quality = "smaller"
    settings.save(s)
    again = settings.load()
    assert again.lut_apply == "dji" and again.crf == 21
