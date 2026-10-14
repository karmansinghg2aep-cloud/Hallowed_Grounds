"""
analog.py - the old-VHS look for Hallowed Grounds.

NORMAL rooms look clean: a very light scanline texture, dark corners, and the
REC label + timecode. The heavy glitching (static, sliding picture strips) is
RESERVED for mini-boss and boss fights.

Put this file next to manor.py. The functions you'll use:

    analog.init(screen)                 - once, right after pygame.display.set_mode(...)
    analog.set_level(n)                 - n = chapter number (makes boss fights a bit nastier later on)
    analog.set_boss(b)                  - 0 = normal room, 1 = mini boss, 2 = boss
    analog.draw(screen, tape_number)    - EVERY frame, LAST, right before pygame.display.flip()
    analog.static_burst(screen, clock)  - a short blast of TV static (for screen transitions)

In rooms.json, add  "boss": "mini"  or  "boss": "boss"  to a room to turn the glitch on for it.

Try it without the game:   python3 analog.py
"""
import random
import pygame

# --- Easy switches you can change ---------------------------------
NORMAL_SCANLINES = True      # False = a completely clean picture in normal rooms
# ------------------------------------------------------------------

_ready = False
_size = (800, 500)
_scan_light = None    # faint scanlines for normal rooms
_scan_full = None     # strong scanlines for boss fights
_vignette = None
_noise_frames = []
_font = None
_frame = 0            # counts frames, used for the timecode and blinking dot
_level = 0            # chapter number
_boss = 0             # 0 = normal, 1 = mini boss, 2 = boss
_glitch_left = 0      # frames of glitch still to show
_glitch = None        # (y, height, x_shift) of the current glitch band

# How bad the tape gets DURING boss fights:      (index = boss level 1 or 2)
_BOSS_GLITCH_CHANCE = {1: 0.010, 2: 0.030}   # chance per frame that a glitch starts
_BOSS_STATIC_ALPHA = {1: 12, 2: 28}          # constant static (0-255)


def _make_scanlines(w, h, alpha):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(s, (0, 0, 0, alpha), (0, y), (w, y))
    return s


def _make_vignette(w, h):
    """Dark corners, like a curved old TV. Built small, then stretched (fast)."""
    sw, sh = 100, max(1, int(100 * h / w))
    s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    cx, cy = sw / 2, sh / 2
    for y in range(sh):
        for x in range(sw):
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            d = (dx * dx + dy * dy) ** 0.5           # 0 in the middle, ~1.4 in the corners
            a = max(0.0, d - 0.6) / 0.8              # only darken the outer part
            s.set_at((x, y), (0, 0, 0, min(200, int(a * a * 255))))
    return pygame.transform.smoothscale(s, (w, h))


def _make_noise_frame(w, h):
    """One frame of black-and-white TV static, made small then stretched."""
    sw, sh = w // 4, h // 4
    grey = random.randbytes(sw * sh)
    rgb = bytearray(sw * sh * 3)
    rgb[0::3] = grey
    rgb[1::3] = grey
    rgb[2::3] = grey
    small = pygame.image.frombuffer(bytes(rgb), (sw, sh), "RGB")
    return pygame.transform.scale(small, (w, h)).convert()


def init(screen):
    """Call once, right after pygame.display.set_mode()."""
    global _ready, _size, _scan_light, _scan_full, _vignette, _noise_frames, _font
    _size = screen.get_size()
    w, h = _size
    _scan_light = _make_scanlines(w, h, 22)
    _scan_full = _make_scanlines(w, h, 60)
    _vignette = _make_vignette(w, h)
    _noise_frames = [_make_noise_frame(w, h) for _ in range(8)]
    _font = pygame.font.Font(None, 24)
    _ready = True


def set_level(level):
    """Chapter number 0-4. Later chapters make boss glitching slightly nastier."""
    global _level
    _level = max(0, min(4, int(level)))


def set_boss(boss):
    """0 = normal room, 1 = mini boss, 2 = boss. Also accepts "mini", "boss" or True."""
    global _boss, _glitch_left
    if boss == "mini":
        boss = 1
    elif boss is True or boss == "boss":
        boss = 2
    _boss = boss if boss in (1, 2) else 0
    _glitch_left = 0


