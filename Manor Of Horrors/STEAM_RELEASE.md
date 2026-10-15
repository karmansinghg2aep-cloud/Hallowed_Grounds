# Hallowed Grounds release preparation

## Build the game

Use a clean Python 3.12 or newer environment on the operating system you are building for. PyInstaller builds must be made separately on macOS, Windows, and Linux; a build made on one OS does not produce the others.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python build_release.py
```

On Windows, activate with `.venv\\Scripts\\activate` and run `py build_release.py`.

The result is under `dist/`. macOS creates `HallowedGrounds.app`; Windows and Linux create an application folder with the executable and its supporting files. Upload the complete folder for each operating system, not just the executable. The build uses the architecture of the Python interpreter that built it, so make a separate Mac build for each processor architecture you choose to support.

The repository also has a manually triggered GitHub Actions workflow, `Build Steam release candidates`. It builds Windows x64, Linux x64, Apple Silicon Mac, and Intel Mac packages, and runs the startup smoke check on each one. The workflow is triggered from GitHub's Actions tab and stores its artifacts for 14 days. It creates build candidates only; it does not upload anything to Steam.

Run a no-window launch check from the project folder with `python manor.py --smoke`. Set `HALLOWED_GROUNDS_DATA_DIR` to a temporary folder when doing this so the check does not read or change your normal saves.

## Test before uploading

- Launch each native build on a clean account with no Python installed.
- Start a new run, quit, relaunch, and confirm all three save slots and settings persist.
- Confirm old source-folder saves migrate on the machine that has them.
- Play the full game on Easy, Normal, and Hard; test each boss, ending, and recovered-title reward.
- Test keyboard remapping or document the fixed controls, window sizing, audio, and quitting.
- Verify macOS signing/notarization and Windows antivirus behavior for the actual distributed builds.
- Record the exact build version and supported operating systems in the Steam store setup.

## Steam upload

Steam upload needs the game's Steamworks App ID, depot IDs, store assets, and a SteamPipe configuration from the Steamworks SDK. Those IDs and store assets must come from the Steamworks account, so this project does not invent them. Upload the builds to a password-protected beta branch first, install them through Steam on a clean account, and only set a build live after that test succeeds.

The macOS build from this project is ad hoc signed. A public Mac release still needs signing and notarization with the developer's Apple certificate. The SteamPipe upload itself also remains manual; see the [official SteamPipe guide](https://partner.steamgames.com/doc/sdk/uploading) for the app/depot config and beta-branch workflow.

## Player data

Settings and saves are stored in the operating system's per-user application data folder. Existing `data/settings.json` and `data/saves/save1.json` through `save3.json` files are copied there once when the game first runs. The original files are left in place.
