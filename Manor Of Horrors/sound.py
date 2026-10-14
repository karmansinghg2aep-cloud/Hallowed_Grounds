"""
sound.py - all the audio for Hallowed Grounds.

No sound files needed: every sound is built from math (sine waves, noise).
Put this file in the same folder as manor.py.

The 5 functions you'll use from manor.py:
    sound.init()            - call ONCE, right after pygame.init()
    sound.set_volume(v)     - v from 0.0 to 1.0 (your Settings volume)
    sound.play("jump")      - play a short sound effect
    sound.play_music(n)     - n = 0..4, which chapter you're in (higher = creepier)
    sound.stop_music()      - fade the music out

Try it without the game:   python3 sound.py
"""
import math
import random
import array
import pygame

SR = 22050          # samples per second (quality of the sound)
TAU = math.tau      # one full circle, 2*pi

_sfx = {}           # name -> (Sound, base_volume)
_music = {}         # level -> Sound
_master = 0.7       # the volume from your Settings menu
_music_chan = None
_current_level = None
_ready = False      # False = no audio device, so every function quietly does nothing

MUSIC_LOOP_SECONDS = 4.0
MUSIC_VOL = 0.55    # music sits under the sound effects


# ---------------------------------------------------------------
# Building blocks: each returns a list of numbers between -1 and 1
# ---------------------------------------------------------------
def _sweep(f0, f1, dur, decay=4.0, vol=0.5, wave="sine"):
    """A tone that slides from pitch f0 to pitch f1."""
    n = int(SR * dur)
    out = []
    phase = 0.0
    for i in range(n):
        p = i / n
        phase += TAU * (f0 + (f1 - f0) * p) / SR
        s = math.sin(phase)
        if wave == "square":
            s = 0.6 if s > 0 else -0.6
        out.append(s * math.exp(-decay * p) * vol)
    return out


def _bell(freq, dur, vol=0.4, decay=5.0):
    """A ringing bell note (the extra 2.76x partial makes it sound metallic)."""
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        p = i / n
        s = math.sin(TAU * freq * t) + 0.4 * math.sin(TAU * freq * 2.76 * t)
        out.append(s * math.exp(-decay * p) * vol)
    return out


def _noise(dur, vol=0.4, decay=8.0, seed=1):
    rng = random.Random(seed)
    n = int(SR * dur)
    return [rng.uniform(-1, 1) * math.exp(-decay * i / n) * vol for i in range(n)]


def _mix(parts):
    """Layer sounds on top of each other. parts = [(start_seconds, samples), ...]"""
    total = max(int(start * SR) + len(s) for start, s in parts)
    out = [0.0] * total
    for start, samples in parts:
        offset = int(start * SR)
        for i, v in enumerate(samples):
            out[offset + i] += v
    return out


def _to_sound(samples):
    """Turn a list of numbers into a real pygame Sound."""
    n = len(samples)
    fade_in = int(SR * 0.005)
    fade_out = int(SR * 0.015)
    data = array.array("h")
    for i, s in enumerate(samples):
        if i < fade_in:
            s *= i / fade_in            # tiny fade-in so it doesn't click
        if i > n - fade_out:
            s *= (n - i) / fade_out     # tiny fade-out for the same reason
        s = max(-1.0, min(1.0, s))
        data.append(int(s * 32767 * 0.8))
    return pygame.mixer.Sound(buffer=data.tobytes())


def _add(name, samples, base_vol=1.0):
    _sfx[name] = (_to_sound(samples), base_vol)


