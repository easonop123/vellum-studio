"""Entry point for the packaged app (PyInstaller) and for running the window from source.

  python run_app.py              open the window
  python run_app.py --selftest   make a tiny test edit without the window (used by the build to check the .app works)
"""
import multiprocessing
import os
import sys


def _unquarantine_self() -> None:
    """Downloaded apps carry a quarantine flag on every file inside. Once you've chosen to open the app,
    clear it from the app's own files so the bundled ffmpeg can run."""
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return
    exe = os.path.realpath(sys.executable)
    bundle = exe.split(".app/")[0] + ".app" if ".app/" in exe else None
    if bundle:
        try:
            import subprocess

            subprocess.run(["xattr", "-dr", "com.apple.quarantine", bundle], capture_output=True, timeout=20)
        except Exception:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()  # must come first: worker processes re-enter here
    _unquarantine_self()
    if "--selftest" in sys.argv:
        from vellum_editor.cli import main as cli_main

        sys.exit(cli_main(["selftest"]))
    from vellum_editor.app import main

    sys.exit(main())