def reset_timecode():
    global _frame
    _frame = 0


def _timecode():
    if _boss and _glitch_left > 0:
        return "--:--:--"                   # the timecode breaks during a glitch
    seconds = _frame // 60
    return "%02d:%02d:%02d" % (seconds // 3600, (seconds // 60) % 60, seconds % 60)


def _text(screen, msg, x, y, color=(235, 235, 235)):
    screen.blit(_font.render(msg, True, (120, 0, 0)), (x + 1, y + 1))   # red-ish edge
    screen.blit(_font.render(msg, True, color), (x, y))


def draw(screen, tape_number=1):
    """Call every frame, LAST, right before pygame.display.flip()."""
    global _frame, _glitch_left, _glitch
    if not _ready:
        return
    _frame += 1
    w, h = _size

    if _boss:
        # 1. Tracking glitch: a horizontal strip of the picture slides sideways
        chance = _BOSS_GLITCH_CHANCE[_boss] * (1 + 0.25 * _level)
        if _glitch_left == 0 and random.random() < chance:
            _glitch_left = random.randint(4, 9)
            _glitch = (random.randint(0, h - 40), random.randint(8, 34),
                       random.choice((-1, 1)) * random.randint(6, 28))
        if _glitch_left > 0:
            y, bh, dx = _glitch
            strip = screen.subsurface((0, y, w, bh)).copy()
            screen.blit(strip, (dx, y))
            _glitch_left -= 1

        # 2. Constant static
        noise = random.choice(_noise_frames)
        noise.set_alpha(_BOSS_STATIC_ALPHA[_boss])
        screen.blit(noise, (0, 0))

        # 3. Strong scanlines and extra-dark corners
        screen.blit(_scan_full, (0, 0))
        screen.blit(_vignette, (0, 0))
    elif NORMAL_SCANLINES:
        screen.blit(_scan_light, (0, 0))

    # Dark corners (always)
    screen.blit(_vignette, (0, 0))

    # Tape label, blinking REC dot, and timecode (always)
    _text(screen, "TAPE %02d" % tape_number, w - 120, 12)
    if (_frame // 30) % 2 == 0:
        pygame.draw.circle(screen, (220, 30, 30), (w - 196, 21), 6)
        _text(screen, "REC", w - 185, 12, (255, 90, 90))
    _text(screen, _timecode(), w - 120, 34)


def static_burst(screen, clock, frames=30, reveal=True):
    """Blocks for a moment and shows TV static (used between screens).
    reveal=True : static fades away, showing the screen
    reveal=False: static fades IN and covers the screen"""
    if not _ready:
        return
    background = screen.copy()
    for i in range(frames):
        pygame.event.pump()
        p = i / max(1, frames - 1)
        alpha = int(255 * ((1 - p) if reveal else p))
        screen.blit(background, (0, 0))
        noise = random.choice(_noise_frames)
        noise.set_alpha(alpha)
        screen.blit(noise, (0, 0))
        pygame.display.flip()
        clock.tick(60)


# ---------------------------------------------------------------
# Run this file by itself to SEE the effect:  python3 analog.py
# Left/right arrows = chapter level.  B = cycle normal / mini boss / boss.  Esc quits.
# ---------------------------------------------------------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 500))
    clock = pygame.time.Clock()
    init(screen)
    level, boss = 0, 0
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RIGHT:
                level = min(4, level + 1)
                set_level(level)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_LEFT:
                level = max(0, level - 1)
                set_level(level)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_b:
                boss = (boss + 1) % 3
                set_boss(boss)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
                static_burst(screen, clock)
        screen.fill((26, 20, 32))
        pygame.draw.rect(screen, (55, 48, 60), (0, 460, 800, 40))
        pygame.draw.rect(screen, (140, 60, 60), (300, 426, 34, 34))
        pygame.draw.rect(screen, (230, 230, 230), (40, 420, 28, 40))
        draw(screen, level + 1)
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()