# ---------------------------------------------------------------
# The sound effects
# ---------------------------------------------------------------
def _build_sfx():
    # Note pitches (Hz)
    A3, E4, A4, C5, E5, A5 = 220.0, 329.6, 440.0, 523.3, 659.3, 880.0

    _add("click", _sweep(700, 700, 0.05, 3, 0.4, "square"), 0.5)
    _add("jump", _sweep(260, 540, 0.15, 5, 0.35, "square"), 0.5)
    _add("pickup", _mix([(0.0, _bell(784, 0.35)), (0.09, _bell(1175, 0.45))]), 0.8)
    _add("scroll", _mix([(0.0, _bell(523, 0.5, 0.35)), (0.12, _bell(392, 0.7, 0.35))]), 0.8)

    # Getting hit: a noise crunch + a low thump
    _add("hit", _mix([(0.0, _noise(0.25, 0.5, 9)), (0.0, _sweep(120, 50, 0.3, 5, 0.7))]), 1.0)

    # Shooter fires: a fast falling zap with a hiss
    _add("shoot", _mix([(0.0, _sweep(1000, 180, 0.22, 6, 0.4, "square")),
                        (0.0, _noise(0.15, 0.2, 10, seed=2))]), 0.7)

    # Chaser wakes up: two low notes beating against each other, wobbling like a growl
    growl = []
    n = int(SR * 0.7)
    for i in range(n):
        t = i / SR
        p = i / n
        wobble = 0.6 + 0.4 * math.sin(TAU * 14 * t)
        s = (math.sin(TAU * 62 * t) + math.sin(TAU * 67 * t)) * 0.5 * wobble
        env = min(1.0, p * 6) * (1 - p)
        growl.append(s * env * 0.9)
    _add("wake", _mix([(0.0, growl), (0.0, _noise(0.5, 0.15, 4, seed=3))]), 1.0)

    # Banshee wail: a high note that wobbles up and down
    wail = []
    n = int(SR * 0.8)
    phase = 0.0
    for i in range(n):
        p = i / n
        f = 900 + 500 * math.sin(math.pi * p) + 40 * math.sin(TAU * 7 * i / SR)
        phase += TAU * f / SR
        wail.append(math.sin(phase) * math.sin(math.pi * p) * 0.35)
    _add("banshee", wail, 0.6)

    # Room escaped: a rising minor arpeggio (A minor - triumphant, but not cheerful)
    _add("escape", _mix([(0.00, _bell(A4, 0.5)), (0.11, _bell(C5, 0.5)),
                         (0.22, _bell(E5, 0.6)), (0.33, _bell(A5, 1.2, 0.45, 3.5))]), 0.9)

    # Wing complete: slower, bigger, with a low bell underneath
    _add("chapter_complete", _mix([(0.0, _bell(A3 / 2, 3.0, 0.5, 2.0)),
                                   (0.2, _bell(E4, 0.9)), (0.6, _bell(A4, 0.9)),
                                   (1.0, _bell(C5, 0.9)), (1.4, _bell(E5, 2.0, 0.45, 2.5))]), 0.9)

    # Game over: four bells falling down and down, then a heartbeat-thump
    _add("game_over", _mix([(0.0, _bell(E4, 0.9, 0.45, 3)), (0.55, _bell(261.6, 0.9, 0.45, 3)),
                            (1.10, _bell(A3, 1.1, 0.5, 3)), (1.70, _bell(A3 / 2, 2.0, 0.6, 2)),
                            (1.70, _sweep(90, 35, 0.6, 4, 0.7))]), 1.0)

    # --- Analog horror sounds ---
    # TV static burst (use with analog.static_burst for tape changes)
    _add("static", _noise(0.6, 0.5, 3, seed=5), 0.6)
    # A tape slowing to a stop: pitch falls away while hiss fades (good for game over)
    _add("tape_stop", _mix([(0.0, _sweep(420, 25, 0.8, 1.5, 0.5)),
                            (0.0, _noise(0.8, 0.25, 3, seed=6))]), 0.9)
    # The steady machine beep from the story twist (Chapters 4-5)
    _add("beep", _sweep(1000, 1000, 0.35, 0.4, 0.4), 0.5)

    # A jumpscare sting: a harsh falling shriek over a burst of noise
    _add("shriek", _mix([(0.0, _sweep(1900, 200, 0.38, 2.3, 0.55, "square")),
                         (0.0, _noise(0.42, 0.55, 3, seed=9)),
                         (0.05, _sweep(2500, 1700, 0.14, 3.0, 0.35, "square"))]), 1.0)

    # Boss: a low creaking warning right before a door-frame activates
    _add("telegraph", _mix([(0.0, _sweep(160, 240, 0.4, 2.0, 0.4, "square")),
                            (0.0, _noise(0.4, 0.12, 5, seed=11))]), 0.6)
    # Boss: a hard slam the instant the figure steps out and dashes
    _add("manifest", _mix([(0.0, _sweep(90, 40, 0.18, 5, 0.8)),
                           (0.0, _noise(0.12, 0.5, 8, seed=12))]), 0.9)
    # Boss: a low, wavering call as something is summoned in
    _add("summon", _mix([(0.0, _sweep(220, 110, 0.5, 2.2, 0.45)),
                         (0.08, _sweep(330, 140, 0.4, 2.5, 0.3, "square")),
                         (0.0, _noise(0.3, 0.1, 5, seed=13))]), 0.7)
    # Boss defeated: a bright rising chime over a burst of static clearing
    _add("defeat", _mix([(0.0, _bell(523, 0.7, 0.4, 3.0)), (0.10, _bell(659, 0.7, 0.4, 3.0)),
                         (0.20, _bell(784, 0.9, 0.45, 2.6)), (0.30, _bell(1047, 1.2, 0.5, 2.2)),
                         (0.0, _noise(0.35, 0.3, 6, seed=14))]), 1.0)


