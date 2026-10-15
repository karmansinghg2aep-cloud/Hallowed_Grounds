"""
HALLOWED GROUNDS
A 2D escape-room platformer told through recovered VHS tapes.

Files this game needs (all in the same folder as manor.py):
    visuals.py, sound.py, analog.py   the pictures, the audio and the "old tape" look
    data/chapters.json                the look and difficulty of each tape (chapter)
    data/rooms.json                   every room, its monsters, and its tape text
    data/extras.json                  notes, secrets, safe rooms, dark rooms, hiding spots (optional)

Settings and saves are created in the user's application-data folder. Existing local saves are
copied there the first time the game starts.

Run it with:   python3 manor.py
Check where the extras landed in every room:   python3 manor.py --check
Smoke-test startup and menu rendering: python3 manor.py --smoke

HOW THIS FILE IS ORGANIZED (top to bottom):
    1.  Constants
    2.  Loading data, settings and saves
    3.  Small helper functions (including where extras are placed)
    4.  The Monster class
    5.  Drawing functions
    6.  Menus and screens (including the ending)
    7.  play_room()  - the heart of the game
    8.  run_game() and main() - the flow between rooms
"""
import json
import math
import os
import random
import shutil
import sys
import tempfile
import traceback

import pygame


# If sound.py or analog.py are missing, the game still runs (silent / clean picture).
class _NoParticles:
    """Stands in for the particle system so the player sprite has nowhere to put its dust puffs."""
    def emit(self, *args, **kwargs):
        pass

    def burst(self, *args, **kwargs):
        pass


_NO_PARTICLES = _NoParticles()


class _Silent:
    """Stands in for a missing module. Every call does nothing."""
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


try:
    import sound
except ImportError:
    sound = _Silent()
try:
    import analog
except ImportError:
    analog = _Silent()

# An older analog.py has no set_boss (the boss-only glitch). Add a do-nothing version so the game still runs,
# but you will only get the new "clean rooms, glitchy boss" look once analog.py is updated.
if not hasattr(analog, "set_boss"):
    analog.set_boss = lambda *args, **kwargs: None


try:
    import visuals
except ImportError:
    sys.exit("visuals.py is missing. Put it in the same folder as manor.py (next to sound.py and analog.py).")


# ==================================================================
# 1. CONSTANTS
# ==================================================================
WIDTH, HEIGHT = 800, 500
FPS = 60
BEAM_SAFE_LANE = 128  # The Signal cannot reach the two marked wall-side shelters.

# Player feel. Change these to change how the game plays!
PLAYER_W, PLAYER_H = 28, 40
MOVE_SPEED = 5
GRAVITY = 0.6
JUMP_SPEED = -12.5
MAX_FALL_SPEED = 14
COYOTE_FRAMES = 6          # you can still jump for 6 frames after walking off a ledge
JUMP_BUFFER_FRAMES = 6     # a jump pressed 6 frames too early still counts
JUMP_CUT = -7.0            # letting go of jump early cuts the rise to this speed, so even a light tap is a real hop
KNOCKBACK_FRAMES = 12

# Running and noise. Hold Shift to run: it is fast, but it costs stamina and it is LOUD.
RUN_SPEED = 7
STAMINA_MAX = 100.0
STAMINA_DRAIN = 0.8        # stamina lost per frame while running (about 2 seconds of running)
STAMINA_REGEN = 0.5        # stamina gained per frame while NOT running
STAMINA_RECOVER = 30.0     # after you run out, you can only run again once stamina climbs back to this
NOISE_RUN = 320            # how far away (pixels) a creature could hear a running step
NOISE_WALK = 110           # ...and a walking step. Standing still makes no noise at all.
NOISE_LIFE = 45            # frames a noise event lasts before it fades away

# Hiding in gaps in the recording, the flashlight, and the Hush
HIDE_KEYS = (pygame.K_DOWN, pygame.K_s, pygame.K_e)
HIDE_FOUND_FRAMES = 150    # a Designation close to the gap this long finds you
BATTERY_MAX = 100.0
BATTERY_DRAIN = 0.015      # lost per frame in a dark room (about 110 seconds of light)
BATTERY_PICKUP = 35.0
LIGHT_R_MAX, LIGHT_R_MIN = 170, 70     # flashlight radius: full battery -> empty battery
HUSH_SPEED = 2.0           # how fast the Hush roams the room
HUSH_RANGE = 230           # how close (pixels, sideways) it has to be to swallow the sound
HUSH_FADE_FRAMES = 120     # the sound fades away over 2 seconds. That fade is the warning.

BUILD = "build 8: fair boss patterns"              # shown in the window title so you can tell which file is running

# Visual switches. True = shown, False = hidden.
PLAYER_PUFFS = False        # the round dust puffs when you jump, land and walk (they come from visuals.py)
SHOW_NOISE_RINGS = False    # the thin grey rings that show how far your footsteps carry (True = show them)

DESIGNATIONS = ("patroller", "flyer", "chaser", "shooter")   # creatures that can find you in a gap

KEY_SIZE = 30
TAPE_W, TAPE_H = 26, 20
NUM_SLOTS = 3

JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)
CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_SPACE)

BLACK = (0, 0, 0)
WHITE = (235, 235, 235)
GREY = (150, 145, 155)
RED = (200, 60, 60)

# Files and folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
DATA_DIR = os.path.join(RESOURCE_DIR, "data")


