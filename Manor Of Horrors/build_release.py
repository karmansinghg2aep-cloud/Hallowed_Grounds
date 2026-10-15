"""Build a native, self-contained Hallowed Grounds folder for the current OS."""
from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
DATA_FILES = ("chapters.json", "rooms.json", "extras.json", "secret_boss.json")


def main():
    missing = [name for name in DATA_FILES if not (ROOT / "data" / name).is_file()]
    if missing:
        raise SystemExit("Missing required game data: " + ", ".join(missing))

    subprocess.run([sys.executable, str(ROOT / "build_icon.py")], cwd=ROOT, check=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--contents-directory", ".",
        "--name", "HallowedGrounds",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
    ]
    if sys.platform == "darwin":
        command.extend(("--osx-bundle-identifier", "com.hallowedgrounds.game",
                        "--icon", str(ROOT / "assets" / "hallowed_grounds_icon.icns")))
    elif sys.platform == "win32":
        command.extend(("--icon", str(ROOT / "assets" / "hallowed_grounds_icon.ico")))
    for filename in DATA_FILES:
        command.extend(("--add-data", str(ROOT / "data" / filename) + os.pathsep + "data"))
    command.extend(("--add-data", str(ROOT / "assets" / "hallowed_grounds_icon.png") + os.pathsep + "assets"))
    command.append(str(ROOT / "manor.py"))
    print("Building Hallowed Grounds for %s..." % sys.platform)
    environment = os.environ.copy()
    environment.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / "build" / "pyinstaller-config"))
    subprocess.run(command, cwd=ROOT, env=environment, check=True)

    if sys.platform == "darwin":
        result = ROOT / "dist" / "HallowedGrounds.app"
    elif sys.platform == "win32":
        result = ROOT / "dist" / "HallowedGrounds" / "HallowedGrounds.exe"
    else:
        result = ROOT / "dist" / "HallowedGrounds" / "HallowedGrounds"
    print("Build created at:", result)


if __name__ == "__main__":
    main()