# ---------------------------------------------------------------
# The music: one seamless looping drone per chapter, getting creepier
# ---------------------------------------------------------------
#                     ch1    ch2    ch3    ch4    ch5
_ROOTS = [110.0, 98.0, 82.4, 73.4, 65.4]   # the main note gets LOWER
_INTERVALS = [7, 3, 6, 6, 1]                # 2nd note: fifth(calm) -> minor 3rd -> tritone -> minor 2nd (clashing!)
_HEARTBEATS = [0, 0, 4, 6, 8]               # heartbeat thumps per loop (none at first, then faster)
_HISS = [0.0, 0.01, 0.02, 0.035, 0.05]      # how much whispery static


def _snap(freq):
    """Nudge a pitch so it fits a whole number of times into the loop.
    Without this, you'd hear a click every time the loop restarts."""
    return round(freq * MUSIC_LOOP_SECONDS) / MUSIC_LOOP_SECONDS


def _build_music(level):
    root = _snap(_ROOTS[level])
    second = _snap(root * 2 ** (_INTERVALS[level] / 12))
    n = int(SR * MUSIC_LOOP_SECONDS)
    rng = random.Random(level)
    hiss = _HISS[level]
    out = []
    for i in range(n):
        t = i / SR
        swell = 0.75 + 0.25 * math.sin(TAU * t * 2 / MUSIC_LOOP_SECONDS)  # slow breathing
        s = 0.5 * math.sin(TAU * root * t) + 0.15 * math.sin(TAU * root * 2 * t)
        s += 0.3 * math.sin(TAU * second * t)
        s = s * swell + rng.uniform(-1, 1) * hiss
        out.append(s * 0.6)

    # Heartbeat: "lub-dub" thumps, wrapping around the end so the loop stays seamless
    beats = _HEARTBEATS[level]
    for k in range(beats):
        start = int(k * n / beats)
        for offset, strength in ((0.0, 0.9), (0.18, 0.55)):
            thump = _sweep(70, 45, 0.25, 12, strength)
            begin = start + int(offset * SR)
            for j, v in enumerate(thump):
                out[(begin + j) % n] += v * 0.7

    data = array.array("h", [int(max(-1.0, min(1.0, s)) * 32767 * 0.8) for s in out])
    return pygame.mixer.Sound(buffer=data.tobytes())


# ---------------------------------------------------------------
# The public functions
# ---------------------------------------------------------------
def init():
    """Call once, right after pygame.init(). Safe if there's no audio device."""
    global _ready, _music_chan
    try:
        pygame.mixer.quit()
        pygame.mixer.init(frequency=SR, size=-16, channels=1, buffer=512)
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)          # channel 0 is kept just for music
        _music_chan = pygame.mixer.Channel(0)
        _build_sfx()
        for level in range(5):
            _music[level] = _build_music(level)
        _ready = True
        set_volume(_master)
    except pygame.error as e:
        print("Sound is off (no audio device?):", e)
        _ready = False


def set_volume(v):
    """v is 0.0 to 1.0. If your Settings volume is 0-100, pass volume / 100."""
    global _master
    _master = max(0.0, min(1.0, v))
    if not _ready:
        return
    for sound, base in _sfx.values():
        sound.set_volume(_master * base)
    for sound in _music.values():
        sound.set_volume(_master * MUSIC_VOL)


def play(name):
    """Play a sound effect by name, e.g. sound.play("jump")."""
    if _ready and name in _sfx:
        _sfx[name][0].play()


def play_music(level):
    """level 0-4 = chapter number. Calling it again with the same level does nothing."""
    global _current_level
    if not _ready:
        return
    level = max(0, min(4, int(level)))
    if level == _current_level:
        return
    _current_level = level
    _music_chan.play(_music[level], loops=-1, fade_ms=800)


def stop_music(fade_ms=600):
    global _current_level
    if not _ready:
        return
    _music_chan.fadeout(fade_ms)
    _current_level = None


# ---------------------------------------------------------------
# Run this file by itself to LISTEN to everything:  python3 sound.py
# ---------------------------------------------------------------
if __name__ == "__main__":
    import time
    pygame.init()
    init()
    print("Sound effects:")
    for name in _sfx:
        print("  ", name)
        play(name)
        time.sleep(2.5 if name in ("chapter_complete", "game_over") else 1.2)
    print("Music, calm to creepy:")
    for lvl in range(5):
        print("   chapter", lvl + 1)
        play_music(lvl)
        time.sleep(6)
    stop_music()
    time.sleep(1)