def user_data_directory():
    """Return a writable per-user directory for saves and settings on each OS."""
    override = os.environ.get("HALLOWED_GROUNDS_DATA_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        root = os.path.join(home, "Library", "Application Support")
    else:
        root = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    return os.path.join(root, "Hallowed Grounds")


USER_DATA_DIR = user_data_directory()
SAVE_DIR = os.path.join(USER_DATA_DIR, "saves")
SETTINGS_PATH = os.path.join(USER_DATA_DIR, "settings.json")
_legacy_data_migrated = False


def migrate_legacy_user_data():
    """Copy existing local saves once, without replacing newer app-data files."""
    global _legacy_data_migrated
    if _legacy_data_migrated:
        return
    os.makedirs(SAVE_DIR, exist_ok=True)
    legacy_dirs = (os.path.join(BASE_DIR, "data"), DATA_DIR)
    for legacy_dir in legacy_dirs:
        for relative in ("settings.json", *("saves/save%d.json" % slot for slot in range(1, NUM_SLOTS + 1))):
            source = os.path.join(legacy_dir, relative)
            target = os.path.join(USER_DATA_DIR, relative)
            if os.path.abspath(source) == os.path.abspath(target) or os.path.exists(target):
                continue
            if os.path.isfile(source):
                os.makedirs(os.path.dirname(target), exist_ok=True)
                try:
                    shutil.copy2(source, target)
                except OSError as exc:
                    print("Could not migrate %s: %s" % (relative, exc))
    _legacy_data_migrated = True


def write_json_atomically(path, data):
    """Write JSON through a temporary file so an interrupted save stays recoverable."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=os.path.dirname(path),
                                         prefix=".save-", suffix=".tmp", delete=False) as f:
            temp_path = f.name
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# The Guide's voice (calm, polite, wrong)
GUIDE_LINES = [
    "Thank you for your compliance. Your escape response is within the expected range.",
    "You are not the first person to stand exactly where you are standing now.",
    "If a voice you recognize speaks from a room marked STAY, do not answer it.",
    "The gaps in this recording are harmless. The Auditor will confirm this.",
    "The Program does not end when the tape does. It has never once ended.",
]
GAME_OVER_LINES = [
    "SUBJECT %d NOT RECOVERED. This footage has been marked for reuse.",
    "Please remain still. The Auditor has already filed your position.",
    "The Program regrets the interruption. It has regretted it %d times before.",
    "TRACKING LOST. Rewinding to the last approved frame. This is routine.",
    "You left the marked path. Subject %d also left the marked path.",
]
LOOP_NOTE = "NOTE 00 [SCRATCHED] THIS ROOM LOOKED SMALLER THE LAST TIME. I KEEP COUNTING THE SAME NUMBER."

# Filled in when the game starts (see load_game_data / load_settings)
CHAPTERS = {}          # chapter id -> its info from chapters.json
CHAPTER_ORDER = []     # chapter ids in file order (tape 1, tape 2, ...)
ROOMS = []             # every room from rooms.json
EXTRAS = {}            # everything from extras.json (notes, secrets, safe rooms...)
FIRST_SEEN_KIND = {}   # monster kind -> index of the first room it appears in (for a one-time jumpscare)
RUN = {"battery": BATTERY_MAX}     # the flashlight battery is carried from room to room
ARTIFACTS = ("bell_clapper", "sealed_writ", "negative_frame")
SECRET_BOSS_ROOM = None

# These are saved in settings.json, so they survive quitting:
#   subject_count  the Subject number. It NEVER resets.
#   loops          how many times the player chose STAY at the ending
#   ending         "", "stay" or "let_go"  (the last choice they made)
#   secrets        room numbers whose secret wall has been opened
#   twist_done     True once the "retired Subject number" has been shown (it only happens once)
DEFAULT_SETTINGS = {"volume": 70, "chapter_intros": True, "difficulty": "normal",
                    "subject_count": 0, "loops": 0, "ending": "", "secrets": [], "twist_done": False,
                    "unlocked_titles": [], "active_title": ""}
TITLE_REWARDS = {
    "FIRST FOOTAGE": "Escape the first room. Sprint uses less stamina.",
    "ARCHIVIST": "Collect three story files. Unseal the unlisted rooms; relics glow nearby.",
    "THE HOUSE KNOWS": "Escape the Auditor's room. Gain one extra heart.",
    "STILL HERE": "Finish the first tape. Stamina recovers faster.",
    "BELOW THE RECORD": "Reach the final tape. Flashlight drains more slowly.",
    "NO EXIT": "Finish the full game. Boss hits deal extra damage.",
    "<dev>": "A private title. Press Tab in a room to skip it.",
}
settings = dict(DEFAULT_SETTINGS)
settings["secrets"] = []
FONTS = {}

# Difficulty presets. Change these numbers to tune the game!
#   lives           hearts you start each tape with
#   monster_speed   every monster's speed is multiplied by this
#   detect          how far away a chaser notices you
#   fire            shooter delay between shots (bigger = slower shooting)
#   projectile      speed of shooter bullets
#   invincible      frames of safety after a hit (60 frames = 1 second)
#   crumble         frames a crumbling platform lasts once you stand on it
#   pit_costs_life  does falling into a pit cost a heart?
DIFFICULTIES = ["easy", "normal", "hard"]
PRESETS = {
    "easy":   {"lives": 5, "monster_speed": 0.85, "detect": 0.90, "fire": 1.25, "projectile": 0.90,
               "invincible": 100, "crumble": 70, "pit_costs_life": False},
    "normal": {"lives": 3, "monster_speed": 1.10, "detect": 1.10, "fire": 0.90, "projectile": 1.05,
               "invincible": 80, "crumble": 45, "pit_costs_life": True},
    "hard":   {"lives": 2, "monster_speed": 1.30, "detect": 1.25, "fire": 0.75, "projectile": 1.15,
               "invincible": 60, "crumble": 30, "pit_costs_life": True},
}


def preset():
    """The settings for the difficulty the player picked."""
    return PRESETS.get(settings.get("difficulty", "normal"), PRESETS["normal"])


def max_lives():
    return preset()["lives"] + (1 if settings.get("active_title") == "THE HOUSE KNOWS" else 0)


def title_active(title):
    return settings.get("active_title") == title


# ==================================================================
# 2. LOADING DATA, SETTINGS AND SAVES
# ==================================================================
def load_json(filename):
    """Reads a JSON file. If it has a typo, says WHERE (a great habit to learn)."""
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        sys.exit("Can't find %s. Is the data folder next to manor.py?" % path)
    except json.JSONDecodeError as e:
        sys.exit("%s has a typo near line %d, column %d: %s" % (filename, e.lineno, e.colno, e.msg))


def load_extras():
    """data/extras.json is optional. Without it the game plays like the old version."""
    EXTRAS.clear()
    path = os.path.join(DATA_DIR, "extras.json")
    if not os.path.exists(path):
        return
    data = load_json("extras.json")
    if isinstance(data, dict):
        EXTRAS.update(data)
    else:
        sys.exit("extras.json should start with { but it holds a %s." % type(data).__name__)


def load_game_data():
    """Loads chapters.json and rooms.json, then checks them for mistakes."""
    chapters = load_json("chapters.json")
    if not isinstance(chapters, dict):
        sys.exit('chapters.json should start with { (a dictionary of chapters) but it holds a %s. '
                 'Did rooms.json get copied into chapters.json by mistake?' % type(chapters).__name__)
    for name, info in chapters.items():
        if not isinstance(info, dict):
            sys.exit('chapters.json: chapter "%s" should be a { } block, but it is a %s.' % (name, type(info).__name__))
    CHAPTERS.clear()
    CHAPTERS.update(chapters)
    CHAPTER_ORDER[:] = list(CHAPTERS.keys())
    rooms = load_json("rooms.json")
    if not isinstance(rooms, list):
        sys.exit('rooms.json should start with [ (a list of rooms) but it holds a %s. '
                 'Did chapters.json get copied into rooms.json by mistake?' % type(rooms).__name__)
    ROOMS[:] = rooms
    global SECRET_BOSS_ROOM
    secret_boss_path = os.path.join(DATA_DIR, "secret_boss.json")
    SECRET_BOSS_ROOM = load_json("secret_boss.json") if os.path.isfile(secret_boss_path) else None
    validate_data()
    load_extras()
    FIRST_SEEN_KIND.clear()
    for i, room in enumerate(ROOMS):
        for m in room.get("monsters", []):
            FIRST_SEEN_KIND.setdefault(m["kind"], i)


def validate_data():
    """Catches mistakes in the JSON files early, with a clear message."""
    if not ROOMS:
        sys.exit("rooms.json has no rooms in it.")
    needed = ("chapter", "platforms", "key", "door", "player_start")
    for i, room in enumerate(ROOMS):
        for field in needed:
            if field not in room:
                sys.exit('rooms.json: room %d is missing "%s".' % (i + 1, field))
        if room["chapter"] not in CHAPTERS:
            sys.exit('rooms.json: room %d uses chapter "%s", which is not in chapters.json.'
                     % (i + 1, room["chapter"]))
    # A chapter's rooms must sit together, or "tape complete" would show too early.
    seen, previous = set(), None
    for room in ROOMS:
        if room["chapter"] != previous and room["chapter"] in seen:
            print('Warning: chapter "%s" appears in two separate groups of rooms.' % room["chapter"])
        seen.add(room["chapter"])
        previous = room["chapter"]


def load_settings():
    migrate_legacy_user_data()
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for key in DEFAULT_SETTINGS:
            if key in saved:
                settings[key] = saved[key]
    except (FileNotFoundError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    if settings.get("difficulty") not in PRESETS:
        settings["difficulty"] = "normal"
    # Counters must always be whole numbers that are never negative, even if the file was edited by hand.
    for key in ("subject_count", "loops"):
        try:
            settings[key] = max(0, int(settings.get(key, 0)))
        except (TypeError, ValueError):
            settings[key] = 0
    if settings.get("ending") not in ("", "stay", "let_go"):
        settings["ending"] = ""
    secrets = settings.get("secrets")
    settings["secrets"] = [s for s in secrets if isinstance(s, int)] if isinstance(secrets, list) else []
    settings["twist_done"] = bool(settings.get("twist_done", False))
    unlocked = settings.get("unlocked_titles", [])
    settings["unlocked_titles"] = [t for t in unlocked if t in TITLE_REWARDS] if isinstance(unlocked, list) else []
    active = settings.get("active_title", "")
    settings["active_title"] = active if active in settings["unlocked_titles"] else ""


def save_settings():
    migrate_legacy_user_data()
    write_json_atomically(SETTINGS_PATH, settings)


def save_path(slot):
    return os.path.join(SAVE_DIR, "save%d.json" % slot)


def read_save(slot):
    """Returns a dict for the slot, or None if the slot is empty (or unreadable)."""
    migrate_legacy_user_data()
    try:
        with open(save_path(slot)) as f:
            data = json.load(f)
        return {
            "room_index": max(0, int(data.get("room_index", 0))),
            "lives": max(1, int(data.get("lives", max_lives()))),
            "collected_scrolls": [c for c in data.get("collected_scrolls", []) if isinstance(c, str)],
            "collected_artifacts": [c for c in data.get("collected_artifacts", []) if c in ARTIFACTS],
            "secret_boss_defeated": bool(data.get("secret_boss_defeated", False)),
        }
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return None


def write_save(slot, room_index, lives, collected, collected_artifacts=None, secret_boss_defeated=False):
    migrate_legacy_user_data()
    write_json_atomically(save_path(slot), {
        "room_index": room_index,
        "lives": lives,
        "collected_scrolls": collected,
        "collected_artifacts": list(collected_artifacts or []),
        "secret_boss_defeated": bool(secret_boss_defeated),
    })


def unlock_title(title):
    """Remember a newly earned title. Returns True only the first time it is earned."""
    if title not in TITLE_REWARDS or title in settings["unlocked_titles"]:
        return False
    settings["unlocked_titles"].append(title)
    save_settings()
    return True


def slot_label(slot):
    save = read_save(slot)
    if save is None:
        status = "(Empty)"
    elif save["room_index"] >= len(ROOMS):
        status = "(Completed)"
    else:
        status = "(Room %d)" % (save["room_index"] + 1)
    return "Slot %d  %s" % (slot, status)


# ==================================================================
# 3. SMALL HELPER FUNCTIONS
# ==================================================================
def quit_game():
    pygame.quit()
    sys.exit()


def make_fonts():
    FONTS["small"] = pygame.font.Font(None, 22)
    FONTS["body"] = pygame.font.Font(None, 28)
    FONTS["big"] = pygame.font.Font(None, 38)
    FONTS["title"] = pygame.font.Font(None, 72)
    FONTS["mono"] = pygame.font.SysFont("couriernew,courier,menlo,monospace", 22, bold=True)
    FONTS["mono_small"] = pygame.font.SysFont("couriernew,courier,menlo,monospace", 17, bold=True)


def mix(c1, c2, t):
    """Blend two colors. t=0 gives c1, t=1 gives c2."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_text(surface, text, font, color, x, y, center=False, shadow=(0, 0, 0)):
    """Draws text (with a little shadow) and returns its rectangle."""
    if shadow:
        shade = font.render(text, True, shadow)
        r = shade.get_rect(center=(x, y)) if center else shade.get_rect(topleft=(x, y))
        surface.blit(shade, r.move(2, 2))
    img = font.render(text, True, color)
    r = img.get_rect(center=(x, y)) if center else img.get_rect(topleft=(x, y))
    surface.blit(img, r)
    return r


def wrap_text(text, font, max_width):
    """Splits text into lines that each fit inside max_width pixels."""
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def present(screen, tape_no):
    """Puts the finished picture on screen, with the tape effect on top."""
    analog.draw(screen, tape_no)
    pygame.display.flip()


def chapter_number(room):
    """0 for the first tape, 1 for the second, ..."""
    return CHAPTER_ORDER.index(room["chapter"])


def chapter_info(room):
    return CHAPTERS[room["chapter"]]


def is_first_in_chapter(index):
    return index == 0 or ROOMS[index - 1]["chapter"] != ROOMS[index]["chapter"]


def is_last_in_chapter(index):
    return index == len(ROOMS) - 1 or ROOMS[index + 1]["chapter"] != ROOMS[index]["chapter"]


def chapter_position(index):
    """(position of the room inside its tape, number of rooms in that tape). Used to change the background as a tape goes on."""
    first = last = index
    while first > 0 and ROOMS[first - 1]["chapter"] == ROOMS[index]["chapter"]:
        first -= 1
    while last < len(ROOMS) - 1 and ROOMS[last + 1]["chapter"] == ROOMS[index]["chapter"]:
        last += 1
    return index - first, last - first + 1


def room_display_name(index):
    """Rooms are just numbers now: ROOM 12."""
    return "ROOM %d" % (index + 1)


def split_chapter_title(chap_no):
    """'TAPE 02: The Old Hallways' -> ('TAPE 02', 'The Old Hallways')."""
    display = CHAPTERS[CHAPTER_ORDER[chap_no]]["display_name"]
    label, colon, name = display.partition(":")
    if not colon:
        return "TAPE %02d" % (chap_no + 1), display
    return label.strip(), name.strip()


def split_tape(text):
    """'TAPE 01 [00:12] Stay on the path.' -> ('TAPE 01 [00:12]', 'Stay on the path.')
    Notes work the same way: 'NOTE 07 [SCRATCHED] Don't look.' -> ('NOTE 07 [SCRATCHED]', "Don't look.")"""
    if (text.startswith("TAPE") or text.startswith("NOTE")) and "]" in text:
        cut = text.index("]") + 1
        return text[:cut], text[cut:].strip()
    return "", text


def tape_label(text):
    header, body = split_tape(text)
    return header if header else body[:32]


def build_monsters(room, difficulty, index=None, strip=False):
    """Makes the Monster objects for a room. Two things make monsters tougher:
    the chapter's difficulty (later tapes are harder) and the player's difficulty setting.
    strip=True builds none at all (safe rooms). From room 15 on, some rooms hide a COPY (Designation 05)."""
    if strip:
        return []
    p = preset()
    monsters = []
    for cfg in room.get("monsters", []):
        cfg = dict(cfg)
        if "speed" in cfg:
            cfg["speed"] = cfg["speed"] * difficulty * p["monster_speed"]
        if "detect_radius" in cfg:
            cfg["detect_radius"] = cfg["detect_radius"] * difficulty * p["detect"]
            # A chaser must go back to sleep at a bigger distance than it wakes at, or it flickers awake/asleep.
            cfg["sleep_radius"] = max(cfg.get("sleep_radius", 250), cfg["detect_radius"] + 15)
        if cfg.get("kind") == "chaser" and "speed" in cfg:
            cfg["speed"] = min(cfg["speed"], MOVE_SPEED * 0.7)   # a chaser can never be almost as fast as you, on any difficulty
        if cfg.get("kind") == "doorstalker":
            cfg.setdefault("doors", room.get("boss_doors", []))
            cfg["speed"] = min(cfg.get("speed", 5.5), MOVE_SPEED * 1.4)   # a dash is telegraphed, so it may be quick
            cfg["telegraph"] = max(25, int(cfg.get("telegraph", 55) * p["fire"]))   # easier setting = more warning (p["fire"] is bigger on Easy)
        if cfg.get("kind") == "shooter":
            cfg["fire_interval"] = max(30, int(cfg.get("fire_interval", 100) * p["fire"]))
            cfg["projectile_speed"] = cfg.get("projectile_speed", 5) * p["projectile"]
        if cfg.get("kind") == "warden":
            cfg["phase1_speed"] = cfg.get("phase1_speed", 2.0) * p["monster_speed"]
            cfg["phase2_fire"] = max(45, int(cfg.get("phase2_fire", 95) * p["fire"]))
            cfg["phase2_speed"] = cfg.get("phase2_speed", 4.5) * p["projectile"]
            cfg["phase3_speed"] = min(cfg.get("phase3_speed", 3.2) * p["monster_speed"], MOVE_SPEED * 0.7)
        monsters.append(Monster(cfg))

    # Designation 05, "the Missing One": a copy of a creature you already know, with ONE thing changed by about 30%.
    if index is not None and index >= 14 and index % 3 == 0:
        pool = [m for m in monsters if m.kind in DESIGNATIONS]
        if pool:
            rng = random.Random(index * 31 + 5)
            m = rng.choice(pool)
            factor = rng.choice((0.7, 1.3))
            m.is_copy = True
            if m.kind in ("patroller", "flyer"):
                m.speed *= factor
            elif m.kind == "chaser":
                if rng.random() < 0.5:
                    m.speed = min(m.speed * factor, MOVE_SPEED * 0.7)   # the fairness cap still applies
                else:
                    m.detect_radius *= factor
                    m.sleep_radius = max(m.sleep_radius, m.detect_radius + 15)
            elif m.kind == "shooter":
                m.fire_interval = max(30, int(m.fire_interval * factor))
                m.cooldown = m.fire_interval
    return monsters


# ---------- Traps ----------
def room_platforms(room):
    """The room's solid platforms. Any "pits" cut holes out of the floor: "pits": [[x, width], ...]."""
    plats = [list(p) for p in room["platforms"]]
    pits = sorted(room.get("pits", []))
    if not pits:
        return plats
    out = []
    for p in plats:
        if p[0] == 0 and p[1] == 460 and p[2] == 800:          # the full floor
            x = 0
            for px, pw in pits:
                if px > x:
                    out.append([x, 460, px - x, p[3]])
                x = px + pw
            if x < 800:
                out.append([x, 460, 800 - x, p[3]])
        else:
            out.append(p)
    return out


def trap_active(trap, frame):
    """Spikes are always dangerous. Pulsing spikes are dangerous for 'on' frames out of every 'period'."""
    if trap.get("kind") == "pulse":
        return (frame + trap.get("offset", 0)) % trap["period"] < trap["on"]
    return True


def trap_warning(trap, frame):
    """True in the last moments before a pulsing trap pops up, so the player gets a fair warning."""
    if trap.get("kind") != "pulse":
        return False
    return (frame + trap.get("offset", 0)) % trap["period"] >= trap["period"] - 25


# ---------- Where the extras go ----------
# Gaps, notes, batteries and secret walls are NOT placed by hand. The computer looks for a spot on the
# floor that is far from pits, spikes, patrol paths, platforms, the door, the key and where you start.
def floor_avoid_rects(room, include_monsters=True):
    """Rectangles on the floor that no extra is allowed to touch."""
    avoid = []

    def span(lo, hi):
        avoid.append(pygame.Rect(int(lo), 0, int(hi - lo), HEIGHT))

    for px, pw in room.get("pits", []):
        span(px - 30, px + pw + 30)
    for t in room.get("traps", []):
        span(t["x"] - 50, t["x"] + t["w"] + 50)
    for m in room.get("monsters", []) if include_monsters else []:
        size = m.get("size", 34)
        if m.get("y", 0) + size < 420:
            continue                                    # flyers and monsters on platforms never reach the floor spots
        kind = m.get("kind")
        if kind == "patroller":
            lo, hi = m.get("range", [0, WIDTH])
            span(lo - 40, hi + size + 40)
        elif kind in ("shooter", "chaser"):
            span(m["x"] - 100, m["x"] + size + 100)
    for p in room["platforms"]:
        if p[1] < 455:
            avoid.append(pygame.Rect(*p).inflate(12, 12))
    for c in room.get("crumbles", []):
        avoid.append(pygame.Rect(*c).inflate(12, 12))
    avoid.append(pygame.Rect(*room["door"]).inflate(60, 60))
    avoid.append(pygame.Rect(room["key"][0], room["key"][1], KEY_SIZE, KEY_SIZE).inflate(40, 40))
    sx, sy = room["player_start"]
    avoid.append(pygame.Rect(sx, sy, PLAYER_W, PLAYER_H).inflate(80, 80))
    if "scroll_pos" in room:
        avoid.append(pygame.Rect(room["scroll_pos"][0], room["scroll_pos"][1], TAPE_W, TAPE_H).inflate(40, 40))
    if room.get("charge_item"):
        avoid.append(pygame.Rect(room["charge_item"][0], room["charge_item"][1], 26, 26).inflate(40, 40))
    for bx, by in room.get("boss_doors", []):
        avoid.append(pygame.Rect(bx, by, 46, 90).inflate(20, 20))
    return avoid


def floor_blocked(room, rect, taken):
    return any(rect.colliderect(a) for a in floor_avoid_rects(room) + list(taken))


def place_on_floor(room, w, h, taken, rng):
    """Finds a w-by-h spot standing on the floor that is safe, or None. 'taken' holds spots already used."""
    avoid = floor_avoid_rects(room) + list(taken)
    xs = list(range(60, WIDTH - 60 - w, 10))
    rng.shuffle(xs)                                     # the same room always shuffles the same way (seeded rng)
    for x in xs:
        r = pygame.Rect(x, 460 - h, w, h)
        if not any(r.colliderect(a) for a in avoid):
            return r
    return None


def place_risky_extra(room, room_no, kind, w, h, taken):
    """Use a hand-picked, monster-exposed floor spot when a room has no safe spot."""
    x = EXTRAS.get("risky_placements", {}).get(str(room_no), {}).get(kind)
    if x is None:
        return None
    rect = pygame.Rect(int(x), 460 - h, w, h)
    blockers = floor_avoid_rects(room, include_monsters=False) + list(taken)
    if any(rect.colliderect(blocker) for blocker in blockers):
        return None
    return rect


def plan_extras(room, index, collected_artifacts=None):
    """Decides everything extra about one room, without playing it:
    safe room? dark room? where is the footage gap, note, battery, secret wall, and marks?"""
    room_no = index + 1
    rng = random.Random(index * 7919 + 101)
    safe = room_no in EXTRAS.get("safe_rooms", [])
    view = dict(room, monsters=[], traps=[]) if safe else room    # a safe room has no creatures or spikes to avoid
    plan = {"room_no": room_no, "safe": safe, "dark": room_no in EXTRAS.get("dark_rooms", []) and not safe,
            "hide": None, "note": None, "battery": None, "secret": None,
            "audit": room_no in EXTRAS.get("audit_rooms", []) and not safe,
            "hush": room_no in EXTRAS.get("hush_rooms", []) and not safe,
            "label": EXTRAS.get("lie_labels", {}).get(str(room_no), room_display_name(index)),
            "marks": [], "skipped": [], "risky": [], "artifact": None}
    taken = []
    boss = bool(room.get("boss_intro"))

    entry = EXTRAS.get("secrets", {}).get(str(room_no))
    if entry and entry.get("requires_title") and not title_active(entry["requires_title"]):
        entry = None
    if entry and not safe and not boss:
        panel = place_on_floor(view, 30, 60, taken, rng)
        risky = False
        if panel is None:
            panel = place_risky_extra(view, room_no, "secret", 30, 60, taken)
            risky = panel is not None
        if panel is None:
            plan["skipped"].append("secret wall (no safe floor)")
        else:
            side = "left" if panel.centerx < WIDTH // 2 else "right"     # which way the panel slides when it opens
            plan["secret"] = {"panel": panel, "side": side, "text": entry["text"],
                              "note_rect": pygame.Rect(panel.centerx - 10, 444, 20, 16), "risky": risky,
                              "reward": entry.get("reward", "life"), "unlisted": bool(entry.get("unlisted"))}
            if risky:
                plan["risky"].append("secret wall")
            taken.append(panel.inflate(30, 0))

    if room_no in EXTRAS.get("hide_rooms", []) and not safe and not boss:
        spot = place_on_floor(view, 30, 56, taken, rng)
        risky = False
        if spot is None:
            spot = place_risky_extra(view, room_no, "gap", 30, 56, taken)
            risky = spot is not None
        if spot is None:
            plan["skipped"].append("recording gap (no safe floor)")
        else:
            plan["hide"] = spot
            if risky:
                plan["risky"].append("gap")
            taken.append(spot.inflate(30, 0))

    text = EXTRAS.get("notes", {}).get(str(room_no))
    if text is None and room_no == 1 and settings.get("loops", 0) > 0:
        text = LOOP_NOTE
    if text and not boss:
        spot = place_on_floor(view, 20, 16, taken, rng)
        if spot is None:
            plan["skipped"].append("note (no safe floor)")
        else:
            plan["note"] = {"rect": spot, "text": text}
            taken.append(spot.inflate(30, 0))

    artifact = EXTRAS.get("artifacts", {}).get(str(room_no))
    if artifact and artifact.get("id") not in (collected_artifacts or []) and not safe and not boss:
        spot = place_on_floor(view, 24, 24, taken, rng)
        if spot is not None:
            plan["artifact"] = dict(artifact, rect=spot)
            taken.append(spot.inflate(30, 0))
        else:
            plan["skipped"].append("relic (no safe floor)")

    if plan["dark"]:
        spot = place_on_floor(view, 18, 22, taken, rng)
        risky = False
        if spot is None:
            spot = place_risky_extra(view, room_no, "battery", 18, 22, taken)
            risky = spot is not None
        if spot is None:
            plan["skipped"].append("battery (no safe floor)")
        else:
            plan["battery"] = spot
            if risky:
                plan["risky"].append("battery")
            taken.append(spot.inflate(30, 0))

    # Marks left by earlier Subjects (decoration only, they never touch the player)
    marks = plan["marks"]
    if view.get("monsters") and not boss:
        marks.append({"kind": "scratch", "x": rng.randint(60, 740), "y": rng.randint(130, 330), "count": 4})
    for m in view.get("monsters", []):
        if m.get("kind") == "chaser":
            sx = m["x"] - 70 if m["x"] > 120 else m["x"] + 90
            marks.append({"kind": "shoe", "x": int(sx), "y": 458})
    if plan["secret"]:                                   # a chalk arrow on the wall, 90 pixels away, pointing at the panel
        px = plan["secret"]["panel"].centerx
        toward = 1 if px > WIDTH // 2 else -1
        marks.append({"kind": "arrow", "x": px - toward * 90, "y": 380, "dir": toward})
    if index % 7 == 3 and not safe and not boss:
        marks.append({"kind": "trail", "x": rng.randint(200, 500), "y": 458, "n": 6})
    return plan


def check_extras():
    """python3 manor.py --check : prints what got placed in every room (no game window needed)."""
    load_game_data()
    load_settings()
    print("Rooms: %d.  Extras file found: %s" % (len(ROOMS), "yes" if EXTRAS else "NO (the game still plays)"))
    for i, room in enumerate(ROOMS):
        p = plan_extras(room, i)
        bits = []
        if p["safe"]:
            bits.append("SAFE ROOM")
        if p["dark"]:
            bits.append("dark")
        if p["hide"]:
            bits.append("gap x=%d" % p["hide"].x)
        if p["note"]:
            bits.append("note x=%d" % p["note"]["rect"].x)
        if p["battery"]:
            bits.append("battery x=%d" % p["battery"].x)
        if p["artifact"]:
            bits.append("relic: %s x=%d" % (p["artifact"]["name"], p["artifact"]["rect"].x))
        if p["secret"]:
            bits.append("secret wall on the %s%s" % (p["secret"]["side"], " (UNLISTED inside)" if p["secret"]["unlisted"] else ""))
        if p["hush"]:
            bits.append("THE HUSH")
        if p["audit"]:
            bits.append("AUDITOR")
        if p["risky"]:
            bits.append("RISKY placement: " + ", ".join(p["risky"]))
        if p["label"] != room_display_name(i):
            bits.append('sign lies: "%s"' % p["label"])
        for s in p["skipped"]:
            bits.append("SKIPPED " + s)
        if bits:
            print("Room %2d: %s" % (i + 1, ", ".join(bits)))


# ==================================================================
# 4. THE MONSTER CLASS
# ==================================================================
class Monster:
    """
    patroller  walks back and forth on a fixed path        (greed)
    flyer      patrols sideways while bobbing up and down  (despair)
    chaser     sleeps until you are close, then chases     (rage)
    shooter    stands still, fires when you are level      (envy)
    plus the five bosses: doorstalker, beamer, summoner, guardian, warden.
    """

    def __init__(self, cfg):
        self.kind = cfg["kind"]
        self.x = float(cfg["x"])
        self.y = float(cfg["y"])
        self.base_y = self.y
        self.size = int(cfg.get("size", 34))
        self.color = tuple(cfg.get("color", (150, 50, 50)))
        self.speed = cfg.get("speed", 0)
        walk_range = cfg.get("range", [0, WIDTH])
        self.range_lo, self.range_hi = walk_range[0], walk_range[1]
        self.direction = 1
        self.is_copy = False            # True for a Designation 05 copy (it has one thing slightly wrong)
        # flyer
        self.bob_amplitude = cfg.get("bob_amplitude", 30)
        self.bob_speed = cfg.get("bob_speed", 0.05)
        self.phase = 0.0
        self.wail_cooldown = 0
        self.dive_state = "idle"
        self.dive_timer = random.randint(420, 720)
        self.dive_warning = 0
        self.dive_target_x = self.x
        self.dive_target_y = self.y
        # chaser
        self.detect_radius = cfg.get("detect_radius", 150)
        self.sleep_radius = cfg.get("sleep_radius", 250)
        self.awake = False
        self.wake_progress = 0.0
        self.face = 1                   # which way a chaser is looking
        self.last_seen_x = self.x       # where a chaser last saw you (it walks there if you hide)
        self.lose_timer = 0
        # shooter
        self.fire_interval = cfg.get("fire_interval", 100)
        self.align_tolerance = cfg.get("align_tolerance", 40)
        self.projectile_speed = cfg.get("projectile_speed", 5)
        self.cooldown = self.fire_interval
        self.aligned = False
        boss_health = {"doorstalker": 4, "beamer": 4, "summoner": 4,
                       "guardian": 4, "warden": 5, "secret_boss": 6}.get(self.kind, 1)
        self.boss_hp_max = boss_health
        self.boss_hp = boss_health
        self.exposed_timer = 0
        self.boss_hit_cooldown = 0
        # doorstalker (boss): lives inside door-frames, telegraphs, then dashes through one of them
        self.doors = cfg.get("doors", [])
        self.telegraph_time = cfg.get("telegraph", 55)
        self.manifest_time = cfg.get("manifest", 36)
        self.cooldown_time = cfg.get("cooldown", 80)
        self.dash_speed = cfg.get("speed", 5.5)
        self.dash_target_x = self.x
        self.dash_passes = 0
        if self.kind == "doorstalker":
            self.w, self.h = 30, 62
            self.state = "hidden"
            self.timer = self.cooldown_time
            self.active_door = None
            self.dash_dir = 1
            self.x, self.y = -400.0, -400.0    # parked off-screen until it manifests

        # beamer (boss): stands still, periodically telegraphs then sweeps a wide beam at its own height
        self.beam_telegraph = cfg.get("beam_telegraph", 60)
        self.beam_time = cfg.get("beam_time", 40)
        self.beam_cooldown = cfg.get("beam_cooldown", 70)
        self.beam_y = self.y + self.size // 2
        # counsel (boss): marks a lane, strikes it, then remains open during recovery
        self.verdict_interval = cfg.get("verdict_interval", 165)
        self.verdict_count = 0
        # guardian (boss): slow patrol, defeated by landing on top of it; hurts if touched from the side
        self.defeated = False
        if self.kind in ("beamer", "summoner", "guardian", "secret_boss"):
            self.w = self.h = self.size
            self.state = "idle"
            self.timer = cfg.get("beam_telegraph", 60) if self.kind == "beamer" else self.verdict_interval
            self.beam_active = False
        if self.kind in ("guardian", "secret_boss"):
            self.state = "stalking"
            self.timer = cfg.get("attack_interval", 100)
            self.special_mode = False
            self.double_slam_pending = False

        # warden (final boss): one monster, three timed phases -- no combat, only avoidance, just like
        # every other room. Phase 1 paces. Phase 2 rises and fires. Phase 3 chases while the room collapses.
        if self.kind == "warden":
            self.w = self.h = self.size
            self.phase = 1
            self.phase_timer = cfg.get("phase1_time", 420)
            self.phase1_speed = cfg.get("phase1_speed", 2.0)
            self.phase2_y = cfg.get("phase2_y", self.y - 140)
            self.phase2_fire = cfg.get("phase2_fire", 95)
            self.phase2_speed = cfg.get("phase2_speed", 4.5)
            self.phase3_speed = min(cfg.get("phase3_speed", 3.2), MOVE_SPEED * 0.7)
            self.cooldown = self.phase2_fire
            self.aligned = False
            self.align_tolerance = cfg.get("align_tolerance", 44)
            self.just_entered_phase = 1    # play_room watches this to trigger one-time phase effects

    @property
    def rect(self):
        if self.defeated:
            return pygame.Rect(-2000, -2000, 1, 1)
        if self.kind == "doorstalker":
            return pygame.Rect(int(self.x), int(self.y), self.w, self.h)
        return pygame.Rect(int(self.x), int(self.y), self.size, self.size)

    @property
    def beam_rect(self):
        """The wide, dangerous hazard a beamer boss sweeps out. None unless it is actively firing."""
        if self.kind == "beamer" and self.state == "beam" and not self.defeated:
            return pygame.Rect(BEAM_SAFE_LANE, int(self.beam_y) - 8,
                              WIDTH - 2 * BEAM_SAFE_LANE, 16)
        return None

    @property
    def attack_rect(self):
        """The Counsel's visible floor-seal danger area while the gavel falls."""
        if self.kind == "summoner" and self.state == "sentence" and not self.defeated:
            return pygame.Rect(int(self.verdict_x - 56), int(self.verdict_y - 12), 112, 24)
        return None

    @property
    def vulnerable(self):
        """Boss weak points have short, readable openings instead of permanent damage windows."""
        if self.kind == "doorstalker":
            return self.state == "exposed"
        if self.kind == "beamer":
            return self.state == "exposed"
        if self.kind == "summoner":
            return self.state == "open"
        if self.kind in ("guardian", "secret_boss"):
            return self.state == "stunned"
        if self.kind == "warden":
            return self.phase == 3 and self.exposed_timer > 0
        return False

    def _distance_to(self, player):
        return math.hypot(player.centerx - self.rect.centerx, player.centery - self.rect.centery)

    def _patrol(self):
        """Walk left and right between range_lo and range_hi."""
        self.x += self.speed * self.direction
        if self.x <= self.range_lo:
            self.x = self.range_lo
            self.direction = 1
        elif self.x >= self.range_hi:
            self.x = self.range_hi
            self.direction = -1

    def _step_toward(self, target_x):
        """Walk one step toward target_x (used by chasers)."""
        dx = target_x - self.rect.centerx
        self.face = 1 if dx > 0 else -1
        if abs(dx) > self.speed:
            self.x += self.speed if dx > 0 else -self.speed
        self.x = max(0, min(WIDTH - self.size, self.x))

    def _aimed_shot(self, player, speed, size, homing=0.0):
        """Fire toward the player's current position; optional homing turns gently while in flight."""
        start_x, start_y = self.rect.centerx, self.rect.centery
        dx, dy = player.centerx - start_x, player.centery - start_y
        distance = max(1.0, math.hypot(dx, dy))
        return {"x": start_x - size / 2, "y": start_y - size / 2,
                "vx": dx / distance * speed, "vy": dy / distance * speed,
                "size": size, "turn_rate": homing}

    def update(self, player, projectiles, hidden=False, noise=None):
        """Moves the monster one frame. Returns a list of sound names to play.
        hidden = the player is inside a gap in the recording.  noise = the sounds the player has been making."""
        sounds = []
        self.boss_hit_cooldown = max(0, self.boss_hit_cooldown - 1)
        self.exposed_timer = max(0, self.exposed_timer - 1)
        if self.kind == "patroller":
            self._patrol()

        elif self.kind == "flyer":
            self.phase += self.bob_speed
            if self.dive_state == "idle":
                self._patrol()
                self.y = self.base_y + math.sin(self.phase) * self.bob_amplitude
                self.dive_timer -= 1
                if self.dive_timer <= 0 and not hidden and self._distance_to(player) < 300:
                    self.dive_state, self.dive_warning = "warning", 54
                    sounds.append("telegraph")
            elif self.dive_state == "warning":
                self.dive_warning -= 1
                if hidden:
                    self.dive_state, self.dive_timer = "idle", 180
                elif self.dive_warning <= 0:
                    self.dive_target_x = max(20, min(WIDTH - self.size - 20, player.centerx - self.size // 2))
                    self.dive_target_y = min(420, max(self.base_y + 70, player.centery - self.size // 2))
                    self.dive_state = "diving"
                    sounds.append("manifest")
            elif self.dive_state == "diving":
                self.x += max(-3.2, min(3.2, self.dive_target_x - self.x))
                self.y += min(7.0, max(0.0, self.dive_target_y - self.y))
                if abs(self.x - self.dive_target_x) < 4 and self.y >= self.dive_target_y:
                    self.dive_state = "rising"
            else:
                self.y = max(self.base_y, self.y - 5.0)
                if self.y <= self.base_y:
                    self.y = self.base_y
                    self.dive_state, self.dive_timer = "idle", random.randint(420, 720)
            self.wail_cooldown = max(0, self.wail_cooldown - 1)
            if self.wail_cooldown == 0 and self._distance_to(player) < 260:
                sounds.append("banshee")
                self.wail_cooldown = 600

        elif self.kind == "chaser":
            distance = self._distance_to(player)
            if hidden:
                # It lost you. An awake chaser walks to where it last saw you, waits a moment, then goes back to sleep.
                if self.awake:
                    if abs(self.last_seen_x - self.rect.centerx) > self.speed:
                        self._step_toward(self.last_seen_x)
                    else:
                        self.lose_timer += 1
                        if self.lose_timer >= 100:
                            self.awake = False
                            self.lose_timer = 0
            else:
                self.last_seen_x = player.centerx
                self.lose_timer = 0
                # Running is loud: a sleeping chaser notices a running player from further away.
                loud = bool(noise) and any(n["radius"] >= NOISE_RUN for n in noise)
                wake_at = self.detect_radius * (1.35 if loud else 1.0)
                if not self.awake and distance < wake_at:
                    self.awake = True
                    sounds.append("wake")
                elif self.awake and distance > max(self.sleep_radius, wake_at + 15):
                    self.awake = False          # you got far enough away, it goes back to sleep
                if self.awake:
                    self._step_toward(player.centerx)
            # It takes several frames to unfold, giving the player a readable warning.
            self.wake_progress = min(1.0, self.wake_progress + 0.055) if self.awake else max(0.0, self.wake_progress - 0.07)

        elif self.kind == "shooter":
            hard_aim = settings.get("difficulty") == "hard"
            self.aligned = (not hidden) and (hard_aim or
                            abs(player.centery - self.rect.centery) < self.align_tolerance)
            if self.cooldown > 0:
                self.cooldown -= 1
            if self.aligned and self.cooldown == 0:
                if hard_aim:
                    projectiles.append(self._aimed_shot(player, self.projectile_speed, 10))
                else:
                    direction = 1 if player.centerx > self.rect.centerx else -1
                    projectiles.append({"x": self.rect.centerx, "y": self.rect.centery - 5,
                                        "vx": direction * self.projectile_speed, "size": 10})
                self.cooldown = self.fire_interval
                sounds.append("shoot")

        elif self.kind == "doorstalker":
            self.timer -= 1
            if self.state == "hidden":
                if self.timer <= 0 and self.doors:
                    choices = [i for i in range(len(self.doors)) if i != self.active_door] or list(range(len(self.doors)))
                    self.active_door = random.choice(choices)
                    self.state, self.timer = "telegraph", self.telegraph_time
                    sounds.append("telegraph")
            elif self.state == "telegraph":
                if self.timer <= 0:
                    dx0, dy0 = self.doors[self.active_door]
                    self.x, self.y = float(dx0), float(dy0)
                    self.dash_dir = 1 if player.centerx >= self.rect.centerx else -1
                    self.dash_target_x = max(24, min(WIDTH - self.w - 24,
                                                     player.centerx + self.dash_dir * 105))
                    self.state, self.timer = "manifest", max(48, self.manifest_time)
                    sounds.append("manifest")
            elif self.state == "manifest":
                speed = max(self.dash_speed, 8.5)
                if settings.get("difficulty") == "hard":
                    speed *= 1.22
                self.x += speed * self.dash_dir
                reached = self.x >= self.dash_target_x if self.dash_dir > 0 else self.x <= self.dash_target_x
                if reached or self.timer <= 0:
                    self.x = max(24, min(WIDTH - self.w - 24, self.x))
                    self.dash_passes += 1
                    if self.dash_passes == 1 and self.doors:
                        choices = [i for i in range(len(self.doors)) if i != self.active_door] or [self.active_door]
                        self.active_door = random.choice(choices)
                        self.x, self.y = map(float, self.doors[self.active_door])
                        self.state, self.timer = "telegraph", 28
                        sounds.append("telegraph")
                    else:
                        self.dash_passes = 0
                        self.state, self.timer = "exposed", 36
                        sounds.append("boss_hit")
            elif self.state == "exposed" and self.timer <= 0:
                self.state, self.timer = "hidden", self.cooldown_time
                self.x, self.y = -400.0, -400.0

        elif self.kind == "beamer" and not self.defeated:
            if self.state == "telegraph" and settings.get("difficulty") == "hard":
                # Keep tracking the player's height during the warning; lock when firing begins.
                self.beam_y = max(12, min(HEIGHT - 12, player.centery))
            self.timer -= 1
            if self.state == "idle":
                if self.timer <= 0:
                    self.state, self.timer = "telegraph", self.beam_telegraph
                    sounds.append("telegraph")
            elif self.state == "telegraph":
                if self.timer <= 0:
                    if settings.get("difficulty") == "hard":
                        self.beam_y = max(12, min(HEIGHT - 12, player.centery))
                    else:
                        self.beam_y = self.y + self.size // 2
                    self.beam_start_y = self.beam_y
                    self.state, self.timer = "beam", self.beam_time
                    sounds.append("manifest")
            elif self.state == "beam":
                # The picture tears down the room instead of holding one easy-to-jump line.
                progress = 1 - max(0, self.timer) / max(1, self.beam_time)
                self.beam_y = 28 + (HEIGHT - 56) * progress
                if self.timer <= 0:
                    self.state, self.timer = "exposed", 48
                    self.exposed_timer = 48
            elif self.state == "exposed":
                if self.timer <= 0:
                    self.state, self.timer = "idle", self.beam_cooldown

        elif self.kind == "summoner" and not self.defeated:
            self.timer -= 1
            if self.state == "idle" and self.timer <= 44:
                if self.verdict_count % 3 == 2:
                    self.state, self.timer = "appeal_warning", 48
                else:
                    self.verdict_x = player.centerx
                    self.verdict_y = player.bottom
                    self.state, self.timer = "warning", 44
                sounds.append("telegraph")
            elif self.state == "warning" and self.timer <= 0:
                self.state, self.timer = "sentence", 14
                sounds.append("manifest")
            elif self.state == "sentence" and self.timer <= 0:
                self.state, self.timer = "open", 54
                sounds.append("boss_hit")
            elif self.state == "appeal_warning" and self.timer <= 0:
                dx, dy = player.centerx - self.rect.centerx, player.centery - self.rect.centery
                aim = math.atan2(dy, dx)
                for offset in (-0.32, 0.0, 0.32):
                    angle = aim + offset
                    speed = 4.2
                    projectiles.append({
                        "x": self.rect.centerx - 6, "y": self.rect.centery - 6,
                        "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                        "size": 12, "paper": True,
                    })
                self.state, self.timer = "open", 54
                sounds.extend(["manifest", "shoot"])
            elif self.state == "open" and self.timer <= 0:
                self.verdict_count += 1
                self.state, self.timer = "idle", max(145, self.verdict_interval)

        elif self.kind in ("guardian", "secret_boss") and not self.defeated:
            if self.state == "stalking":
                self.speed = max(0.75, self.speed)
                self._patrol()
                self.timer -= 1
                if self.timer <= 0:
                    self.state, self.timer = "windup", 42
                    self.double_slam_pending = False
                    sounds.append("telegraph")
            elif self.state == "windup":
                self.timer -= 1
                if self.timer <= 0:
                    self.state, self.timer = "slam", 10
                    sounds.append("manifest")
            elif self.state == "slam":
                self.timer -= 1
                if self.timer <= 0:
                    wave_speed = ((12.0 if self.special_mode else 9.5) if self.kind == "secret_boss"
                                  else (10.5 if self.special_mode else 8.5))
                    for direction in (-1, 1):
                        projectiles.append({"x": self.rect.centerx - 16, "y": HEIGHT - 60,
                                            "vx": direction * wave_speed, "size": 32, "wave": True})
                    if self.special_mode and not self.double_slam_pending:
                        self.double_slam_pending = True
                        self.state, self.timer = "recoil", 26
                    else:
                        self.double_slam_pending = False
                        self.state, self.timer = "stunned", 82
                    sounds.append("boss_hit")
            elif self.state == "recoil":
                self.timer -= 1
                if self.timer <= 0:
                    self.state, self.timer = "slam", 8
                    sounds.extend(["telegraph", "manifest"])
            elif self.state == "stunned":
                self.timer -= 1
                if self.timer <= 0:
                    self.state, self.timer = "stalking", 75

        elif self.kind == "warden":
            self.just_entered_phase = 0
            self.phase_timer -= 1
            if self.phase == 1:
                self.speed = self.phase1_speed
                if self.phase_timer % 180 < 115:
                    self._step_toward(player.centerx)
                else:
                    self._patrol()
                if self.phase_timer <= 0:
                    self.phase = 2
                    self.phase_timer = 10 ** 9     # phase 2 ends when it's fired a few times, not on a clock
                    self.phase2_shots = 0
                    self.y = self.phase2_y
                    self.just_entered_phase = 2
                    sounds.append("telegraph")
            elif self.phase == 2:
                hard_aim = settings.get("difficulty") == "hard"
                self.aligned = hard_aim or abs(player.centery - self.rect.centery) < self.align_tolerance
                if self.cooldown > 0:
                    self.cooldown -= 1
                if self.cooldown == 0:
                    if hard_aim:
                        projectiles.append(self._aimed_shot(player, self.phase2_speed, 14, homing=0.035))
                    else:
                        direction = 1 if player.centerx > self.rect.centerx else -1
                        projectiles.append({"x": self.rect.centerx, "y": self.rect.centery - 6,
                                            "vx": direction * self.phase2_speed, "size": 14})
                    self.cooldown = self.phase2_fire
                    self.phase2_shots += 1
                    sounds.append("shoot")
                    if self.phase2_shots >= 4:
                        self.phase = 3
                        self.just_entered_phase = 3
                        self.phase_timer = 100
                        self.exposed_timer = 48
                        sounds.append("manifest")
            elif self.phase == 3:
                if self.phase_timer <= 0:
                    self.phase_timer = 120
                    self.exposed_timer = 44
                    sounds.append("telegraph")
                dx = player.centerx - self.rect.centerx
                self.face = 1 if dx > 0 else -1
                if abs(dx) > self.phase3_speed:
                    self.x += self.phase3_speed if dx > 0 else -self.phase3_speed
                self.x = max(0, min(WIDTH - self.size, self.x))
        return sounds

    def draw(self, surface, frame, player):
        visuals.draw_monster(surface, self, frame, player)


# ==================================================================
# 5. DRAWING FUNCTIONS
# ==================================================================
# Everything here is drawn with plain pygame.draw calls straight onto the picture
# (no separate little pictures pasted in), the same rule visuals.py follows.
def draw_spikes(surface, rect, active, warning, frame):
    """Pulsing spikes stay flat during the light-and-sound warning, then rise."""
    x0, y0, w, h = rect
    step = 12
    if active:
        height, color = h, (205, 205, 215)
    elif warning:
        height, color = 4, (95, 90, 105)
    else:
        height, color = 4, (95, 90, 105)
    for x in range(x0, x0 + w, step):
        jitter = 0
        pts = [(x + jitter, y0 + h), (x + step + jitter, y0 + h), (x + step // 2 + jitter, y0 + h - height)]
        pygame.draw.polygon(surface, color, pts)
        if active:
            pygame.draw.circle(surface, (230, 70, 70), (x + step // 2, y0 + h - height + 2), 2)


def draw_pit(surface, px, pw):
    """A hole in the floor, with spikes far below so it looks as dangerous as it is."""
    pygame.draw.rect(surface, (4, 3, 6), (px, 460, pw, 40))
    for x in range(px, px + pw, 14):
        pygame.draw.polygon(surface, (70, 30, 40), [(x, 500), (x + 14, 500), (x + 7, 484)])
    pygame.draw.line(surface, (110, 30, 45), (px, 460), (px, 500), 2)
    pygame.draw.line(surface, (110, 30, 45), (px + pw, 460), (px + pw, 500), 2)


def draw_crumble(surface, c, chapter, frame):
    """A platform that falls apart soon after you stand on it, then grows back."""
    r = c["rect"]
    if c["state"] == "gone":
        pygame.draw.rect(surface, (70, 60, 70), r, 1)                # a faint outline shows where it will return
        return
    shake = random.randint(-2, 2) if c["state"] == "shaking" else 0
    shown = r.move(shake, 0)
    accent = tuple(chapter.get("accent", (120, 120, 120)))
    pygame.draw.rect(surface, mix((70, 55, 50), accent, 0.2), shown)
    pygame.draw.rect(surface, (30, 22, 22), shown, 1)
    for i in range(1, 5):                                            # cracks
        cx = shown.x + i * shown.w // 5
        pygame.draw.line(surface, (30, 22, 22), (cx, shown.y), (cx - 4, shown.bottom - 1), 1)


def draw_player(surface, rect, facing, invincible, frame, sprite):
    """Draws the player. (It is its own small function so the tests can watch it.)"""
    sprite.draw(surface, rect, facing, invincible, frame)


def draw_heart(surface, x, y, size, color):
    r = size // 4
    pygame.draw.circle(surface, color, (x + r, y + r), r)
    pygame.draw.circle(surface, color, (x + 3 * r, y + r), r)
    pygame.draw.polygon(surface, color, [(x, y + r + 1), (x + 4 * r, y + r + 1), (x + 2 * r, y + 4 * r)])


def draw_hud(screen, lives, has_key, tape_count, name, message, message_timer, has_charge=False,
             stamina=STAMINA_MAX, tired=False, battery=None, artifact_count=0):
    for i in range(max_lives()):
        color = (210, 50, 60) if i < lives else (60, 40, 45)
        draw_heart(screen, 14 + i * 28, 12, 20, color)
    draw_text(screen, name, FONTS["mono_small"], (200, 195, 205), 14, 40)
    if settings.get("active_title"):
        title = FONTS["mono_small"].render("TITLE: " + settings["active_title"], True, (178, 157, 135))
        screen.blit(title, title.get_rect(topright=(WIDTH - 14, 40)))
    draw_text(screen, "FILES: %d" % tape_count, FONTS["mono_small"], (200, 195, 205), 14, 60)
    draw_text(screen, "RELICS: %d/3" % artifact_count, FONTS["mono_small"], (180, 170, 135), 14, 80)
    if has_key:
        draw_text(screen, "KEY", FONTS["mono_small"], (235, 200, 70), 14, 100)
    if has_charge:
        draw_text(screen, "CHARGED: touch the presence", FONTS["mono_small"], (140, 200, 255), 14, 120)
    if stamina < STAMINA_MAX:                         # the stamina bar only appears once you have used some
        pygame.draw.rect(screen, (40, 36, 44), (14, 144, 80, 6))
        bar_color = (200, 60, 60) if tired else (120, 200, 140)    # red = worn out, cannot run yet
        pygame.draw.rect(screen, bar_color, (14, 144, int(80 * stamina / STAMINA_MAX), 6))
    if battery is not None:                           # the flashlight battery (dark rooms only)
        pygame.draw.rect(screen, (40, 36, 44), (14, 156, 80, 6))
        low = battery < 20
        pygame.draw.rect(screen, (230, 170, 60) if low else (230, 220, 140), (14, 156, int(80 * battery / BATTERY_MAX), 6))
    if message and message_timer > 0:
        color = mix((20, 20, 20), WHITE, min(1.0, message_timer / 30))
        draw_text(screen, message, FONTS["body"], color, WIDTH // 2, 90, center=True)


def draw_boss_status(screen, monsters):
    boss_names = {"doorstalker": "THE GLITCH", "beamer": "THE SIGNAL", "summoner": "THE COUNSEL",
                  "guardian": "THE GATE", "warden": "THE RECORD", "secret_boss": "THE WITNESS"}
    boss = next((m for m in monsters if m.kind in boss_names and not m.defeated), None)
    if boss is None:
        return
    x, y = WIDTH - 190, 14
    draw_text(screen, boss_names[boss.kind], FONTS["mono_small"], (202, 194, 190), x, y)
    for i in range(boss.boss_hp_max):
        rect = pygame.Rect(x, y + 23, 28, 7)
        rect.x += i * 34
        color = (180, 37, 43) if i < boss.boss_hp else (48, 33, 38)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (100, 81, 78), rect, 1)
    if boss.kind == "warden":
        draw_text(screen, "PHASE %d" % boss.phase, FONTS["mono_small"], (153, 111, 118), x, y + 34)
    elif boss.vulnerable:
        draw_text(screen, "EXPOSED", FONTS["mono_small"], (190, 205, 176), x, y + 34)


def draw_darkness(surface, cx, cy, r, dense=False):
    """Darkness with a round hole of light around (cx, cy). Drawn as black stripes (no see-through layers).
    Far away it is two stripes in three, at the soft edge one in three, and inside the light nothing.
    dense=True is used while hidden between frames: almost everything is black."""
    cx, cy = int(cx), int(cy)
    r_out = r * 1.5
    for y in range(0, HEIGHT, 2):
        band = (y // 2) % 3
        dy = abs(y + 1 - cy)
        out_h = int(math.sqrt(r_out * r_out - dy * dy)) if dy < r_out else 0
        in_h = int(math.sqrt(r * r - dy * dy)) if dy < r else 0
        if dense or band != 2:
            if out_h == 0:
                pygame.draw.rect(surface, BLACK, (0, y, WIDTH, 2))
            else:
                pygame.draw.rect(surface, BLACK, (0, y, max(0, cx - out_h), 2))
                pygame.draw.rect(surface, BLACK, (cx + out_h, y, max(0, WIDTH - (cx + out_h)), 2))
        if out_h > 0 and ((band != 2) if dense else (band == 0)):
            pygame.draw.rect(surface, BLACK, (cx - out_h, y, out_h - in_h, 2))
            pygame.draw.rect(surface, BLACK, (cx + in_h, y, out_h - in_h, 2))


def draw_vignette(screen, amount):
    """Black closes in from the screen edges as 'amount' goes from 0 to 1. This is the Hush's visual warning
    for players who cannot hear the sound fading."""
    t = int(max(0.0, min(1.0, amount)) * 120)
    if t <= 0:
        return
    pygame.draw.rect(screen, BLACK, (0, 0, t, HEIGHT))
    pygame.draw.rect(screen, BLACK, (WIDTH - t, 0, t, HEIGHT))
    pygame.draw.rect(screen, BLACK, (0, 0, WIDTH, t // 2))
    pygame.draw.rect(screen, BLACK, (0, HEIGHT - t // 2, WIDTH, t // 2))


def draw_gap(surface, rect, frame, occupied):
    """A narrow tear in the image. Entering it drops the player between recorded frames."""
    pulse = 0.5 + 0.5 * math.sin(frame * 0.08)
    col = (95 + int(pulse * 45), 20, 35)
    pygame.draw.rect(surface, (8, 6, 12), rect.inflate(8, 4))
    pygame.draw.line(surface, col, (rect.centerx - 2, rect.y), (rect.centerx + 1, rect.bottom), 2)
    for i in range(4):
        y = rect.y + 5 + i * 12
        wobble = int(math.sin(frame * 0.13 + i) * 4)
        pygame.draw.line(surface, (170, 165, 175), (rect.x - wobble, y), (rect.right + wobble, y - 3), 1)
    if occupied:
        pygame.draw.line(surface, (220, 215, 220), (rect.centerx - 4, rect.y + 12), (rect.centerx + 4, rect.y + 12), 2)


def draw_audit_overlay(surface, frame, state, warning, scan):
    """The Auditor's scan line sweeps the room after its audio/light warning."""
    tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    strength = 26 if state == "warning" else 52
    tint.fill((115, 0, 12, strength))
    surface.blit(tint, (0, 0))
    if state == "warning":
        pulse = 0.5 + 0.5 * math.sin(frame * 0.24)
        label = "AUDIT IN %d  /  ENTER THE GAP" % max(1, math.ceil(warning / FPS))
        draw_text(surface, label, FONTS["mono"], (220, int(100 + 100 * pulse), 110), WIDTH // 2, 30, center=True)
        y = 100 + (frame * 3) % 300
        pygame.draw.line(surface, (160, 20, 30), (0, y), (WIDTH, y), 1)
    else:
        y = int((1 - scan / 72) * HEIGHT)
        pygame.draw.rect(surface, (180, 15, 28), (0, y - 5, WIDTH, 10))
        pygame.draw.line(surface, (245, 125, 120), (0, y), (WIDTH, y), 2)
        draw_text(surface, "RECORDING SUBJECT", FONTS["mono_small"], (235, 190, 190), WIDTH // 2, 30, center=True)


def draw_note(surface, rect, frame):
    """A small piece of paper lying on the floor."""
    lift = int(math.sin(frame * 0.07) * 1.5)
    r = rect.move(0, lift)
    pygame.draw.rect(surface, (205, 200, 172), r)
    pygame.draw.rect(surface, (110, 100, 80), r, 1)
    for i in range(3):
        pygame.draw.line(surface, (110, 100, 80), (r.x + 3, r.y + 4 + i * 4), (r.right - 4, r.y + 4 + i * 4), 1)


def draw_battery(surface, rect, frame):
    """A flashlight battery: a little green cell that glows."""
    pulse = 0.5 + 0.5 * math.sin(frame * 0.1)
    cx, cy = rect.centerx, rect.centery
    visuals.add_glow(surface, cx, cy, int(16 + 4 * pulse), (14, 44, 24))
    pygame.draw.rect(surface, (50, 150, 80), rect, border_radius=3)
    pygame.draw.rect(surface, (180, 240, 190), rect, 2, border_radius=3)
    pygame.draw.rect(surface, (180, 240, 190), (cx - 3, rect.y - 3, 6, 3))
    pygame.draw.rect(surface, (230, 255, 235), (cx - 2, cy - 5, 4, 10))


def draw_artifact(surface, artifact, frame):
    """Draws one of the three evidence pieces that can expose the sealed room."""
    rect = artifact["rect"]
    pulse = 0.55 + 0.45 * math.sin(frame * 0.11)
    colors = {"bell_clapper": (212, 174, 92), "sealed_writ": (165, 70, 74),
              "negative_frame": (117, 174, 190)}
    color = colors.get(artifact.get("id"), (190, 180, 145))
    visuals.add_glow(surface, rect.centerx, rect.centery, int(24 + pulse * 7), tuple(c // 5 for c in color))
    pygame.draw.rect(surface, (13, 11, 15), rect.inflate(4, 4), border_radius=3)
    pygame.draw.rect(surface, color, rect, border_radius=2)
    pygame.draw.rect(surface, (235, 225, 202), rect, 1, border_radius=2)
    pygame.draw.line(surface, (25, 20, 24), (rect.x + 5, rect.y + 6), (rect.right - 5, rect.y + 6), 2)


def draw_unlisted_figure(surface, cx, by, frame):
    """The thing in the secret room. It just stands there. It never moves toward you."""
    body = (30, 28, 34)
    pygame.draw.polygon(surface, body, [(cx - 6, by), (cx + 6, by), (cx + 4, by - 38), (cx - 4, by - 38)])
    pygame.draw.line(surface, body, (cx - 5, by - 34), (cx - 8, by - 14), 3)
    pygame.draw.line(surface, body, (cx + 5, by - 34), (cx + 8, by - 14), 3)
    pygame.draw.ellipse(surface, (196, 192, 186), (cx - 5, by - 52, 10, 14))      # a blank face, nothing on it
    if (frame // 7) % 23 == 0:
        pygame.draw.line(surface, (210, 50, 50), (cx - 8, by - 30), (cx + 8, by - 30), 1)


def draw_secret_panel(surface, secret, open_t, frame):
    """A wall panel that is almost, but not quite, the same color as the wall. Walk into it and it slides away."""
    p = secret["panel"]
    pygame.draw.rect(surface, (6, 5, 8), p)                              # the little room behind it
    w = int(p.w * (1 - open_t))
    if w > 0:
        x = p.x if secret["side"] == "left" else p.right - w
        pygame.draw.rect(surface, (78, 64, 58), (x, p.y, w, p.h))
        pygame.draw.line(surface, (40, 33, 32), (x, p.y + 16), (x + w, p.y + 24), 1)
        pygame.draw.line(surface, (40, 33, 32), (x + w // 2, p.y), (x + w // 2 - 3, p.bottom), 1)
        pygame.draw.rect(surface, (44, 36, 34), (x, p.y, w, p.h), 1)
    if open_t >= 1.0 and secret["unlisted"]:
        draw_unlisted_figure(surface, p.centerx, p.bottom - 2, frame)


def draw_mark(surface, m, frame):
    """Traces left by earlier Subjects: scratches, a dropped shoe, a chalk arrow, a trail that just stops."""
    kind = m["kind"]
    if kind == "scratch":
        x, y = m["x"], m["y"]
        for i in range(m.get("count", 4)):
            pygame.draw.line(surface, (120, 100, 98), (x + i * 6, y), (x + i * 6, y + 22), 2)
        pygame.draw.line(surface, (120, 100, 98), (x - 4, y + 18), (x + m.get("count", 4) * 6, y + 3), 2)
    elif kind == "shoe":
        x, y = m["x"], m["y"]
        pygame.draw.ellipse(surface, (58, 48, 54), (x - 9, y - 7, 18, 8))
        pygame.draw.line(surface, (24, 20, 24), (x - 9, y - 1), (x + 9, y - 1), 2)
    elif kind == "arrow":
        x, y, d = m["x"], m["y"], m["dir"]
        chalk = (196, 196, 186)
        pygame.draw.line(surface, chalk, (x - 18 * d, y), (x + 14 * d, y), 3)
        pygame.draw.polygon(surface, chalk, [(x + 20 * d, y), (x + 10 * d, y - 7), (x + 10 * d, y + 7)])
    elif kind == "trail":
        for i in range(m["n"]):
            pygame.draw.circle(surface, (74, 36, 40), (m["x"] + i * 14, m["y"] - (i % 2)), 3 - (i // 3))


def draw_monitor_line(surface, bx, y0, color):
    """A heart-monitor line. A blip sits at x = bx (None = a flat line)."""
    pts = []
    for x in range(0, WIDTH, 4):
        d = (x - bx) if bx is not None else 999
        y = y0
        if -30 < d < -20:
            y -= 4
        elif -20 <= d < -14:
            y -= 26
        elif -14 <= d < -8:
            y += 12
        elif -8 <= d < -2:
            y -= 4
        pts.append((x, y))
    pygame.draw.lines(surface, color, False, pts, 3)


# ==================================================================
# 6. MENUS AND SCREENS
# ==================================================================
def draw_menu_frame(screen, title, options, selected, subtitle, backdrop, frame):
    """Draws any vertical menu. Long lists scroll so they never run off the screen."""
    if backdrop is not None:
        screen.blit(backdrop, (0, 0))
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        screen.blit(dim, (0, 0))
    else:
        visuals.menu_background(screen, frame)

    jitter = random.randint(-6, 6) if frame % 120 < 4 else 0      # rare title glitch
    draw_text(screen, title, FONTS["title"], (120, 20, 20), WIDTH // 2 + jitter + 3, 103, center=True, shadow=None)
    draw_text(screen, title, FONTS["title"], WHITE, WIDTH // 2, 100, center=True)

    y = 152
    for line in wrap_text(subtitle, FONTS["mono_small"], 660)[:3]:
        draw_text(screen, line, FONTS["mono_small"], (170, 150, 150), WIDTH // 2, y, center=True)
        y += 22

    visible = 6
    first = max(0, min(selected - 3, len(options) - visible))
    y = 245
    for i in range(first, min(len(options), first + visible)):
        if i == selected:
            pulse = 0.5 + 0.5 * math.sin(frame * 0.1)
            draw_text(screen, "> %s <" % options[i], FONTS["big"], mix(RED, (255, 150, 150), pulse),
                      WIDTH // 2, y, center=True)
        else:
            draw_text(screen, options[i], FONTS["big"], GREY, WIDTH // 2, y, center=True)
        y += 40
    draw_text(screen, "UP / DOWN + ENTER      ESC = back", FONTS["mono_small"], (95, 90, 100),
              WIDTH // 2, HEIGHT - 26, center=True)


def run_menu(screen, clock, title, options, subtitle="", tape_no=1, start_index=0, backdrop=None):
    """Shows a menu and waits. Returns the chosen index, or None if Esc was pressed."""
    selected = start_index
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(options)
                    sound.play("click")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(options)
                    sound.play("click")
                elif event.key in CONFIRM_KEYS:
                    sound.play("click")
                    return selected
                elif event.key == pygame.K_ESCAPE:
                    return None
        draw_menu_frame(screen, title, options, selected, subtitle, backdrop, frame)
        present(screen, tape_no)
        clock.tick(FPS)


def wait_for_key(screen, clock, draw_fn, tape_no=1, min_frames=20):
    """Calls draw_fn(frame) every frame until the player presses Enter/Space/Esc."""
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN and frame > min_frames:
                if event.key in CONFIRM_KEYS or event.key == pygame.K_ESCAPE:
                    return
        draw_fn(frame)
        present(screen, tape_no)
        clock.tick(FPS)


def draw_loading_frame(screen, label, progress):
    pygame.event.pump()
    screen.fill((8, 6, 10))
    for _ in range(40):                                   # a little static
        y = random.randint(0, HEIGHT)
        g = random.randint(20, 60)
        pygame.draw.line(screen, (g, g, g), (random.randint(0, WIDTH), y), (random.randint(0, WIDTH), y))
    draw_text(screen, "HALLOWED GROUNDS", FONTS["big"], WHITE, WIDTH // 2, 190, center=True)
    draw_text(screen, label, FONTS["mono_small"], GREY, WIDTH // 2, 300, center=True)
    bar = pygame.Rect(200, 250, 400, 18)
    pygame.draw.rect(screen, (60, 50, 60), bar, 2)
    pygame.draw.rect(screen, RED, (bar.x + 3, bar.y + 3, int((bar.w - 6) * progress), bar.h - 6))
    pygame.display.flip()


def show_loading(screen, clock, tasks):
    """tasks = [(label, function), ...]. Runs each one while showing a loading bar."""
    total = len(tasks)
    for i, (label, task) in enumerate(tasks):
        draw_loading_frame(screen, label, i / total)
        task()
    draw_loading_frame(screen, "Tape ready.", 1.0)
    pygame.time.wait(250)


def show_controls(screen, clock):
    lines = [
        "MOVE     Arrow keys  or  A / D",
        "RUN      Hold Shift (uses stamina, and it is LOUD)",
        "JUMP     Space, Up, or W  (hold = higher)",
        "HIDE     Down / S / E in a footage gap (again = leave)",
        "PAUSE    Esc",
        "SKIP     Tab with the <dev> title equipped",
        "READ     Walk into a cassette or a note",
        "",
        "GOAL     Find the KEY, then reach the DOOR.",
        "",
        "The Guide gives one rule per room.",
        "Every rule is a hint. Listen carefully.",
    ]

    def draw(frame):
        screen.fill((14, 10, 16))
        draw_text(screen, "CONTROLS", FONTS["title"], WHITE, WIDTH // 2, 70, center=True)
        for i, line in enumerate(lines):
            draw_text(screen, line, FONTS["mono"], (200, 195, 205), 70, 125 + i * 28)
        draw_text(screen, "Press ENTER", FONTS["mono_small"], (95, 90, 100), WIDTH // 2, HEIGHT - 26, center=True)

    wait_for_key(screen, clock, draw)


def show_settings(screen, clock, backdrop=None, tape_no=1):
    """Volume, difficulty and the chapter-intro toggle. LEFT/RIGHT changes a value."""
    selected = 0
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % 4
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % 4
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                    direction = 1 if event.key in (pygame.K_RIGHT, pygame.K_d) else -1
                    if selected == 0:
                        settings["volume"] = max(0, min(100, settings["volume"] + 10 * direction))
                        sound.set_volume(settings["volume"] / 100)
                        sound.play("click")
                    elif selected == 1:
                        i = DIFFICULTIES.index(settings["difficulty"])
                        settings["difficulty"] = DIFFICULTIES[(i + direction) % len(DIFFICULTIES)]
                        sound.play("click")
                    elif selected == 2:
                        settings["chapter_intros"] = not settings["chapter_intros"]
                elif event.key in CONFIRM_KEYS:
                    if selected == 1:
                        i = DIFFICULTIES.index(settings["difficulty"])
                        settings["difficulty"] = DIFFICULTIES[(i + 1) % len(DIFFICULTIES)]
                    elif selected == 2:
                        settings["chapter_intros"] = not settings["chapter_intros"]
                    elif selected == 3:
                        save_settings()
                        return
                elif event.key == pygame.K_ESCAPE:
                    save_settings()
                    return
        options = ["Volume:  < %d%% >" % settings["volume"],
                   "Difficulty:  < %s >" % settings["difficulty"].capitalize(),
                   "Tape intros:  %s" % ("On" if settings["chapter_intros"] else "Off"),
                   "Back"]
        hint = {0: "LEFT / RIGHT changes the volume.",
                1: "Easy: 5 hearts, slower monsters.  Normal: 3 hearts.  Hard: 2 hearts, faster monsters. Applies from the next room.",
                2: "Show a title card when a new tape begins.",
                3: ""}[selected]
        draw_menu_frame(screen, "SETTINGS", options, selected, hint, backdrop, frame)
        present(screen, tape_no)
        clock.tick(FPS)


def show_titles(screen, clock):
    """Equip one of the run titles the player has recovered."""
    unlocked = settings["unlocked_titles"]
    if not unlocked:
        run_menu(screen, clock, "RECOVERED TITLES", ["Back"],
                 "No titles recovered yet. Clear rooms and find story files.")
        return
    selected = unlocked.index(settings["active_title"]) if settings["active_title"] in unlocked else 0
    labels = [("* " if title == settings["active_title"] else "  ") + title for title in unlocked] + ["Back"]
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(labels)
                    sound.play("click")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(labels)
                    sound.play("click")
                elif event.key in CONFIRM_KEYS:
                    sound.play("click")
                    if selected < len(unlocked):
                        settings["active_title"] = unlocked[selected]
                        save_settings()
                    return
                elif event.key == pygame.K_ESCAPE:
                    return
        description = (TITLE_REWARDS[unlocked[selected]] if selected < len(unlocked)
                       else "%d title(s) recovered. Select one to wear." % len(unlocked))
        draw_menu_frame(screen, "RECOVERED TITLES", labels, selected, description, None, frame)
        present(screen, 1)
        clock.tick(FPS)


def show_title_recovered(screen, clock, title):
    """A quick VHS-style card for a newly earned title; any confirm key dismisses it early."""
    for frame in range(72):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            if event.type == pygame.KEYDOWN and event.key in CONFIRM_KEYS + (pygame.K_ESCAPE,):
                return
        visuals.menu_background(screen, frame)
        draw_text(screen, "TITLE RECOVERED", FONTS["mono"], (175, 168, 177), WIDTH // 2, 174, center=True)
        color = (225, 210, 180) if frame % 8 < 6 else (130, 35, 42)
        draw_text(screen, title, FONTS["big"], color, WIDTH // 2, 225, center=True)
        draw_text(screen, "Equip it from RECOVERED TITLES", FONTS["mono_small"], (120, 112, 125),
                  WIDTH // 2, 294, center=True)
        present(screen, 1)
        clock.tick(FPS)


def show_boss_lore(screen, clock, entries, chap_no):
    """A short sequence of recovered-log entries shown once, right as a boss fight begins.
    entries = [(header, body), ...]. Press to advance each one; press again on the last to close."""
    sound.play("static")
    for header, body in entries:
        lines = wrap_text(body, FONTS["mono"], WIDTH - 168)
        total_chars = len(body)
        revealed = 0.0
        frame = 0
        while True:
            frame += 1
            advance = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    quit_game()
                elif event.type == pygame.KEYDOWN and event.key in CONFIRM_KEYS + (pygame.K_ESCAPE,):
                    if revealed < total_chars:
                        revealed = total_chars
                    else:
                        advance = True
            revealed = min(total_chars, revealed + 1.1)
            screen.fill((8, 6, 9))
            for i in range(0, HEIGHT, 3):                              # a bare scanline texture, nothing fancier
                pygame.draw.line(screen, (14, 11, 15), (0, i), (WIDTH, i))
            box = pygame.Rect(60, 150, WIDTH - 120, 220)
            pygame.draw.rect(screen, (12, 10, 14), box, border_radius=6)
            pygame.draw.rect(screen, (120, 30, 30), box, 2, border_radius=6)
            draw_text(screen, header, FONTS["mono"], (230, 80, 80), box.x + 24, box.y + 20)
            remaining = int(revealed)
            y = box.y + 62
            for line in lines:
                draw_text(screen, line[:remaining], FONTS["mono"], (210, 205, 215), box.x + 24, y)
                remaining -= len(line) + 1
                y += 28
            if revealed >= total_chars and (frame // 30) % 2 == 0:
                draw_text(screen, "ENTER", FONTS["mono_small"], (140, 135, 145), box.right - 70, box.bottom - 26)
            present(screen, chap_no + 1)
            clock.tick(FPS)
            if advance:
                break


def show_tape(screen, clock, text, chap_no, backdrop=None):
    """Shows one tape's (or note's) text, typed out letter by letter."""
    sound.play("scroll")
    header, body = split_tape(text)
    lines = wrap_text(body, FONTS["mono"], WIDTH - 168)
    total_chars = len(body)
    revealed = 0.0
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN and event.key in CONFIRM_KEYS + (pygame.K_ESCAPE,):
                if revealed < total_chars:
                    revealed = total_chars          # first press: show everything
                else:
                    return                          # second press: close
        revealed = min(total_chars, revealed + 1.2)

        if backdrop is not None:
            screen.blit(backdrop, (0, 0))
        else:
            screen.fill((14, 10, 16))
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        screen.blit(dim, (0, 0))
        box = pygame.Rect(60, 140, WIDTH - 120, 240)
        pygame.draw.rect(screen, (12, 10, 14), box, border_radius=6)
        pygame.draw.rect(screen, (120, 30, 30), box, 2, border_radius=6)
        if header:
            draw_text(screen, header, FONTS["mono"], (230, 80, 80), box.x + 24, box.y + 22)
        remaining = int(revealed)
        y = box.y + 66
        for line in lines:
            draw_text(screen, line[:remaining], FONTS["mono"], (225, 220, 225), box.x + 24, y)
            remaining -= len(line) + 1
            y += 30
        if revealed >= total_chars and (frame // 30) % 2 == 0:
            draw_text(screen, "ENTER", FONTS["mono_small"], (150, 145, 155), box.right - 24, box.bottom - 26, center=False)
        present(screen, chap_no + 1)
        clock.tick(FPS)


def show_journal(screen, clock, collected, chap_no, backdrop=None):
    """The file log: every tape and note found so far, readable again."""
    if not collected:
        run_menu(screen, clock, "TAPE LOG", ["Back"], "Nothing recovered yet. Look for cassettes and notes in each room.",
                 chap_no + 1, 0, backdrop)
        return
    labels = [tape_label(t) for t in collected]
    selected = 0
    while True:
        choice = run_menu(screen, clock, "TAPE LOG", labels + ["Back"], "%d file(s) recovered." % len(collected),
                          chap_no + 1, selected, backdrop)
        if choice is None or choice == len(labels):
            return
        selected = choice
        show_tape(screen, clock, collected[choice], chap_no, backdrop)


def show_pause_menu(screen, clock, chap_no, collected, backdrop):
    """Returns 'resume' or 'menu'."""
    selected = 0
    while True:
        choice = run_menu(screen, clock, "PAUSED", ["Resume", "Tape Log", "Settings", "Quit to Main Menu"],
                          "", chap_no + 1, selected, backdrop)
        if choice is None or choice == 0:
            return "resume"
        selected = choice
        if choice == 1:
            show_journal(screen, clock, collected, chap_no, backdrop)
        elif choice == 2:
            show_settings(screen, clock, backdrop, chap_no + 1)
        else:
            return "menu"


def show_slot_picker(screen, clock):
    """Returns 1, 2 or 3 (the chosen save slot), or None for Back."""
    labels = [slot_label(s) for s in range(1, NUM_SLOTS + 1)] + ["Back"]
    choice = run_menu(screen, clock, "SELECT TAPE", labels, "Pick a save slot.")
    if choice is None or choice == NUM_SLOTS:
        return None
    return choice + 1


def show_chapter_intro(screen, clock, chap_no):
    """The card shown when a new tape begins (can be turned off in Settings)."""
    label, name = split_chapter_title(chap_no)
    guide = GUIDE_LINES[chap_no % len(GUIDE_LINES)]
    sound.stop_music()
    sound.play("static")

    def draw(frame):
        screen.fill((6, 4, 8))
        draw_text(screen, label, FONTS["title"], WHITE, WIDTH // 2, 190, center=True)
        draw_text(screen, name, FONTS["big"], RED, WIDTH // 2, 250, center=True)
        for i, line in enumerate(wrap_text('GUIDE: "%s"' % guide, FONTS["mono_small"], 640)):
            draw_text(screen, line, FONTS["mono_small"], (150, 140, 150), WIDTH // 2, 330 + i * 22, center=True)
        draw_text(screen, "ENTER to begin", FONTS["mono_small"], (95, 90, 100), WIDTH // 2, HEIGHT - 26, center=True)

    draw(0)
    analog.static_burst(screen, clock, 30, True)
    wait_for_key(screen, clock, draw, chap_no + 1)


def show_chapter_complete(screen, clock, chap_no):
    label, name = split_chapter_title(chap_no)
    guide = random.choice(GUIDE_LINES)
    sound.stop_music()
    sound.play("chapter_complete")

    def draw(frame):
        screen.fill((6, 4, 8))
        draw_text(screen, "%s RECOVERED" % label, FONTS["title"], WHITE, WIDTH // 2, 190, center=True)
        draw_text(screen, name, FONTS["big"], RED, WIDTH // 2, 250, center=True)
        for i, line in enumerate(wrap_text('GUIDE: "%s"' % guide, FONTS["mono_small"], 640)):
            draw_text(screen, line, FONTS["mono_small"], (150, 140, 150), WIDTH // 2, 330 + i * 22, center=True)
        draw_text(screen, "ENTER to continue", FONTS["mono_small"], (95, 90, 100), WIDTH // 2, HEIGHT - 26, center=True)

    draw(0)
    analog.static_burst(screen, clock, 25, True)
    wait_for_key(screen, clock, draw, chap_no + 1, 45)


def show_game_over(screen, clock, chap_no):
    """Returns 0 for Try Again, 1 for Main Menu."""
    settings["subject_count"] += 1       # the Subject number goes up on every death, and it is saved so it never resets
    count = settings["subject_count"]
    sound.stop_music()
    sound.play("shriek")
    visuals.jumpscare_sequence(screen, clock, frames=14, big=True)
    sound.play("tape_stop")
    analog.static_burst(screen, clock, 40, False)
    line = random.choice(GAME_OVER_LINES)
    if "%d" in line:
        line = line % count
    if count >= 7 and not settings["twist_done"]:
        # Once, and only once: a number that was already retired comes back.
        settings["twist_done"] = True
        line = "SUBJECT 2 NOT RECOVERED. This number was retired. Please disregard it."
    save_settings()
    choice = run_menu(screen, clock, "SUBJECT NOT RECOVERED", ["Try Again", "Main Menu"],
                      line, chap_no + 1)
    return 0 if choice == 0 else 1


def show_ending(screen, clock, collected):
    sound.stop_music()
    sound.play("shriek")
    visuals.jumpscare_sequence(screen, clock, frames=22, big=True)   # the tape pretends to end, then does not
    sound.play("chapter_complete")
    lines = ["END OF RECORDING", "", "Files recovered: %d" % len(collected), "",
             "SUBJECT COPY: INCOMPLETE", "", "The voice on the monitor was never the Guide.", "",
             "A game by Karman"]

    def draw(frame):
        screen.fill((4, 3, 6))
        for i, line in enumerate(lines):
            font = FONTS["title"] if i == 0 else FONTS["mono"]
            color = WHITE if i == 0 else ((150, 30, 30) if line == "SUBJECT COPY: INCOMPLETE" else (190, 185, 195))
            draw_text(screen, line, font, color, WIDTH // 2, 120 + i * 40, center=True)

    draw(0)
    analog.static_burst(screen, clock, 40, True)
    wait_for_key(screen, clock, draw, 1, 60)


def show_ending_choice(screen, clock):
    """The last scene: a plain white room, the beep from the whole game is now clearly a heart monitor,
    and one quiet choice. There is no timer and no right answer. Returns 'stay' or 'let_go'."""
    sound.stop_music()
    selected = 0
    frame = 0
    while True:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN and frame > 90:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
                    selected = 1 - selected
                    sound.play("click")
                elif event.key in CONFIRM_KEYS:
                    return "stay" if selected == 0 else "let_go"
        if frame % 90 == 45:
            sound.play("beep")
        screen.fill((236, 238, 240))
        draw_monitor_line(screen, ((frame - 45) % 90) * 9, 300, (120, 150, 130))
        if frame > 30:
            draw_text(screen, "They are still in there.", FONTS["big"], (70, 70, 78), WIDTH // 2, 170, center=True, shadow=None)
        if frame > 90:
            for i, label in enumerate(("STAY WITH THEM", "LET GO")):
                x = 280 + i * 240
                if i == selected:
                    draw_text(screen, "> %s <" % label, FONTS["big"], (150, 40, 40), x, 400, center=True, shadow=None)
                else:
                    draw_text(screen, label, FONTS["big"], (130, 130, 138), x, 400, center=True, shadow=None)
            draw_text(screen, "LEFT / RIGHT + ENTER", FONTS["mono_small"], (170, 170, 176), WIDTH // 2, HEIGHT - 26,
                      center=True, shadow=None)
        pygame.display.flip()
        clock.tick(FPS)


def show_let_go(screen, clock):
    """The beep slows down, then stops. One line appears."""
    beeps = [0, 100, 250, 450]                     # frame of each beep: further and further apart, then none
    frame = 0
    while frame < 800:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
        if frame in beeps:
            sound.play("beep")
        blip = None
        for b in beeps:
            if 0 <= frame - b < 80:
                blip = (frame - b) * 10
        screen.fill((236, 238, 240))
        draw_monitor_line(screen, blip, 300, (120, 150, 130))
        if frame > 560:
            draw_text(screen, "SUBJECT 0 RECOVERED.", FONTS["big"], (70, 70, 78), WIDTH // 2, 170, center=True, shadow=None)
        pygame.display.flip()
        clock.tick(FPS)


def show_credits(screen, clock):
    """Credits roll with no music. Enter skips them."""
    lines = ["HALLOWED GROUNDS", "", "A game by Karman", "", "",
             "Designations 01 through 04", "were never four separate recordings.", "",
             "The beep was always the beep.", "", "", "SUBJECT 0 RECOVERED", "", "", ""]
    y = float(HEIGHT)
    frame = 0
    while y > -len(lines) * 40:
        frame += 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN and frame > 30 and event.key in CONFIRM_KEYS + (pygame.K_ESCAPE,):
                return
        y -= 0.9
        screen.fill((4, 3, 6))
        for i, line in enumerate(lines):
            font = FONTS["title"] if i == 0 else FONTS["mono"]
            draw_text(screen, line, font, (190, 185, 195), WIDTH // 2, int(y + i * 40), center=True)
        pygame.display.flip()
        clock.tick(FPS)


# ==================================================================
# 7. PLAY_ROOM  -  the heart of the game
# ==================================================================
def play_room(screen, clock, room, index, lives, collected, collected_artifacts=None):
    """
    Plays one room until something ends it.
    Returns (result, lives) where result is 'escaped', 'dead' or 'menu'.
    """
    chapter = chapter_info(room)
    chap_no = chapter_number(room)
    difficulty = chapter.get("difficulty", 1.0)
    collected_artifacts = collected_artifacts if collected_artifacts is not None else []
    plan = plan_extras(room, index, collected_artifacts)
    room_no = plan["room_no"]
    safe = plan["safe"]
    dark = plan["dark"]

    # --- Build everything in the room from the JSON ---
    platforms = [pygame.Rect(*p) for p in room_platforms(room)]
    pits = room.get("pits", [])
    traps = [] if safe else [dict(t, rect=pygame.Rect(t["x"], t["y"], t["w"], t.get("h", 14))) for t in room.get("traps", [])]
    crumbles = [{"rect": pygame.Rect(*c), "state": "solid", "timer": 0} for c in room.get("crumbles", [])]
    boss_doors = [pygame.Rect(x, y, 46, 90) for x, y in room.get("boss_doors", [])]
    collapse_queue = [pygame.Rect(*p) for p in room.get("collapse_platforms", [])]  # removed one by one in the Warden's phase 3
    collapse_timer = 0
    crumble_of = {id(c["rect"]): c for c in crumbles}
    pre = preset()
    pos, length = chapter_position(index)
    bg = visuals.Background(chapter, chap_no, index, pos, length)
    particles = visuals.Particles()
    sprite = visuals.PlayerSprite()
    escaping = 0                                 # counts up while the door swings open
    door = pygame.Rect(*room["door"])
    key_rect = pygame.Rect(room["key"][0], room["key"][1], KEY_SIZE, KEY_SIZE)
    tape_text = room.get("scroll", "")
    tape_rect = None
    if tape_text and "scroll_pos" in room:
        tape_rect = pygame.Rect(room["scroll_pos"][0], room["scroll_pos"][1], TAPE_W, TAPE_H)
    tape_taken = tape_rect is None or tape_text in collected
    monsters = build_monsters(room, difficulty, index, strip=safe)
    projectiles = []            # each is a dict: x, y, vx, size

    # --- Extras for this room ---
    hide_spot = plan["hide"]                       # a footage gap (or None)
    hidden = False
    found_timer = 0
    audit_state = "idle"
    audit_timer = random.randint(840, 1080)
    audit_warning = 0
    audit_scan = 0
    audit_hit = False
    note = plan["note"]                            # {"rect", "text"} or None
    note_taken = note is None or note["text"] in collected
    battery_item = plan["battery"]
    battery_taken = False
    artifact = plan["artifact"]
    secret = plan["secret"]
    secret_found = secret is not None and room_no in settings["secrets"]
    secret_open = 1.0 if secret_found else 0.0
    secret_note_taken = secret is None or secret["text"] in collected
    marks = list(plan["marks"])
    if settings["loops"] > 0:                      # after choosing STAY, every room carries one more mark
        marks.append({"kind": "scratch", "x": 90 + (index * 53) % 620, "y": 190, "count": min(settings["loops"] + 4, 9)})
    hush = None
    if plan["hush"]:
        hush = {"x": 700.0 if PLAYER_W + room["player_start"][0] < WIDTH // 2 else 100.0, "dir": 0, "fade": 0.0}
        hush["dir"] = -1 if hush["x"] > WIDTH // 2 else 1
    if safe:
        lives = max_lives()                        # a quiet room: rest
        RUN["battery"] = BATTERY_MAX
    if dark and RUN["battery"] < 40:
        RUN["battery"] = 40                        # a little grace so a retry is never pitch black

    # --- Player state ---
    player = pygame.Rect(room["player_start"][0], room["player_start"][1], PLAYER_W, PLAYER_H)
    vel_y = 0.0
    on_ground = False
    coyote = 0
    jump_buffer = 0
    facing = 1
    has_key = False
    has_charge = False                             # carrying the boss-defeating charge item
    stamina = STAMINA_MAX                          # running uses this up; standing or walking refills it
    tired = False                                  # True after stamina hits zero: no running until it recovers
    noise_events = []                              # every sound you make: {"x", "y", "radius", "life"}. Creatures listen to these.
    key_from_boss = bool(room.get("key_from_boss"))
    if key_from_boss:
        key_rect = pygame.Rect(-300, -300, KEY_SIZE, KEY_SIZE)   # parked off-screen until the boss drops it
    charge_rect = pygame.Rect(room["charge_item"][0], room["charge_item"][1], 26, 26) if room.get("charge_item") else None
    charge_taken = charge_rect is None
    charge_respawn_timer = 0
    warning_flicker = 0
    invincible = 0
    knock_vx = 0
    knock_frames = 0
    shake = 0
    message, message_timer = "", 0
    if safe:
        message, message_timer = "THE ROOM IS QUIET. REST HERE.", 120
    frame = 0
    world = pygame.Surface((WIDTH, HEIGHT))
    safe_pos = player.topleft                    # where you reappear if you fall into a pit

    sound.play_music(chap_no)
    analog.set_level(chap_no)
    scare_flash = 0
    first_time_kinds = {m.kind for m in monsters if FIRST_SEEN_KIND.get(m.kind) == index}
    entering_final_tape = chap_no == len(CHAPTER_ORDER) - 1 and pos == 0
    is_boss_room = bool(room.get("boss_intro"))
    if first_time_kinds or entering_final_tape or is_boss_room:
        sound.play("shriek")
        scare_boss = next((m.kind for m in monsters if m.kind in ("doorstalker", "beamer", "summoner", "guardian", "warden", "secret_boss")), None)
        visuals.jumpscare_sequence(screen, clock, frames=22 if is_boss_room else 18, big=True,
                                   boss_kind=scare_boss if is_boss_room else None)
    if is_boss_room and room.get("boss_lore"):
        show_boss_lore(screen, clock, [tuple(e) for e in room["boss_lore"]], chap_no)
    # Glitchy picture is ONLY for boss fights: add "boss": "mini" or "boss" to a room in rooms.json
    analog.set_boss(room.get("boss", 0))

    while True:
        frame += 1
        forced_hit = None                        # set when something catches you outside the normal hit checks
        fatal_hit = False                        # the Auditor ends a run as soon as its scan verifies you
        warning_flicker = max(0, warning_flicker - 1)
        warning_alarm_played = False
        if charge_respawn_timer > 0:
            charge_respawn_timer -= 1
            if charge_respawn_timer == 0 and charge_rect is not None:
                charge_taken = False
        jumped = False

        # ---------- 1. Events ----------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB and settings.get("active_title") == "<dev>":
                    sound.play("static")
                    return "skip", lives
                elif event.key in JUMP_KEYS:
                    jump_buffer = JUMP_BUFFER_FRAMES
                    hidden = False               # jumping out of the footage gap
                elif event.key == pygame.K_ESCAPE:
                    if show_pause_menu(screen, clock, chap_no, collected, world) == "menu":
                        return "menu", lives
                    lives = min(lives, max_lives())
                elif event.key in HIDE_KEYS and not escaping:
                    if hidden:
                        hidden = False
                    elif hide_spot is not None and on_ground and player.colliderect(hide_spot):
                        hidden = True
                        found_timer = 0
                        player.centerx = hide_spot.centerx
                        sound.play("click")
            elif event.type == pygame.KEYUP:
                if event.key in JUMP_KEYS and vel_y < JUMP_CUT:
                    vel_y = JUMP_CUT                 # let go early = shorter hop (but never a tiny one)

        # ---------- 2. Player movement ----------
        keys = pygame.key.get_pressed()
        move = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move += 1
        if hidden and move:
            hidden = False                           # walking out of the footage gap
        if hidden:
            move = 0                                 # hiding means standing perfectly still
        if escaping:
            move = 0                                 # no steering while the door opens
            escaping += 1
            player.x += max(-3, min(3, door.centerx - player.centerx))     # walk into the doorway
        if move:
            facing = move

        # Running: hold Shift while moving. It is faster, but it drains stamina and it is loud.
        shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        running = bool(move) and bool(shift) and stamina > 0 and not tired
        if running:
            stamina -= STAMINA_DRAIN * (0.78 if title_active("FIRST FOOTAGE") else 1.0)
            if stamina <= 0:
                stamina, tired = 0.0, True           # worn out: cannot run again until stamina recovers
        else:
            stamina = min(STAMINA_MAX, stamina + STAMINA_REGEN * (1.45 if title_active("STILL HERE") else 1.0))
            if tired and stamina >= STAMINA_RECOVER:
                tired = False

        # Noise: running is loud, walking is soft, standing still is silent.
        # Each noise is a little record (where, how far it carries, how long it lasts) so a creature can check it later.
        if running and frame % 10 == 0:
            noise_events.append({"x": player.centerx, "y": player.centery, "radius": NOISE_RUN, "life": NOISE_LIFE})
        elif move and not running and frame % 24 == 0:
            noise_events.append({"x": player.centerx, "y": player.centery, "radius": NOISE_WALK, "life": NOISE_LIFE})
        for n in noise_events:
            n["life"] -= 1
        noise_events[:] = [n for n in noise_events if n["life"] > 0]

        if knock_frames > 0:                         # being knocked back: can't steer
            dx = knock_vx
            knock_frames -= 1
        else:
            dx = move * (RUN_SPEED if running else MOVE_SPEED)

        # Everything solid this frame: platforms, plus crumbling platforms that have not fallen yet
        solids = platforms + [c["rect"] for c in crumbles if c["state"] != "gone"]

        # Move sideways first, then fix any overlap with platforms
        player.x += int(dx)
        for p in solids:
            if player.colliderect(p):
                if dx > 0:
                    player.right = p.left
                elif dx < 0:
                    player.left = p.right
        player.x = max(0, min(WIDTH - PLAYER_W, player.x))

        # Jumping (with coyote time and a jump buffer, so it feels fair)
        coyote = COYOTE_FRAMES if on_ground else max(0, coyote - 1)
        jump_buffer = max(0, jump_buffer - 1)
        if jump_buffer > 0 and coyote > 0:
            vel_y = JUMP_SPEED
            coyote = 0
            jump_buffer = 0
            jumped = True
            sound.play("jump")

        # Then move up/down and fix overlap. Moving UP into a platform bumps your head.
        vel_y = min(vel_y + GRAVITY, MAX_FALL_SPEED)
        player.y += round(vel_y)
        on_ground = False
        for p in solids:
            if player.colliderect(p):
                if vel_y > 0:
                    player.bottom = p.top
                    on_ground = True
                    c = crumble_of.get(id(p))
                    if c is not None and c["state"] == "solid":       # you stepped on it: it starts to crumble
                        c["state"], c["timer"] = "shaking", pre["crumble"]
                elif vel_y < 0:
                    player.top = p.bottom
                vel_y = 0
        if player.top < 0:
            player.top = 0

        # Crumbling platforms fall apart, then grow back a couple of seconds later
        for c in crumbles:
            if c["state"] == "shaking":
                c["timer"] -= 1
                if c["timer"] <= 0:
                    c["state"], c["timer"] = "gone", 150
                    particles.burst(c["rect"].centerx, c["rect"].centery, 12, (130, 115, 100), speed=2.0, life=30, size=3, gravity=0.15)
            elif c["state"] == "gone":
                c["timer"] -= 1
                if c["timer"] <= 0 and not player.colliderect(c["rect"].inflate(6, 6)):
                    c["state"] = "solid"

        # Remember the last safe spot you stood on (not near spikes), for pit respawns
        if on_ground:
            for p in platforms:
                if p.top == player.bottom and p.left < player.right and p.right > player.left:
                    near_spikes = any(player.colliderect(t["rect"].inflate(40, 40)) for t in traps)
                    if not near_spikes:
                        safe_pos = (max(p.left + 6, min(player.x, p.right - PLAYER_W - 6)), p.top - PLAYER_H)
                    break

        sprite.update(player, vel_y, on_ground, move, facing, invincible, frame,
                      particles if PLAYER_PUFFS else _NO_PARTICLES, running=running)

        # Fell into a pit?
        if player.top > HEIGHT + 10:
            sound.play("hit")
            shake = 12
            particles.burst(player.centerx, HEIGHT - 10, 12, (170, 55, 70), speed=2.6, life=30, size=3, up=2.5)
            if pre["pit_costs_life"]:
                lives -= 1
                if lives <= 0:
                    return "dead", 0
            player.topleft = safe_pos
            vel_y, knock_frames, invincible = 0.0, 0, 60
            message, message_timer = "WATCH YOUR STEP", 70

        # ---------- 3. Monsters and projectiles ----------
        for trap in traps:
            warning_now = trap_warning(trap, frame)
            if warning_now and not trap.get("alarm_active", False):
                warning_flicker = max(warning_flicker, 55)
                if not warning_alarm_played:
                    sound.play("alarm")
                    warning_alarm_played = True
            trap["alarm_active"] = warning_now
        for m in monsters:
            for name in m.update(player, projectiles, hidden, noise_events):
                if name == "telegraph":
                    if not warning_alarm_played:
                        sound.play("alarm")
                        warning_alarm_played = True
                    warning_flicker = max(warning_flicker, 66)
                else:
                    sound.play(name)
                if name == "shoot":
                    particles.burst(m.rect.centerx, m.rect.centery, 8, (150, 240, 150), speed=2.2, life=18, size=3, gravity=0)
                elif name == "wake":
                    particles.burst(m.rect.centerx, m.rect.centery, 10, (190, 80, 220), speed=2.0, life=24, size=3)
                    scare_flash = 10
                    sound.play("shriek")
            if m.kind == "warden" and m.just_entered_phase:
                scare_flash = 14
                sound.play("shriek")
                particles.burst(m.rect.centerx, m.rect.centery, 36, (210, 70, 70), speed=3.4, life=36, size=4)
                if m.just_entered_phase == 3:
                    collapse_timer = 1          # start dropping platforms on the very next frame
        if collapse_timer > 0:                     # the Warden's arena falling apart, one platform at a time
            collapse_timer -= 1
            if collapse_timer == 0 and collapse_queue:
                gone = collapse_queue.pop(0)
                if gone in platforms:
                    platforms.remove(gone)
                particles.burst(gone.centerx, gone.centery, 18, (120, 40, 40), speed=2.2, life=30, size=3)
                sound.play("manifest")
                if collapse_queue:
                    collapse_timer = 60
        for pr in projectiles:
            turn_rate = pr.get("turn_rate", 0.0)
            if turn_rate and not hidden:
                cx = pr["x"] + pr["size"] / 2
                cy = pr["y"] + pr["size"] / 2
                target_angle = math.atan2(player.centery - cy, player.centerx - cx)
                angle = math.atan2(pr.get("vy", 0.0), pr["vx"])
                delta = (target_angle - angle + math.pi) % (2 * math.pi) - math.pi
                angle += max(-turn_rate, min(turn_rate, delta))
                speed = math.hypot(pr["vx"], pr.get("vy", 0.0))
                pr["vx"], pr["vy"] = math.cos(angle) * speed, math.sin(angle) * speed
            pr["x"] += pr["vx"]
            pr["y"] += pr.get("vy", 0.0)
        projectiles[:] = [pr for pr in projectiles
                          if -30 < pr["x"] < WIDTH + 30 and -30 < pr["y"] < HEIGHT + 30]

        # ---------- 3b. Extras: footage gaps, the Auditor, flashlight, Hush, secret wall ----------
        if hide_spot is not None and not hidden and not escaping and message_timer == 0 and player.colliderect(hide_spot):
            message, message_timer = "DOWN / S: ENTER THE GAP", 45
        if hidden:
            # A Designation that stands next to the gap too long finds you.
            near = any(m.kind in DESIGNATIONS and not m.defeated and
                       math.hypot(m.rect.centerx - hide_spot.centerx, m.rect.centery - hide_spot.centery) < 70
                       for m in monsters)
            found_timer = found_timer + 1 if near else max(0, found_timer - 2)
            if found_timer >= HIDE_FOUND_FRAMES:
                hidden = False
                found_timer = 0
                forced_hit = hide_spot.centerx
                message, message_timer = "IT FOUND THE GAP.", 80
        if plan["audit"] and not escaping:
            if audit_state == "idle":
                audit_timer -= 1
                if audit_timer <= 0:
                    audit_state, audit_warning, audit_hit = "warning", 120, False
                    warning_flicker = max(warning_flicker, 96)
                    if not warning_alarm_played:
                        sound.play("alarm")
                        warning_alarm_played = True
            elif audit_state == "warning":
                audit_warning -= 1
                if audit_warning <= 0:
                    audit_state, audit_scan = "scan", 72
                    sound.play("manifest")
            elif audit_state == "scan":
                audit_scan -= 1
                if not hidden and not audit_hit:
                    forced_hit = player.centerx
                    fatal_hit = True
                    audit_hit = True
                if audit_scan <= 0:
                    audit_state, audit_timer = "idle", random.randint(1500, 2100)
        if dark and not escaping:
            RUN["battery"] = max(0.0, RUN["battery"] - BATTERY_DRAIN * (0.65 if title_active("BELOW THE RECORD") else 1.0))
        if hush is not None and not escaping:
            hush["x"] += hush["dir"] * HUSH_SPEED
            if hush["x"] < 40:
                hush["x"], hush["dir"] = 40.0, 1
            elif hush["x"] > WIDTH - 40:
                hush["x"], hush["dir"] = float(WIDTH - 40), -1
            if abs(player.centerx - hush["x"]) < HUSH_RANGE:
                hush["fade"] = min(float(HUSH_FADE_FRAMES), hush["fade"] + 1)       # the sound slips away over 2 seconds
            else:
                hush["fade"] = max(0.0, hush["fade"] - 3)                           # and comes back quickly
            sound.set_volume(settings["volume"] / 100 * (1 - hush["fade"] / HUSH_FADE_FRAMES))
            if hush["fade"] >= HUSH_FADE_FRAMES and (move != 0 or jumped):
                forced_hit = hush["x"]                                              # you moved in the silence: it finds you
                message, message_timer = "IT HEARD YOU.", 60
        if secret is not None:
            if not secret_found and player.colliderect(secret["panel"]):
                secret_found = True
                if room_no not in settings["secrets"]:
                    settings["secrets"].append(room_no)
                    save_settings()
                if secret["reward"] == "battery":
                    RUN["battery"] = BATTERY_MAX
                elif lives < max_lives():
                    lives += 1
                message, message_timer = "A WALL GIVES WAY.", 90
                sound.play("manifest")
                particles.burst(secret["panel"].centerx, secret["panel"].centery, 20, (120, 100, 90), speed=2.4, life=34, size=3)
            if secret_found:
                secret_open = min(1.0, secret_open + 0.05)

        # ---------- 4. Getting hit (and defeating a boss) ----------
        if escaping:
            pass                                     # no hits while the door is opening
        elif invincible > 0 and not fatal_hit:
            invincible -= 1
        else:
            hit_from = None
            defeated = False
            boss_finished = False
            for m in monsters:
                if m.defeated or not player.colliderect(m.rect):
                    continue
                if hidden and m.kind in DESIGNATIONS:
                    continue                         # you are between frames: it walks right past you
                last_pos = m.rect.topleft
                if m.kind in ("doorstalker", "beamer", "summoner", "warden") and has_charge \
                        and m.vulnerable and m.boss_hit_cooldown == 0:
                    m.boss_hp -= 2 if title_active("NO EXIT") else 1
                    m.boss_hit_cooldown = 45
                    has_charge = False
                    defeated = True                  # the hit connected; do not damage the player too
                    if m.kind == "doorstalker" and m.boss_hp > 0:
                        m.state, m.timer = "hidden", 55
                        m.x, m.y = -400.0, -400.0
                        charge_respawn_timer = 105
                    elif m.kind == "beamer" and m.boss_hp > 0:
                        m.state, m.timer, m.exposed_timer = "idle", 70, 0
                        charge_respawn_timer = 70
                    elif m.kind == "summoner" and m.boss_hp > 0:
                        m.exposed_timer = 0
                        charge_respawn_timer = 70
                    elif m.kind == "warden" and m.boss_hp > 0:
                        m.exposed_timer = 0
                        m.phase_timer = max(m.phase_timer, 75)
                        charge_respawn_timer = 70
                    if m.boss_hp <= 0:
                        m.defeated = True
                        boss_finished = True
                    else:
                        if m.kind == "warden" and m.phase == 3 and m.boss_hp <= 2:
                            message, message_timer = "THE ROOM IS CLOSING IN", 120
                        else:
                            message, message_timer = "SIGNAL BROKEN  //  %d LEFT" % m.boss_hp, 100
                        sound.play("boss_hit")
                        vel_y = JUMP_SPEED * 0.55
                        invincible = 45
                elif m.kind in ("guardian", "secret_boss") and vel_y > 0 and player.bottom - m.rect.top < 18:
                    vel_y = JUMP_SPEED * 0.55
                    defeated = True
                    if m.vulnerable and m.boss_hit_cooldown == 0:
                        m.boss_hp -= 2 if title_active("NO EXIT") else 1
                        m.boss_hit_cooldown = 48
                        if m.boss_hp <= 0:
                            m.defeated = True
                            boss_finished = True
                        else:
                            if m.boss_hp == (3 if m.kind == "secret_boss" else 2) and not m.special_mode:
                                m.special_mode = True
                                m.timer = 65
                                warning_flicker = max(warning_flicker, 90)
                                scare_flash = 14
                                sound.play("shriek")
                                particles.burst(m.rect.centerx, m.rect.centery, 32,
                                                (193, 93, 63), speed=3.0, life=35, size=4)
                                message, message_timer = "DOUBLE VERDICT // JUMP BOTH WAVES", 150
                            else:
                                message, message_timer = "PLATE BROKEN  //  %d LEFT" % m.boss_hp, 100
                            sound.play("boss_hit")
                        invincible = 48
                    else:
                        # A stomp on its closed armor is safe, but it does not hurt the boss.
                        invincible = max(invincible, 18)
                else:
                    hit_from = m.rect.centerx
                if defeated:
                    if not boss_finished and m.kind in ("guardian", "secret_boss"):
                        particles.burst(last_pos[0] + m.w // 2, last_pos[1], 18,
                                        (210, 190, 130), speed=2.8, life=32, size=3)
                    if boss_finished:
                        sound.play("defeat")
                    particles.burst(last_pos[0] + m.w // 2 if hasattr(m, "w") else last_pos[0],
                                    last_pos[1] + (m.h if hasattr(m, "h") else m.size) // 2,
                                    30 if boss_finished else 16,
                                    (255, 225, 150) if boss_finished else (225, 75, 80),
                                    speed=3.5, life=40, size=4)
                    if boss_finished and key_from_boss and not has_key:
                        key_rect.topleft = last_pos
                        message, message_timer = "THE PRESENCE IS GONE", 90
                    if boss_finished:
                        invincible = pre["invincible"]
                break
            if not defeated and hit_from is None and not hidden:
                for pr in projectiles:
                    pr_rect = pygame.Rect(int(pr["x"]), int(pr["y"]), pr["size"], pr["size"])
                    if player.colliderect(pr_rect):
                        hit_from = pr_rect.centerx
                        projectiles.remove(pr)
                        break
            if not defeated and hit_from is None:
                for m in monsters:
                    br = m.beam_rect if hasattr(m, "beam_rect") else None
                    if br is not None and player.colliderect(br):
                        hit_from = player.centerx        # a full-width beam has no meaningful "side"
                        break
                    ar = m.attack_rect if hasattr(m, "attack_rect") else None
                    if ar is not None and player.colliderect(ar):
                        hit_from = ar.centerx
                        break
            if not defeated and hit_from is None:
                for t in traps:
                    if trap_active(t, frame) and player.colliderect(t["rect"]):
                        hit_from = t["rect"].centerx
                        break
            if not defeated and hit_from is None and forced_hit is not None:
                hit_from = forced_hit                    # found in a gap, audited, or caught in the Hush's silence
            if hit_from is not None:
                if fatal_hit:
                    sound.play("hit")
                    visuals.jumpscare_sequence(screen, clock, frames=20, big=True)
                    return "dead", 0
                lives -= 1
                invincible = pre["invincible"]
                knock_vx = 7 if player.centerx >= hit_from else -7     # away from whatever hit us
                knock_frames = KNOCKBACK_FRAMES
                vel_y = -6
                shake = 12
                sound.play("hit")
                particles.burst(player.centerx, player.centery, 14, (230, 70, 70), speed=3.0, life=26, size=3)
                if lives <= 0:
                    return "dead", 0

        # ---------- 5. Key, tape, notes, and door ----------
        if charge_rect is not None and not charge_taken and player.colliderect(charge_rect):
            charge_taken = True
            has_charge = True
            message, message_timer = "CHARGE RECOVERED — STRIKE ON THE FLICKER", 90
            sound.play("pickup")
            particles.burst(charge_rect.centerx, charge_rect.centery, 16, (150, 210, 255), speed=2.6, life=32, size=3)
        if not has_key and player.colliderect(key_rect):
            has_key = True
            message, message_timer = "KEY RECOVERED", 90
            sound.play("pickup")
            particles.burst(key_rect.centerx, key_rect.centery, 16, (255, 220, 90), speed=2.6, life=32, size=3, gravity=0.02)
        if battery_item is not None and not battery_taken and player.colliderect(battery_item):
            battery_taken = True
            RUN["battery"] = min(BATTERY_MAX, RUN["battery"] + BATTERY_PICKUP)
            message, message_timer = "BATTERY RECOVERED", 90
            sound.play("pickup")
            particles.burst(battery_item.centerx, battery_item.centery, 12, (150, 240, 170), speed=2.2, life=28, size=3)
        if artifact is not None and player.colliderect(artifact["rect"]):
            artifact_id = artifact["id"]
            if artifact_id not in collected_artifacts:
                collected_artifacts.append(artifact_id)
            artifact = None
            count = len(collected_artifacts)
            message, message_timer = "RELIC RECOVERED  //  %d/3" % count, 110
            sound.play("pickup")
            particles.burst(player.centerx, player.centery, 20, (188, 174, 129), speed=2.8, life=34, size=3)
            show_tape(screen, clock, artifact.get("text", artifact.get("name", "RELIC RECOVERED")), chap_no, world)
            if count == len(ARTIFACTS):
                message, message_timer = "THREE PIECES. A DOOR BELOW THE RECORDING OPENS.", 180
                sound.play("manifest")

        if not tape_taken and player.colliderect(tape_rect):
            tape_taken = True
            if tape_text not in collected:
                collected.append(tape_text)
            particles.burst(tape_rect.centerx, tape_rect.centery, 14, (230, 80, 80), speed=2.4, life=28, size=3, gravity=0.02)
            show_tape(screen, clock, tape_text, chap_no, world)
        if note is not None and not note_taken and player.colliderect(note["rect"]):
            note_taken = True
            if note["text"] not in collected:
                collected.append(note["text"])
            particles.burst(note["rect"].centerx, note["rect"].centery, 10, (220, 215, 180), speed=2.0, life=26, size=2, gravity=0.02)
            show_tape(screen, clock, note["text"], chap_no, world)
        if secret is not None and not secret_note_taken and secret_found and secret_open >= 0.6 \
                and player.colliderect(secret["note_rect"]):
            secret_note_taken = True
            if secret["text"] not in collected:
                collected.append(secret["text"])
            show_tape(screen, clock, secret["text"], chap_no, world)

        if player.colliderect(door) and escaping == 0:
            if has_key:
                escaping = 1                 # the door swings open, you step through, the picture fades
                sound.play("escape")
                particles.burst(door.centerx, door.centery, 26, (240, 240, 200), speed=3.2, life=34, size=3, gravity=-0.02)
            elif move != 0 and frame > 20:   # only nag when you actually push into it
                message, message_timer = "LOCKED. FIND THE KEY.", 60

        # Later tapes: the steady machine beep from the story. In the Warden's final phase, and only
        # there, it speeds up -- the one place in the whole game this sound is allowed to change pace.
        warden = next((m for m in monsters if m.kind == "warden"), None)
        beep_interval = 90 if (warden is not None and warden.phase == 3) else 300
        if chap_no >= 3 and frame % beep_interval == beep_interval // 2:
            sound.play("beep")

        # ---------- 6. Drawing ----------
        try:
            bg.draw(world, frame, player.centerx, warning_flicker)
        except pygame.error:
            world.fill(tuple(chapter.get("sky", (20, 20, 30))))   # picture trouble: at least show a plain colored room
        for px, pw in pits:
            draw_pit(world, px, pw)
            if frame % 6 == 0:                                       # glowing embers rise out of the pit
                particles.emit(px + random.uniform(0, pw), 496, 0, -0.7, 40, 2, (170, 60, 70))
        for p in platforms:
            visuals.draw_platform(world, p, chapter, frame)
        for c in crumbles:
            draw_crumble(world, c, chapter, frame)
            if c["state"] == "shaking" and frame % 3 == 0:           # dust falls off a crumbling platform
                particles.emit(c["rect"].x + random.uniform(0, c["rect"].w), c["rect"].bottom, 0, 0.6, 22, 2, (125, 112, 100), gravity=0.05)
        for t in traps:
            draw_spikes(world, t["rect"], trap_active(t, frame), trap_warning(t, frame), frame)
        for mk in marks:
            draw_mark(world, mk, frame)
        if secret is not None:
            if title_active("ARCHIVIST"):
                visuals.add_glow(world, secret["panel"].centerx, secret["panel"].centery, 52, (43, 34, 21))
            draw_secret_panel(world, secret, secret_open, frame)
            if secret_found and secret_open >= 0.6 and not secret_note_taken:
                draw_note(world, secret["note_rect"], frame)
        if hide_spot is not None:
            draw_gap(world, hide_spot, frame, hidden)
        if note is not None and not note_taken:
            draw_note(world, note["rect"], frame)
        if battery_item is not None and not battery_taken:
            draw_battery(world, battery_item, frame)
        if artifact is not None:
            draw_artifact(world, artifact, frame)
        if boss_doors:
            active_stalker = next((m for m in monsters if m.kind == "doorstalker"), None)
            for i, d in enumerate(boss_doors):
                state = "idle"
                if active_stalker is not None and active_stalker.active_door == i and active_stalker.state in ("telegraph", "manifest"):
                    state = active_stalker.state
                visuals.draw_boss_door(world, d, state, frame)
        visuals.draw_door(world, door, has_key, frame, min(1.0, escaping / 16))
        if not has_key:
            visuals.draw_key(world, key_rect, frame)
            if frame % 18 == 0:
                particles.emit(key_rect.centerx + random.uniform(-14, 14), key_rect.centery + random.uniform(-12, 8), 0, -0.4, 26, 2, (255, 235, 150))
        if not tape_taken:
            visuals.draw_tape(world, tape_rect, frame)
        if charge_rect is not None and not charge_taken:
            visuals.draw_charge_item(world, charge_rect, frame)
        if has_charge:                                    # a soft glow around the player while carrying the charge
            visuals.add_glow(world, player.centerx, player.centery, 34, (25, 50, 80))
        for m in monsters:
            m.draw(world, frame, player)
            if m.is_copy and not m.defeated:              # a copy is a little TOO clean: a thin pale ring above its head
                pygame.draw.circle(world, (205, 215, 225), (m.rect.centerx, m.rect.top - 10), 4, 1)
        for pr in projectiles:
            visuals.draw_projectile(world, pr, frame)
        if not hidden:
            try:
                draw_player(world, player, facing, invincible, frame, sprite)
            except pygame.error:
                pygame.draw.rect(world, (225, 225, 235), player, border_radius=6)   # picture trouble: a plain player rectangle
        for n in (noise_events if SHOW_NOISE_RINGS else []):      # thin rings that spread out from where you made noise
            ring = int(n["radius"] * (1 - n["life"] / NOISE_LIFE)) + 1
            pygame.draw.circle(world, (90, 90, 110), (n["x"], n["y"]), ring, 1)
        particles.update()
        particles.draw(world)
        if dark and not hidden:                           # the flashlight: darkness everywhere except a circle around you
            b = RUN["battery"] / BATTERY_MAX
            light_r = LIGHT_R_MIN + (LIGHT_R_MAX - LIGHT_R_MIN) * min(1.0, b / 0.5)
            if RUN["battery"] < 20 and (frame // 3) % 9 == 0:
                light_r *= 0.55                           # a dying battery flickers
            draw_darkness(world, player.centerx, player.centery, light_r)
            visuals.draw_door(world, door, has_key, frame, min(1.0, escaping / 16))     # the goal is never lost in the dark
            if not has_key:
                visuals.draw_key(world, key_rect, frame)
            if battery_item is not None and not battery_taken:
                draw_battery(world, battery_item, frame)
        if hidden:                                        # inside a footage gap you can barely see anything
            draw_darkness(world, hide_spot.centerx, hide_spot.y + 16, 26, dense=True)
        # The chandelier and room lights snap out in irregular bursts before an attack.
        if warning_flicker and warning_flicker % 9 in (0, 1, 5):
            draw_darkness(world, player.centerx, player.centery, 68, dense=True)
        if artifact is not None and title_active("ARCHIVIST"):
            visuals.add_glow(world, artifact["rect"].centerx, artifact["rect"].centery, 58, (55, 43, 25))

        offset = (random.randint(-4, 4), random.randint(-4, 4)) if shake > 0 else (0, 0)
        shake = max(0, shake - 1)
        screen.fill(BLACK)
        screen.blit(world, offset)
        if is_boss_room:
            boss = next((m for m in monsters if m.kind in ("doorstalker", "beamer", "summoner", "guardian", "warden", "secret_boss") and not m.defeated), None)
            if boss is not None:
                camera_phase = boss.phase if boss.kind == "warden" else 2 if getattr(boss, "special_mode", False) else 1
                visuals.draw_surveillance_overlay(screen, frame, boss.kind, camera_phase)
        if hush is not None:
            draw_vignette(screen, hush["fade"] / HUSH_FADE_FRAMES)
        if audit_state == "scan":
            draw_audit_overlay(screen, frame, audit_state, audit_warning, audit_scan)
        message_timer = max(0, message_timer - 1)
        draw_hud(screen, lives, has_key, len(collected), plan["label"], message, message_timer, has_charge,
                 stamina, tired, RUN["battery"] if dark else None)
        draw_boss_status(screen, monsters)
        if frame < 20:
            visuals.fade(screen, 255 - frame * 13)                   # fade in from black
        if escaping > 12:
            visuals.fade(screen, (escaping - 12) * 12)               # fade out through the door
        if scare_flash > 0:
            visuals.draw_jumpscare(screen, frame, big=False)
            scare_flash -= 1
        present(screen, chap_no + 1)
        clock.tick(FPS)
        if escaping > 34:
            return "escaped", lives


# ==================================================================
# 8. RUN_GAME AND MAIN  -  the flow between rooms
# ==================================================================
def run_game(screen, clock, slot, start_index, lives, collected, collected_artifacts=None,
             secret_boss_defeated=False):
    """Plays rooms one after another, starting at start_index (so saves can resume)."""
    analog.reset_timecode()
    collected_artifacts = list(collected_artifacts or [])
    index = start_index
    result = "escaped"
    while True:
        while index < len(ROOMS):
            room = ROOMS[index]
            chap_no = chapter_number(room)

            if is_first_in_chapter(index) and settings["chapter_intros"]:
                show_chapter_intro(screen, clock, chap_no)

            result, lives = play_room(screen, clock, room, index, lives, collected, collected_artifacts)
            analog.set_boss(0)               # back to a clean picture after any room
            sound.set_volume(settings["volume"] / 100)    # the Hush may have muted everything

            if result == "menu":
                return
            if result == "dead":
                if show_game_over(screen, clock, chap_no) == 0:
                    lives = max_lives()      # try this room again with full lives
                    continue
                return
            if result not in ("escaped", "skip"):
                return

            # The room was cleared, or the private dev title skipped it.
            was_cleared = result == "escaped"
            index += 1
            just_finished = index - 1
            new_titles = []
            if was_cleared:
                if just_finished == 0 and unlock_title("FIRST FOOTAGE"):
                    new_titles.append("FIRST FOOTAGE")
                if len(collected) >= 3 and unlock_title("ARCHIVIST"):
                    new_titles.append("ARCHIVIST")
                if just_finished == 15 and unlock_title("THE HOUSE KNOWS"):
                    new_titles.append("THE HOUSE KNOWS")
                if is_last_in_chapter(just_finished) and chap_no == 0 and unlock_title("STILL HERE"):
                    new_titles.append("STILL HERE")
                if index < len(ROOMS) and chapter_number(ROOMS[index]) == len(CHAPTER_ORDER) - 1 \
                        and unlock_title("BELOW THE RECORD"):
                    new_titles.append("BELOW THE RECORD")
            if is_last_in_chapter(just_finished):
                lives = max_lives()          # a new tape starts with full lives
            write_save(slot, index, lives, collected, collected_artifacts, secret_boss_defeated)
            for title in new_titles:
                show_title_recovered(screen, clock, title)
            if is_last_in_chapter(just_finished):
                show_chapter_complete(screen, clock, chap_no)

        # The three pieces of evidence open an optional room beneath the final tape.
        if (len(collected_artifacts) == len(ARTIFACTS) and SECRET_BOSS_ROOM is not None
                and not secret_boss_defeated):
            draw_menu_frame(screen, "UNSEALED", ["ENTER THE ROOM"], 0,
                            "Three relics fit the frame. Something behind it is awake.", None, 0)
            present(screen, len(CHAPTER_ORDER))
            secret_result, lives = play_room(screen, clock, SECRET_BOSS_ROOM, len(ROOMS) - 1,
                                             lives, collected, collected_artifacts)
            if secret_result == "menu":
                return
            while secret_result == "dead":
                if show_game_over(screen, clock, len(CHAPTER_ORDER) - 1) == 0:
                    lives = max_lives()
                    secret_result, lives = play_room(screen, clock, SECRET_BOSS_ROOM, len(ROOMS) - 1,
                                                     lives, collected, collected_artifacts)
                else:
                    return
            if secret_result == "escaped":
                secret_boss_defeated = True
                write_save(slot, len(ROOMS), lives, collected, collected_artifacts, True)

        # The Warden is done. The recording "ends", and then the real ending begins.
        if result == "escaped" and unlock_title("NO EXIT"):
            show_title_recovered(screen, clock, "NO EXIT")
        show_ending(screen, clock, collected)
        choice = show_ending_choice(screen, clock)
        settings["ending"] = choice
        if choice == "stay":
            settings["subject_count"] += 1       # staying means the loop goes on, as a new Subject
            settings["loops"] += 1
            save_settings()
            index, lives, collected = 0, max_lives(), []
            collected_artifacts, secret_boss_defeated = [], False
            write_save(slot, 0, lives, collected, collected_artifacts, secret_boss_defeated)
            analog.reset_timecode()
            continue
        save_settings()
        show_let_go(screen, clock)
        show_credits(screen, clock)
        return


def start_new_run(screen, clock, slot):
    write_save(slot, 0, max_lives(), [], [], False)
    run_game(screen, clock, slot, 0, max_lives(), [], [])


def play_menu(screen, clock):
    """Pick a slot, then start, continue or restart depending on what's saved there."""
    slot = show_slot_picker(screen, clock)
    if slot is None:
        return
    save = read_save(slot)

    if save is None:
        start_new_run(screen, clock, slot)
    elif save["room_index"] >= len(ROOMS):
        choice = run_menu(screen, clock, "RUN COMPLETE", ["Restart Run", "Back to Main Menu"],
                          "This slot already reached the end of the tape.")
        if choice == 0:
            start_new_run(screen, clock, slot)
    else:
        choice = run_menu(screen, clock, "SLOT %d" % slot,
                          ["Continue (Room %d)" % (save["room_index"] + 1), "Restart Run", "Back"],
                          "%d file(s) recovered so far." % len(save["collected_scrolls"]))
        if choice == 0:
            run_game(screen, clock, slot, save["room_index"], min(save["lives"], max_lives()),
                     save["collected_scrolls"], save["collected_artifacts"], save["secret_boss_defeated"])
        elif choice == 1:
            start_new_run(screen, clock, slot)


def setup():
    """Starts pygame, shows the loading bar, and loads everything."""
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    icon_path = os.path.join(RESOURCE_DIR, "assets", "hallowed_grounds_icon.png")
    try:
        pygame.display.set_icon(pygame.image.load(icon_path))
    except (FileNotFoundError, pygame.error):
        pass
    pygame.display.set_caption("Hallowed Grounds  (%s)" % BUILD)
    print("Hallowed Grounds running from:", os.path.abspath(__file__), "-", BUILD)
    clock = pygame.time.Clock()
    make_fonts()
    tasks = [
        ("Reading the tape label...", load_game_data),
        ("Loading settings...", load_settings),
        ("Tuning the speakers...", lambda: (sound.init(), sound.set_volume(settings["volume"] / 100))),
        ("Cleaning the tape heads...", lambda: analog.init(screen)),
    ]
    show_loading(screen, clock, tasks)
    return screen, clock


def main():
    screen, clock = setup()
    while True:
        sound.play_music(0)
        analog.set_level(0)
        analog.set_boss(0)
        subtitle = {"let_go": "NO FURTHER FOOTAGE", "stay": "A RECOVERED TAPE. AGAIN."}.get(settings["ending"], "A RECOVERED TAPE")
        choice = run_menu(screen, clock, "HALLOWED GROUNDS",
                          ["Play", "Recovered Titles", "Controls", "Settings", "Quit"], subtitle)
        if choice == 0:
            play_menu(screen, clock)
        elif choice == 1:
            show_titles(screen, clock)
        elif choice == 2:
            show_controls(screen, clock)
        elif choice == 3:
            show_settings(screen, clock)
        elif choice == 4:
            quit_game()


def smoke_check():
    """Initializes the real game and renders one menu frame for release-build checks."""
    screen, clock = setup()
    draw_menu_frame(screen, "HALLOWED GROUNDS", ["Play", "Quit"], 0,
                    "A RECOVERED TAPE", None, 1)
    present(screen, 1)
    pygame.display.flip()
    pygame.quit()
    print("Game startup and menu render: OK")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_extras()
    elif "--smoke" in sys.argv:
        smoke_check()
    else:
        try:
            main()
        except Exception:
            details = traceback.format_exc()
            print(details, file=sys.stderr)
            try:
                os.makedirs(USER_DATA_DIR, exist_ok=True)
                crash_path = os.path.join(USER_DATA_DIR, "crash.log")
                with open(crash_path, "a", encoding="utf-8") as f:
                    f.write("\n--- Hallowed Grounds crash ---\n")
                    f.write(details)
                if pygame.display.get_init() and hasattr(pygame.display, "message_box"):
                    try:
                        pygame.display.message_box(
                            "Hallowed Grounds stopped",
                            "The game saved an error report here:\n%s" % crash_path,
                            "error",
                        )
                    except pygame.error:
                        pass
            except OSError:
                pass
            raise
