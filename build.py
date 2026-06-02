#!/usr/bin/env python
# ============================================================
#  WinHide - Nuitka Build Script
#
#  Reads arguments from nuitka_build_args.txt (or _release.txt)
#  and invokes Nuitka.
#  Works from ANY shell (PowerShell / cmd / Git Bash).
#
#  Automatically resolves and includes DLLs that Nuitka's
#  --include-package-data ignores (e.g. shiboken6.abi3.dll).
#
#  Usage (from project root, with venv activated):
#    python build.py              # debug build (console, no LTO)
#    python build.py --release    # release build (no console, LTO, smaller)
# ============================================================

import importlib.util
import subprocess
import sys
from pathlib import Path


def parse_args_file(path: Path) -> list[str]:
    """Read nuitka_build_args*.txt, strip comments and blank lines."""
    args: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        args.append(line)
    return args


def find_package_dir(package_name: str) -> Path | None:
    """Find the filesystem path of an installed Python package."""
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        return None
    # spec.submodule_search_locations is set for packages
    if spec.submodule_search_locations:
        return Path(spec.submodule_search_locations[0])
    # spec.origin points to __init__.py for packages
    if spec.origin:
        return Path(spec.origin).parent
    return None


def collect_missing_dlls() -> list[str]:
    """
    Collect DLLs that Nuitka --include-package-data won't include.

    Nuitka's PySide6 plugin misses critical DLLs:
    - shiboken6/shiboken6.abi3.dll  (Shiboken.pyd depends on it)
    - PySide6/Qt6*.dll              (Qt framework runtime)
    - PySide6/pyside6.abi3.dll      (PySide6 Python binding runtime)

    --include-package-data explicitly excludes DLLs ("DLLs and extension
    modules are not data files and never included like this"), so we must
    inject them via --include-data-files.
    """
    extra_args: list[str] = []

    # ── shiboken6 ─────────────────────────────────────────
    # Only shiboken6.abi3.dll is needed (Shiboken.pyd already collected)
    shiboken6_dir = find_package_dir("shiboken6")
    if shiboken6_dir:
        dll = shiboken6_dir / "shiboken6.abi3.dll"
        if dll.is_file():
            extra_args.append(f"--include-data-files={dll}=shiboken6/")
            print(f"  [DLL] shiboken6: {dll.name}")
        else:
            print(f"  [WARN] shiboken6.abi3.dll not found at {dll}")

    # ── PySide6 ───────────────────────────────────────────
    # Curated list of REQUIRED DLLs. Do NOT use *.dll glob — PySide6
    # ships 161 DLLs (3D, WebEngine, Bluetooth...) that we don't need.
    PYSIDE6_REQUIRED_DLLS = [
        # Core Qt framework
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Widgets.dll",
        "Qt6Network.dll",
        # SVG support (icon rendering)
        "Qt6Svg.dll",
        "Qt6SvgWidgets.dll",
        # OpenGL (software fallback for headless / RDP)
        "Qt6OpenGL.dll",
        "Qt6OpenGLWidgets.dll",
        "opengl32sw.dll",
        # PySide6 binding runtime
        "pyside6.abi3.dll",
        # MSVC runtime (may already be at dist root, include as backup)
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
    ]

    pyside6_dir = find_package_dir("PySide6")
    if pyside6_dir:
        found = 0
        missing = 0
        for dll_name in PYSIDE6_REQUIRED_DLLS:
            dll_path = pyside6_dir / dll_name
            if dll_path.is_file():
                extra_args.append(f"--include-data-files={dll_path}=PySide6/")
                found += 1
            else:
                print(f"  [WARN] PySide6/{dll_name} not found")
                missing += 1
        print(f"  [DLL] PySide6: {found} included, {missing} missing")
    else:
        print("  [WARN] PySide6 package not found — Qt DLLs will be missing!")

    return extra_args


def main() -> int:
    root = Path(__file__).resolve().parent

    # Determine build mode: --release or debug (default)
    is_release = "--release" in sys.argv

    if is_release:
        args_file = root / "nuitka_build_args_release.txt"
        build_mode = "RELEASE"
    else:
        args_file = root / "nuitka_build_args.txt"
        build_mode = "DEBUG"

    if not args_file.is_file():
        print(f"[ERROR] Args file not found: {args_file}")
        return 1

    nuitka_args = parse_args_file(args_file)

    # Collect DLLs that --include-package-data won't cover
    dll_args = collect_missing_dlls()
    nuitka_args.extend(dll_args)

    cmd = [sys.executable, "-m", "nuitka", *nuitka_args, "src/app.py"]

    print("=" * 60)
    print(f"  WinHide - Nuitka Build ({build_mode})")
    print("=" * 60)
    print(f"  Args file : {args_file}")
    print(f"  Arguments : {len(nuitka_args)}")
    print(f"  Working dir: {root}")
    print("=" * 60)
    print()

    result = subprocess.run(cmd, cwd=str(root))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
