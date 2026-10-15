"""
HALLOWED GROUNDS - visuals.py
The ART of the game: animated backgrounds, characters and effects.

IMPORTANT DESIGN RULE (added after a Mac showed a fully black screen):
Every picture in this file is drawn STRAIGHT ONTO the room's picture, using only the plain
drawing calls (pygame.draw.rect, circle, line, polygon...). Nothing here ever builds a
separate small picture and pastes it in. That "build a separate picture, then paste it"
style is exactly what broke on that Mac, so this file avoids it completely, even though a
separate-picture is sometimes the more natural way to code an effect.

When your friend's pixel-art sprites are ready, swap them in HERE without touching manor.py.

Put this file next to manor.py. What is inside:
    Particles          dust, sparkles, embers, debris
    Background         an animated background for each chapter style
    PlayerSprite        the player: idle breathing, walk cycle, squash and stretch, blinking
    draw_monster        all four monsters, animated
    draw_platform, draw_door, draw_key, draw_tape, draw_projectile
    menu_background, fade

Try a picture show without the game:   python3 visuals.py
"""
import math
import random
import pygame

W, H = 800, 500
BEAM_SAFE_LANE = 128


# ------------------------------------------------------------------
# small helpers
# ------------------------------------------------------------------
def mix(c1, c2, t):
    """Blend two colors. t=0 gives c1, t=1 gives c2."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def add_glow(surface, x, y, radius, color, steps=5):
    """A soft-looking light, made of a few solid circles getting brighter toward the middle.
    Drawn straight onto the picture (no separate picture involved)."""
    x, y, radius = int(x), int(y), int(radius)
    if radius <= 0:
        return
    for i in range(steps, 0, -1):
        r = radius * i // steps
        if r <= 0:
            continue
        t = 1 - i / steps
        pygame.draw.circle(surface, mix((0, 0, 0), color, 0.35 + 0.65 * t), (x, y), r)


def flame(surface, x, y, frame, seed=0.0, scale=1.0, color=(255, 170, 60)):
    """A flickering flame with a warm glow. (x, y) is the base of the flame."""
    f = math.sin(frame * 0.31 + seed) * 3 + math.sin(frame * 0.17 + seed * 2) * 2
    h = (26 + f) * scale
    w = 15 * scale
    add_glow(surface, x, y - h * 0.5, int(30 * scale + f * 2), (70, 46, 18))
    pygame.draw.ellipse(surface, color, (x - w / 2, y - h, w, h))
    pygame.draw.ellipse(surface, (255, 235, 150), (x - w / 4, y - h * 0.7, w / 2, h * 0.6))


def h_gradient(surface, top, bottom, y0, y1, bands=24):
    """A vertical gradient made of solid horizontal bands (direct rectangles, no alpha)."""
    step = max(1, (y1 - y0) // bands)
    y = y0
    while y < y1:
        t = (y - y0) / max(1, y1 - y0 - 1)
        pygame.draw.rect(surface, mix(top, bottom, t), (0, y, W, step + 1))
        y += step


# ------------------------------------------------------------------
# particles (already direct draws, nothing to change)
# ------------------------------------------------------------------
class Particles:
    """Little bits that fly around and fade: dust, sparkles, embers, debris."""
    MAX = 400

    def __init__(self):
        self.items = []

    def emit(self, x, y, vx=0.0, vy=0.0, life=30, size=2.0, color=(200, 200, 200), gravity=0.0, shrink=True):
        if len(self.items) < self.MAX:
            self.items.append([x, y, vx, vy, life, life, size, color, gravity, shrink])

    def burst(self, x, y, n, color, speed=2.0, life=24, size=3.0, gravity=0.08, up=0.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.3, 1.0) * speed
            self.emit(x, y, math.cos(a) * s, math.sin(a) * s - up, life + random.randint(-6, 6), size, color, gravity)

    def update(self):
        for p in self.items:
            p[0] += p[2]
            p[1] += p[3]
            p[3] += p[8]
            p[4] -= 1
        self.items = [p for p in self.items if p[4] > 0]

    def draw(self, surface):
        for x, y, vx, vy, life, total, size, color, g, shrink in self.items:
            t = life / total
            s = size * t if shrink else size
            if s < 0.6:
                continue
            pygame.draw.circle(surface, mix((0, 0, 0), color, min(1.0, t * 1.4)), (int(x), int(y)), max(1, int(s)))


# ------------------------------------------------------------------
# backgrounds
# ------------------------------------------------------------------
class Background:
    """
    An animated background. __init__ only picks positions (a list of numbers) for things like
    stars, windows and bricks. draw() is called every frame and paints all of it straight onto
    the room, fresh each time -- nothing is pre-painted onto a separate picture.
    """

    def __init__(self, chapter, chap_no, room_index, room_pos, chapter_len):
        self.chapter = chapter
        self.chap_no = chap_no
        self.room_index = room_index
        self.style = chapter.get("style", "")
        self.sky = tuple(chapter.get("sky", (20, 20, 30)))
        self.accent = tuple(chapter.get("accent", (120, 120, 120)))
        self.progress = room_pos / max(1, chapter_len - 1)          # 0 at the start of a tape, 1 at its end
        self.rng = random.Random(room_index * 7919 + 13)
        self.motes = [[self.rng.uniform(0, W), self.rng.uniform(0, 450), self.rng.uniform(0.1, 0.5),
                       self.rng.uniform(0, 6.28), 1] for _ in range(20)]
        getattr(self, "_layout_" + self.style, self._layout_plain)()

    # ---------- shared ----------
    def _layout_plain(self):
        pass

    def _mote_color(self):
        return mix(self.sky, (255, 255, 255), 0.35)

    # ---------- Tape 1: the west wing (moonlit) ----------
    def _layout_moonlit(self):
        rng = self.rng
        self.stars = [(rng.randint(0, W), rng.randint(95, 205), rng.uniform(0, 6.28)) for _ in range(24)]
        self.tall_windows = [74, 354, 634]
        self.portraits = [(246, 126), (522, 114)]
        self.cameras = [(744, 38)]

    def _draw_moonlit(self, surface, frame):
        # Interior of the mansion; wooded grounds appear only through the windows.
        wall = mix(self.sky, (82, 68, 68), 0.26)
        surface.fill(wall)
        h_gradient(surface, mix(wall, (0, 0, 0), 0.12), mix(wall, (22, 17, 20), 0.42), 0, 318)
        pygame.draw.rect(surface, (34, 28, 30), (0, 322, W, 138))
        pygame.draw.line(surface, (102, 76, 65), (0, 318), (W, 318), 4)
        pygame.draw.line(surface, (18, 16, 20), (0, 329), (W, 329), 2)
        for x in range(18, W, 54):
            pygame.draw.line(surface, (48, 37, 38), (x, 338), (x, 458), 2)
            pygame.draw.line(surface, (25, 22, 25), (x + 4, 338), (x + 4, 458), 1)
        for i, wx in enumerate(self.tall_windows):
            outer = pygame.Rect(wx, 86, 88, 190)
            inner = pygame.Rect(wx + 8, 100, 72, 160)
            pygame.draw.rect(surface, (10, 16, 25), inner)
            for yy in range(inner.y, inner.bottom, 12):
                t = (yy - inner.y) / inner.h
                pygame.draw.rect(surface, mix((13, 22, 37), (22, 31, 39), t),
                                 (inner.x, yy, inner.w, min(12, inner.bottom - yy)))
            for tree_x in range(inner.x + 9, inner.right - 7, 14):
                height = 42 + ((tree_x * 7 + i * 13) % 46)
                base_y = inner.bottom - 4
                tree_col = (20, 29, 39) if tree_x % 2 else (12, 19, 27)
                pygame.draw.polygon(surface, tree_col, [(tree_x - 8, base_y), (tree_x, base_y - height), (tree_x + 8, base_y)])
                if tree_x % 3 == 0:
                    pygame.draw.polygon(surface, mix(tree_col, (0, 0, 0), 0.22),
                                        [(tree_x - 12, base_y), (tree_x, base_y - height * 0.66), (tree_x + 12, base_y)])
            # Rain is visible only against the dark glass.
            for drop in range(9):
                rx = inner.x + 4 + ((drop * 19 + frame * (1 + drop % 2)) % (inner.w - 8))
                ry = inner.y + ((drop * 31 + frame * (2 + drop % 3)) % (inner.h - 12))
                pygame.draw.line(surface, (49, 65, 78), (rx, ry), (rx - 1, ry + 6), 1)
            if i == 2:
                mx, my = inner.right - 18, inner.y + 31
                pygame.draw.circle(surface, (139, 145, 151), (mx, my), 12)
                pygame.draw.circle(surface, (19, 28, 39), (mx + 7, my - 5), 11)
            for x, y, ph in self.stars:
                if inner.x + 2 < x < inner.right - 2 and inner.y + 2 < y < inner.y + 55:
                    c = 116 + int(48 * math.sin(frame * 0.035 + ph))
                    surface.fill((c, c, c), (x, y, 1, 1))
            arch = [(outer.x, outer.y + 24), (outer.x + 12, outer.y + 6),
                    (outer.centerx, outer.y - 5), (outer.right - 12, outer.y + 6),
                    (outer.right, outer.y + 24), (outer.right, outer.bottom), (outer.x, outer.bottom)]
            pygame.draw.polygon(surface, (48, 34, 31), arch, 7)
            pygame.draw.line(surface, (25, 22, 24), (outer.centerx, outer.y + 8), (outer.centerx, outer.bottom), 3)
            pygame.draw.line(surface, (25, 22, 24), (inner.x, inner.y + 78), (inner.right, inner.y + 78), 3)
            pygame.draw.line(surface, (105, 77, 61), (outer.x - 5, outer.bottom), (outer.right + 5, outer.bottom), 5)
        # Small sconces cast local warmth rather than broad grey cones.
        for i, lx in enumerate((213, 565)):
            ly = 221
            flicker = (frame // 6 + i * 9) % 53 not in (0, 1, 2, 3)
            if flicker:
                add_glow(surface, lx, ly, 16, (48, 31, 18), steps=3)
            pygame.draw.rect(surface, (34, 29, 30), (lx - 10, ly - 14, 20, 31), border_radius=3)
            pygame.draw.rect(surface, (91, 65, 48), (lx - 7, ly - 11, 14, 23), 1, border_radius=2)
            pygame.draw.line(surface, (112, 83, 59), (lx, ly + 12), (lx, ly + 20), 2)
            if flicker:
                pygame.draw.ellipse(surface, (152, 114, 70), (lx - 3, ly - 8, 6, 11))
            else:
                pygame.draw.ellipse(surface, (43, 36, 33), (lx - 3, ly - 8, 6, 11))
        for fx, fy in self.portraits:
            frame_rect = pygame.Rect(fx, fy, 42, 64)
            pygame.draw.rect(surface, (34, 25, 25), frame_rect.inflate(6, 6))
            pygame.draw.rect(surface, (112, 80, 58), frame_rect, 3)
            pygame.draw.rect(surface, (27, 24, 28), frame_rect.inflate(-8, -8))
            pygame.draw.ellipse(surface, (19, 18, 22), (fx + 13, fy + 11, 16, 22))
            pygame.draw.polygon(surface, (19, 18, 22), [(fx + 9, fy + 57), (fx + 12, fy + 36), (fx + 30, fy + 36), (fx + 35, fy + 57)])
            if (frame // 130 + fx) % 9 == 0:
                pygame.draw.line(surface, (111, 49, 44), (fx + 17, fy + 21), (fx + 24, fy + 21), 1)
            pygame.draw.line(surface, (75, 63, 58), (fx + 4, fy + 9), (fx + 10, fy + 4), 1)
        # One small security camera is tucked into the ceiling trim.
        for i, (cx, cy) in enumerate(self.cameras):
            pygame.draw.rect(surface, (39, 35, 37), (cx - 10, cy - 3, 20, 9), border_radius=3)
            pygame.draw.polygon(surface, (22, 20, 23), [(cx - 4, cy + 4), (cx + 8, cy + 4), (cx + 11, cy + 12)])
            blink = (frame // 24 + i) % 4 == 0
            pygame.draw.circle(surface, (173, 37, 38) if blink else (49, 25, 27), (cx + 7, cy + 2), 2)

    # ---------- Tape 2: the old hallways (cobweb) ----------
    def _layout_cobweb(self):
        rng = self.rng
        self.stripe_x = list(range(0, W + 20, 30))
        self.doors = [rng.randint(60, 140), rng.randint(360, 440), rng.randint(600, 690)]
        self.pictures = [(rng.randint(30, 720), rng.randint(60, 170), rng.randint(-4, 4)) for _ in range(3)]
        self.torches = [(150, 250), (650, 250)]
        self.spider = [rng.randint(120, 680), 0.0, 1]
        self.cameras = [rng.randint(35, 765) for _ in range(3)]

    def _draw_cobweb(self, surface, frame):
        surface.fill(mix(self.sky, self.accent, 0.10))
        for x in self.stripe_x:
            pygame.draw.rect(surface, mix(self.sky, self.accent, 0.24), (x, 0, 14, 370))
        pygame.draw.rect(surface, mix(self.sky, (0, 0, 0), 0.30), (0, 370, W, 90))
        for x in range(0, W, 64):
            pygame.draw.rect(surface, mix(self.sky, self.accent, 0.20), (x + 6, 380, 52, 66), 1)
        pygame.draw.rect(surface, mix(self.sky, self.accent, 0.35), (0, 366, W, 5))
        for dx in self.doors:
            door = pygame.Rect(dx, 235, 70, 135)
            pygame.draw.rect(surface, mix(self.sky, (0, 0, 0), 0.5), door.inflate(10, 6))
            pygame.draw.rect(surface, mix(self.sky, (0, 0, 0), 0.35), door)
            pygame.draw.rect(surface, mix(self.sky, self.accent, 0.3), door.inflate(-22, -30), 1)
            pygame.draw.circle(surface, (110, 95, 60), (door.right - 10, door.centery), 3)
            pygame.draw.rect(surface, (74, 67, 65), (dx + 22, 217, 28, 12))
            pygame.draw.line(surface, (165, 150, 128), (dx + 25, 220), (dx + 46, 220), 1)
            pygame.draw.line(surface, (165, 150, 128), (dx + 25, 225), (dx + 42, 225), 1)
        for fx, fy, tilt in self.pictures:
            pts = [(fx, fy + tilt), (fx + 40, fy), (fx + 40, fy + 50), (fx, fy + 50 + tilt)]
            pygame.draw.polygon(surface, (70, 52, 42), pts)
            pygame.draw.polygon(surface, (14, 12, 16), [(fx + 4, fy + 4 + tilt), (fx + 36, fy + 4), (fx + 36, fy + 46), (fx + 4, fy + 46 + tilt)])
        web = mix(self.sky, (200, 200, 215), 0.30)
        for corner_x, sign in ((0, 1), (W, -1)):
            angles = range(0, 91, 18)
            for radius in (40, 80, 120, 170):
                pts = [(corner_x + sign * radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a))) for a in angles]
                pygame.draw.lines(surface, web, False, pts, 1)
            for a in angles:
                pygame.draw.line(surface, web, (corner_x, 0), (corner_x + sign * 170 * math.cos(math.radians(a)), 170 * math.sin(math.radians(a))), 1)
        for sx, sy in self.torches:
            pygame.draw.rect(surface, (28, 27, 32), (sx - 15, sy - 8, 30, 34), border_radius=4)
            pygame.draw.rect(surface, (92, 83, 76), (sx - 12, sy - 5, 24, 28), 2, border_radius=3)
            on = (frame // 5 + sx) % 47 > 4
            pygame.draw.rect(surface, (154, 136, 111) if on else (38, 35, 38), (sx - 7, sy, 14, 18))
        # A broken fluorescent panel and ceiling-mounted cameras replace the fantasy chandelier.
        cx = 400 + math.sin(frame * 0.02) * 10
        pygame.draw.rect(surface, (48, 46, 52), (cx - 80, 22, 160, 17), border_radius=3)
        lamp_col = (149, 158, 151) if frame % 93 > 3 else (30, 33, 34)
        pygame.draw.rect(surface, lamp_col, (cx - 72, 26, 144, 5))
        pygame.draw.rect(surface, (80, 76, 75), (cx - 80, 22, 160, 17), 2, border_radius=3)
        for cam_x in self.cameras:
            pygame.draw.line(surface, (38, 36, 41), (cam_x, 0), (cam_x, 26), 2)
            pygame.draw.rect(surface, (50, 48, 52), (cam_x - 9, 22, 18, 10), border_radius=3)
            pygame.draw.circle(surface, (185, 35, 36) if frame % 36 < 19 else (44, 24, 27), (cam_x, 30), 2)
        sp = self.spider
        sp[1] += 0.35 * sp[2]
        if sp[1] > 130:
            sp[2] = -1
        if sp[1] < 2:
            sp[2] = 1
        pygame.draw.line(surface, (110, 110, 120), (sp[0], 0), (sp[0], sp[1]), 1)
        pygame.draw.circle(surface, (20, 18, 22), (int(sp[0]), int(sp[1])), 3)

    # ---------- Tape 3: the crypts (torchlit) ----------
    def _layout_torchlit(self):
        rng = self.rng
        self.bricks = []
        for row, y in enumerate(range(-6, H, 26)):
            off = 28 if row % 2 else 0
            for x in range(-off, W + 60, 56):
                self.bricks.append((x, y, mix(self.sky, self.accent, rng.uniform(0.02, 0.20))))
        self.arches = [150, 420, 690]
        self.chains = [(rng.randint(60, 140), rng.randint(80, 190)), (rng.randint(270, 340), rng.randint(80, 190)),
                       (rng.randint(500, 560), rng.randint(80, 190)), (rng.randint(700, 760), rng.randint(80, 190))]
        self.torches = [(tx, 175) for tx in self.chapter.get("torch_x", [120, 680])]
        self.wall_monitors = [(82, 245), (666, 260)]

    def _draw_torchlit(self, surface, frame):
        surface.fill(mix(self.sky, (0, 0, 0), 0.10))
        for x, y, c in self.bricks:
            pygame.draw.rect(surface, c, (x + 1, y + 1, 54, 24))
        for ax in self.arches:
            pygame.draw.rect(surface, mix(self.sky, (0, 0, 0), 0.5), (ax - 54, 130, 108, 330))
            pygame.draw.ellipse(surface, mix(self.sky, (0, 0, 0), 0.5), (ax - 54, 76, 108, 108))
        for cx, length in self.chains:
            for y in range(0, length, 12):
                pygame.draw.ellipse(surface, (90, 88, 96), (cx - 3, y, 6, 11), 2)
        for tx, ty in self.torches:
            pygame.draw.rect(surface, (45, 41, 40), (tx - 14, ty - 8, 28, 42), border_radius=4)
            pygame.draw.rect(surface, (106, 90, 73), (tx - 10, ty - 3, 20, 31), 2, border_radius=3)
            light_on = (frame // 4 + tx) % 39 > 3
            pygame.draw.rect(surface, (172, 143, 102) if light_on else (40, 35, 33), (tx - 5, ty + 2, 10, 21))
            if frame % 9 == 0:
                self.motes.append([tx + random.uniform(-4, 4), ty - 20, random.uniform(0.6, 1.2), random.uniform(0, 6), 9])
        for mx, my in self.wall_monitors:
            pygame.draw.rect(surface, (35, 34, 39), (mx - 29, my - 21, 58, 42), border_radius=3)
            pygame.draw.rect(surface, (8, 17, 18), (mx - 24, my - 16, 48, 32))
            if frame % 120 < 96:
                pygame.draw.lines(surface, (77, 114, 96), False, [(mx - 20, my + 8), (mx - 8, my - 9), (mx + 2, my + 6), (mx + 12, my - 5), (mx + 20, my + 1)], 1)
            pygame.draw.circle(surface, (180, 35, 36) if frame % 42 < 22 else (45, 24, 27), (mx + 23, my - 15), 2)
        drift = mix(self.sky, (150, 130, 150), 0.10)
        for i in range(3):
            mx = (frame * 0.3 + i * 300) % (W + 300) - 150
            pygame.draw.ellipse(surface, drift, (mx, 350 + i * 30, 220, 40))

    # ---------- Tape 4: the buried wing (roots) ----------
    def _layout_roots(self):
        rng = self.rng
        self.earth_rows = list(range(60, 460, 46))
        self.specks = [(rng.randint(0, W), rng.randint(40, 450)) for _ in range(50)]
        self.stalactites = [(x, rng.randint(30, 90)) for x in range(0, W + 20, rng.randint(52, 80))]
        self.pillars = [(rng.randint(40, 740), rng.randint(90, 200)) for _ in range(3)]
        self.roots = [(25 + i * 54, 70 + (i * 37) % 120, i) for i in range(15)]
        self.orbs = [(rng.randint(40, 760), rng.randint(200, 420), rng.uniform(0, 6.28)) for _ in range(7)]
        self.cameras = [(x, rng.randint(78, 170), rng.choice((-1, 1))) for x in (85, 270, 525, 720)]

    def _draw_roots(self, surface, frame):
        surface.fill(mix(self.sky, self.accent, 0.15))
        for y in self.earth_rows:
            pts = [(x, y + math.sin(x * 0.02 + y) * 8) for x in range(0, W + 60, 20)]
            pygame.draw.lines(surface, mix(self.sky, self.accent, 0.25), False, pts, 2)
        for x, y in self.specks:
            pygame.draw.circle(surface, mix(self.sky, self.accent, 0.3), (x, y), 2)
        for x, length in self.stalactites:
            pygame.draw.polygon(surface, mix(self.sky, self.accent, 0.28), [(x - 15, 0), (x + 15, 0), (x, length)])
        for px, ph in self.pillars:
            pygame.draw.rect(surface, mix(self.sky, (0, 0, 0), 0.4), (px, 460 - ph, 34, ph))
            pygame.draw.polygon(surface, mix(self.sky, (0, 0, 0), 0.4), [(px, 460 - ph), (px + 34, 460 - ph), (px + 26, 460 - ph - 10), (px + 8, 460 - ph - 5)])
        col = mix(self.sky, self.accent, 0.55)
        for x, length, i in self.roots:
            pts = []
            for k in range(7):
                sway = math.sin(frame * 0.02 + i + k * 0.5) * 3 * k
                pts.append((x + sway + ((i * 13 + k * 7) % 9 - 4), k * length / 6))
            pygame.draw.lines(surface, col, False, pts, 3 if i % 2 else 2)
            bx, by = pts[4]
            pygame.draw.line(surface, col, (bx, by), (bx + 12 * (1 if i % 2 else -1), by + 14), 1)
        for x, y, ph in self.orbs:
            p = 0.5 + 0.5 * math.sin(frame * 0.03 + ph)
            add_glow(surface, x, y + math.sin(frame * 0.015 + ph) * 6, int(20 + 6 * p), (int(16 * p + 5), int(60 * p + 16), int(50 * p + 16)))
        for cx, cy, direction in self.cameras:
            pygame.draw.rect(surface, (32, 29, 28), (cx - 9, cy - 5, 18, 12), border_radius=3)
            pygame.draw.polygon(surface, (17, 16, 17), [(cx - 3, cy + 6), (cx + 3, cy + 6), (cx + 8 * direction, cy + 15)])
            pygame.draw.circle(surface, (165, 42, 35) if frame % 52 < 28 else (55, 25, 24), (cx + direction * 6, cy), 2)
        # Signal cables run through the roots as if the building grew around them.
        for i, x in enumerate((165, 398, 635)):
            sway = math.sin(frame * 0.025 + i) * 4
            pygame.draw.lines(surface, (36, 31, 28), False, [(x, 0), (x + sway, 62), (x - 12, 110), (x + 8, 168)], 5)
            pygame.draw.lines(surface, (102, 47, 37), False, [(x + 2, 0), (x + sway + 2, 62), (x - 10, 110), (x + 10, 168)], 1)
        if self.progress >= 0.7:
            monitor_line(surface, frame, self.sky, 0.35)
        if frame % 26 == 0:
            self.motes.append([random.uniform(0, W), 0, random.uniform(0.8, 1.6), 0, 9])

    # ---------- Tape 5: the reckoning (tiles) ----------
    def _layout_tiles(self):
        pass

    def _draw_tiles(self, surface, frame):
        pr = self.progress
        h_gradient(surface, mix(self.sky, (0, 0, 0), 0.15), mix(self.sky, (170, 180, 190), 0.10 + 0.22 * pr), 0, H)
        tile = mix(self.sky, (200, 208, 215), 0.05 + 0.20 * pr)
        for gx in range(0, W, 60):
            pygame.draw.line(surface, tile, (gx, 90), (gx, H))
        for gy in range(90, H, 60):
            pygame.draw.line(surface, tile, (0, gy), (W, gy))
        pygame.draw.rect(surface, mix(self.sky, (210, 218, 225), 0.12 + 0.25 * pr), (0, 90, W, 6))
        win = pygame.Rect(590, 130, 130, 170)
        pygame.draw.rect(surface, mix(self.sky, (230, 236, 240), 0.20 + 0.45 * pr), win)
        pygame.draw.rect(surface, mix(self.sky, (210, 218, 225), 0.30), win.inflate(10, 10), 3)
        pygame.draw.line(surface, mix(self.sky, (210, 218, 225), 0.30), (win.centerx, win.y), (win.centerx, win.bottom), 2)
        for k in range(6):
            x0 = 40 + k * 22
            pygame.draw.polygon(surface, mix(self.sky, (170, 180, 190), 0.18 + 0.20 * pr), [(x0, 96), (x0 + 22, 96), (x0 + 14 + (k % 2) * 6, 380), (x0 - 4, 380)])
            pygame.draw.line(surface, mix(self.sky, (0, 0, 0), 0.4), (x0 + 11, 96), (x0 + 8 + (k % 2) * 6, 380), 1)
        pygame.draw.line(surface, (150, 155, 165), (30, 94), (190, 94), 3)
        for k in range(3):
            flick = 0.55 if (frame // 5 + k * 7) % 41 == 0 else 1.0
            pygame.draw.rect(surface, (150, 155, 165), (150 + k * 220, 8, 130, 16), border_radius=3)
            add_glow(surface, 215 + k * 220, 36, 80, (int(40 * flick + 18 * pr), int(46 * flick + 18 * pr), int(52 * flick + 20 * pr)))
        # One-way glass looks into the room the subject is trying to remember.
        glass = pygame.Rect(520, 145, 190, 150)
        pygame.draw.rect(surface, mix(self.sky, (115, 126, 137), 0.22), glass)
        pygame.draw.rect(surface, (10, 12, 16), glass, 4)
        pygame.draw.line(surface, (63, 72, 80), (glass.centerx, glass.y), (glass.centerx, glass.bottom), 2)
        bed_y = 258 + int(math.sin(frame * 0.018) * 1)
        pygame.draw.rect(surface, (45, 48, 53), (565, bed_y, 105, 10))
        pygame.draw.rect(surface, (95, 99, 103), (572, bed_y - 12, 32, 12), border_radius=4)
        pygame.draw.line(surface, (37, 39, 44), (575, bed_y + 10), (575, bed_y + 27), 3)
        pygame.draw.line(surface, (37, 39, 44), (659, bed_y + 10), (659, bed_y + 27), 3)
        # A camera watches the bed; its feed has a red tally light.
        pygame.draw.line(surface, (25, 27, 32), (748, 0), (721, 82), 3)
        pygame.draw.rect(surface, (45, 47, 52), (706, 78, 30, 13), border_radius=3)
        pygame.draw.circle(surface, (190, 32, 34) if frame % 36 < 20 else (48, 25, 28), (710, 84), 2)
        # A face resolves on this tile for one frame, then the wall loses it again.
        if (frame // 110) % 7 == 3:
            fx, fy = 278, 208
            pygame.draw.ellipse(surface, (53, 55, 62), (fx - 13, fy - 18, 26, 38))
            pygame.draw.line(surface, (150, 47, 45), (fx - 5, fy - 4), (fx - 2, fy - 4), 2)
            pygame.draw.line(surface, (150, 47, 45), (fx + 3, fy - 4), (fx + 6, fy - 4), 2)
        edge = int(clamp(pr * 60, 0, 60))
        if edge > 0:
            pygame.draw.rect(surface, mix(self.sky, (230, 235, 240), 0.5), (0, 0, edge, H))
            pygame.draw.rect(surface, mix(self.sky, (230, 235, 240), 0.5), (W - edge, 0, edge, H))
        monitor_line(surface, frame, self.sky, 0.35 + 0.5 * pr)

    # ---------- drawing ----------
    def draw(self, surface, frame, player_x=400, flicker_timer=0):
        getattr(self, "_draw_" + self.style, lambda *a: None)(surface, frame)
        self._draw_chandelier(surface, frame, flicker_timer)
        self._draw_recurring_portrait(surface, frame)
        self._draw_tape_wear(surface, frame)
        for m in self.motes:
            if m[4] == 9:
                m[1] += m[2] * (-1.2 if self.style == "torchlit" else 1.5)
            else:
                m[1] += math.sin(frame * 0.01 + m[3]) * 0.15 + 0.05
            m[0] += math.sin(frame * 0.02 + m[3]) * 0.3
        self.motes = [m for m in self.motes if -20 < m[1] < H + 20 and -20 < m[0] < W + 20]
        while sum(1 for m in self.motes if m[4] != 9) < 20:
            self.motes.append([random.uniform(0, W), random.uniform(0, 450), random.uniform(0.1, 0.5), random.uniform(0, 6.28), 1])
        dust = self._mote_color()
        for x, y, sp, ph, kind in self.motes:
            if kind == 9:
                pygame.draw.circle(surface, (255, 150, 60) if self.style == "torchlit" else mix(self.sky, self.accent, 0.5), (int(x), int(y)), 1)
            else:
                surface.fill(dust, (int(x), int(y), 1, 1))

    def _draw_chandelier(self, surface, frame, flicker_timer):
        """The same old iron chandelier recurs in every room, though its bulbs do not behave."""
        cx = 200 if self.room_index % 2 == 0 else 480
        cy = 54
        pygame.draw.line(surface, (44, 39, 39), (cx, 0), (cx, cy - 8), 3)
        pygame.draw.circle(surface, (91, 73, 59), (cx, cy - 7), 5, 2)
        pygame.draw.circle(surface, (35, 31, 34), (cx, cy), 7)
        pygame.draw.circle(surface, (103, 82, 62), (cx, cy), 7, 1)
        for side in (-1, 1):
            pts = [(cx, cy), (cx + side * 13, cy - 5), (cx + side * 27, cy - 2),
                   (cx + side * 34, cy + 6), (cx + side * 34, cy + 13)]
            pygame.draw.lines(surface, (88, 72, 57), False, pts, 2)
            pygame.draw.circle(surface, (94, 76, 60), (cx + side * 34, cy + 12), 4, 1)
        pygame.draw.line(surface, (87, 70, 57), (cx, cy + 3), (cx, cy + 17), 2)
        bulbs = [(cx - 34, cy + 19), (cx - 17, cy + 11), (cx, cy + 20),
                 (cx + 17, cy + 11), (cx + 34, cy + 19)]
        for i, (bx, by) in enumerate(bulbs):
            # Normally they glow unevenly. A threat makes them snap and flutter together.
            if flicker_timer:
                lit = (flicker_timer + i * 3) % 11 not in (0, 1, 4, 5, 8)
            else:
                lit = (frame + i * 17 + self.room_index * 5) % 173 > 5
            pygame.draw.line(surface, (96, 76, 59), (bx, by - 4), (bx, by + 1), 2)
            if lit:
                add_glow(surface, bx, by + 3, 10, (36, 25, 15), steps=2)
            pygame.draw.ellipse(surface, (168, 137, 91) if lit else (41, 37, 36),
                                (bx - 3, by, 6, 9))

    def _draw_recurring_portrait(self, surface, frame):
        """A family portrait follows the recordings and becomes less trustworthy each tape."""
        x, y = 19, 177
        pygame.draw.rect(surface, (22, 18, 20), (x - 4, y - 4, 35, 49))
        pygame.draw.rect(surface, (102, 72, 54), (x, y, 27, 41), 2)
        pygame.draw.rect(surface, (17, 19, 23), (x + 4, y + 4, 19, 33))
        shift = 1 if self.chap_no >= 2 else 0
        pygame.draw.ellipse(surface, (45, 44, 49), (x + 8 + shift, y + 9, 8, 10))
        pygame.draw.polygon(surface, (39, 39, 44), [(x + 5 + shift, y + 34), (x + 7 + shift, y + 20),
                                                     (x + 17 + shift, y + 20), (x + 20 + shift, y + 34)])
        if self.chap_no >= 1:
            pygame.draw.line(surface, (112, 35, 39), (x + 11 + shift, y + 15), (x + 14 + shift, y + 15), 1)
        if self.chap_no >= 2:
            pygame.draw.line(surface, (74, 111, 61), (x + 3, y + 25), (x + 9, y + 21), 2)
            pygame.draw.line(surface, (74, 111, 61), (x + 3, y + 25), (x + 7, y + 31), 1)
        if self.chap_no >= 3:
            pygame.draw.rect(surface, (17, 19, 23), (x + 4, y + 4, 19, 33))
        misplaced = self.chap_no >= 4 and frame % 210 < 38
        dot = (x + 13, y + 14) if misplaced else (x + 23, y + 2)
        lit = (frame // 18) % 2 == 0
        pygame.draw.circle(surface, (196, 30, 34) if lit else (53, 25, 28), dot, 2)
        if misplaced and lit:
            pygame.draw.circle(surface, (76, 8, 12), dot, 5, 1)

    def _draw_tape_wear(self, surface, frame):
        """Add mild image dropouts without obscuring platforms or enemies."""
        if frame % 173 in (0, 1):
            y = 125 + (frame * 7) % 270
            pygame.draw.line(surface, mix(self.sky, (200, 205, 210), 0.45), (0, y), (W, y - 1), 1)
            pygame.draw.line(surface, mix(self.sky, (120, 42, 48), 0.30), (0, y + 2), (W, y + 1), 1)
        for i in range(5):
            x = (i * 173 + frame * (i + 1)) % W
            y = (i * 89 + frame * 2) % 440
            surface.fill(mix(self.sky, (205, 205, 198), 0.44), (x, y, 1, 1))


def monitor_line(surface, frame, sky, strength):
    """A hospital-monitor line. The blip crosses the wall every time the steady beep sounds (every 300 frames)."""
    t = (frame - 150) % 300
    bx = t * 6
    pts = []
    for x in range(0, W, 4):
        d = x - bx
        y = 66
        if -30 < d < -20:
            y -= 4
        elif -20 <= d < -14:
            y -= 26
        elif -14 <= d < -8:
            y += 12
        elif -8 <= d < -2:
            y -= 4
        pts.append((x, y))
    col = mix(sky, (90, 200, 130), strength)
    pygame.draw.lines(surface, col, False, pts, 2)
    if 0 < bx < W:
        add_glow(surface, bx, 66, 12, (int(50 * strength), int(120 * strength), int(80 * strength)))


_fog_bits = [(random.uniform(0, W * 2), random.uniform(20, 130), random.uniform(30, 60), random.uniform(20, 45)) for _ in range(18)]


def menu_background(surface, frame):
    """The slow, foggy backdrop behind the menus."""
    h_gradient(surface, (10, 7, 14), (34, 22, 40), 0, H)
    add_glow(surface, 560, 120, 140, (34, 30, 24))
    pygame.draw.circle(surface, (150, 146, 120), (560, 120), 30)
    pygame.draw.circle(surface, (20, 14, 26), (572, 112), 27)
    off = int(frame * 0.4) % (W * 2)
    for fx, fy, fw, fh in _fog_bits:
        x = (fx - off) % (W * 2) - W
        if -260 < x < W + 60:
            pygame.draw.ellipse(surface, (44, 38, 46), (x, fy + 300, fw, fh))
    for i in range(30):
        x = (i * 97 + frame * (0.2 + (i % 5) * 0.05)) % W
        y = (i * 53 + math.sin(frame * 0.01 + i) * 20) % 460
        surface.fill((90, 82, 96), (int(x), int(y), 1, 1))


def fade(surface, alpha):
    """Cover the picture toward black as alpha rises from 0 (nothing) to 255 (fully black).
    Drawn as plain stripes (no separate picture, no alpha blending) so it works everywhere."""
    a = clamp(alpha, 0, 255)
    if a <= 4:
        return
    if a >= 250:
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, W, H))
        return
    step = max(1, int(6 - a / 50))
    for y in range(0, H, step):
        pygame.draw.rect(surface, (0, 0, 0), (0, y, W, max(1, step - 1)))


# ------------------------------------------------------------------
# platforms, doors, keys, tapes  (already direct draws; unchanged)
# ------------------------------------------------------------------
def draw_platform(surface, rect, chapter, frame=0):
    style = chapter.get("style", "")
    accent = tuple(chapter.get("accent", (120, 120, 120)))
    base = mix((55, 50, 62), accent, 0.30)
    big = rect.height >= 30
    if style == "cobweb":
        base = mix((70, 54, 44), accent, 0.15)
    elif style == "roots":
        base = mix((52, 40, 30), accent, 0.20)
    elif style == "tiles":
        base = mix((70, 76, 86), (200, 208, 215), 0.30)
    pygame.draw.rect(surface, base, rect)
    dark = mix(base, (0, 0, 0), 0.35)
    if style == "cobweb":
        for y in range(rect.y + 6, rect.bottom - 2, 9):
            pygame.draw.line(surface, dark, (rect.x + 2, y), (rect.right - 3, y), 1)
    else:
        step = 40 if big else 24
        for x in range(rect.x + step, rect.right - 4, step):
            pygame.draw.line(surface, dark, (x, rect.y + 3), (x, rect.bottom - 3), 1)
        if big:
            pygame.draw.line(surface, dark, (rect.x + 2, rect.y + 20), (rect.right - 3, rect.y + 20), 1)
    pygame.draw.line(surface, mix(base, (255, 255, 255), 0.30), rect.topleft, rect.topright, 2)
    pygame.draw.rect(surface, dark, rect, 1)
    if style == "roots":
        for x in range(rect.x + 4, rect.right - 6, 11):
            pygame.draw.ellipse(surface, (54, 86, 50), (x, rect.y - 2, 9, 5))
    elif style == "tiles" and not big:
        pygame.draw.line(surface, (225, 232, 238), (rect.x + 2, rect.y + 2), (rect.right - 3, rect.y + 2), 1)


def draw_door(surface, rect, unlocked, frame, open_t=0.0):
    """open_t goes from 0 to 1 while the door swings open."""
    pygame.draw.rect(surface, (50, 32, 24), rect.inflate(8, 8))
    if unlocked:
        pulse = 0.5 + 0.5 * math.sin(frame * 0.08)
        add_glow(surface, rect.centerx, rect.centery, 55, (int(20 + 16 * pulse), int(44 + 24 * pulse), int(22 + 8 * pulse)))
    if open_t > 0:
        pygame.draw.rect(surface, (230, 240, 210), rect)
        add_glow(surface, rect.centerx, rect.centery, int(60 + 50 * open_t), (95, 100, 78))
    leaf_w = max(4, int(rect.w * (1 - 0.85 * open_t)))
    leaf = pygame.Rect(rect.x, rect.y, leaf_w, rect.h)
    pygame.draw.rect(surface, (95, 60, 38), leaf)
    if leaf_w > 20:
        pygame.draw.rect(surface, (60, 38, 26), leaf.inflate(-16, -16), 2)
        pygame.draw.circle(surface, (210, 180, 90), (leaf.right - 10, leaf.centery), 3)
    light = (70, 220, 90) if unlocked else (200, 40, 40)
    pygame.draw.circle(surface, light, (rect.centerx, rect.top - 10), 4)
    add_glow(surface, rect.centerx, rect.top - 10, 12, tuple(int(c * 0.35) for c in light))


def draw_key(surface, rect, frame):
    bob = int(math.sin(frame * 0.1) * 3)
    cx, cy = rect.centerx, rect.centery + bob
    add_glow(surface, cx, cy, 22, (55, 46, 12))
    gold = (240, 205, 75)
    pygame.draw.circle(surface, gold, (cx - 7, cy), 6, 3)
    pygame.draw.line(surface, gold, (cx - 1, cy), (cx + 11, cy), 3)
    pygame.draw.line(surface, gold, (cx + 8, cy), (cx + 8, cy + 6), 3)
    pygame.draw.line(surface, gold, (cx + 11, cy), (cx + 11, cy + 4), 3)
    a = frame * 0.06
    for k in range(2):
        sx, sy = cx + math.cos(a + k * math.pi) * 17, cy + math.sin(a + k * math.pi) * 10
        pygame.draw.line(surface, (255, 245, 190), (sx - 2, sy), (sx + 2, sy), 1)
        pygame.draw.line(surface, (255, 245, 190), (sx, sy - 2), (sx, sy + 2), 1)


def draw_tape(surface, rect, frame):
    """A little cassette. It pulses red so you notice it, and its reels turn."""
    pulse = 0.5 + 0.5 * math.sin(frame * 0.08)
    add_glow(surface, rect.centerx, rect.centery, 22, (int(45 * pulse), 5, 6))
    pygame.draw.rect(surface, (35, 35, 40), rect, border_radius=2)
    pygame.draw.rect(surface, mix((60, 60, 60), (200, 60, 60), pulse), rect.inflate(8, 8), 2, border_radius=3)
    pygame.draw.rect(surface, (200, 200, 205), (rect.x + 3, rect.y + 3, rect.w - 6, 6))
    for cx in (rect.x + 8, rect.right - 8):
        cy = rect.y + 14
        pygame.draw.circle(surface, (230, 230, 230), (cx, cy), 3)
        a = frame * 0.2
        pygame.draw.line(surface, (40, 40, 44), (cx, cy), (cx + math.cos(a) * 3, cy + math.sin(a) * 3), 1)


def draw_projectile(surface, pr, frame):
    cx, cy = int(pr["x"]) + pr["size"] // 2, int(pr["y"]) + pr["size"] // 2
    if pr.get("paper"):
        velocity = math.hypot(pr["vx"], pr.get("vy", 0.0)) or 1.0
        ux, uy = pr["vx"] / velocity, pr.get("vy", 0.0) / velocity
        px, py = -uy, ux
        tip = (int(cx + ux * 9), int(cy + uy * 9))
        tail = (int(cx - ux * 7), int(cy - uy * 7))
        points = [tip, (int(cx + px * 4), int(cy + py * 4)), tail,
                  (int(cx - px * 4), int(cy - py * 4))]
        add_glow(surface, cx, cy, 15, (88, 54, 34))
        pygame.draw.polygon(surface, (206, 187, 146), points)
        pygame.draw.lines(surface, (72, 49, 39), True, points, 1)
        pygame.draw.line(surface, (112, 48, 43), (cx - int(ux * 4), cy - int(uy * 4)),
                         (cx + int(ux * 4), cy + int(uy * 4)), 1)
        return
    if pr.get("wave"):
        direction = 1 if pr["vx"] > 0 else -1
        wave = pygame.Rect(int(pr["x"]), int(pr["y"] + 9), pr["size"], pr["size"] - 9)
        add_glow(surface, cx, wave.centery, 27, (101, 50, 28))
        points = [(wave.left, wave.bottom), (wave.left + 6, wave.top + 5),
                  (wave.left + 13, wave.centery), (wave.left + 21, wave.top),
                  (wave.right, wave.bottom)]
        pygame.draw.polygon(surface, (93, 70, 53), points)
        pygame.draw.lines(surface, (224, 170, 103), False, points[1:-1], 3)
        for trail in range(3):
            tx = cx - direction * (11 + trail * 7)
            pygame.draw.line(surface, (112, 74, 52), (tx, wave.top + 8 + trail * 2),
                             (tx - direction * 7, wave.bottom - 2), 2)
        return
    velocity = math.hypot(pr["vx"], pr.get("vy", 0.0)) or 1.0
    trail_x, trail_y = -pr["vx"] / velocity, -pr.get("vy", 0.0) / velocity
    for k in range(1, 5):
        tail = (int(cx + trail_x * k * 5), int(cy + trail_y * k * 5))
        pygame.draw.line(surface, mix((0, 0, 0), (70, 140, 80), 1 - k * 0.2),
                         (cx, cy), tail, max(1, pr["size"] // 2 - k))
    add_glow(surface, cx, cy, 16, (25, 75, 34))
    pulse = 1 if frame % 8 < 4 else 0
    pygame.draw.circle(surface, (70, 120, 70), (cx, cy), pr["size"] // 2 + 3)
    pygame.draw.circle(surface, (180, 250, 180) if pulse else (130, 205, 155), (cx, cy), pr["size"] // 2)


# ------------------------------------------------------------------
# the player -- drawn straight onto the room, no separate picture
# ------------------------------------------------------------------
class PlayerSprite:
    """Draws the player and animates: breathing, walking, jump stretch, landing squash, blinking, hit flash."""

    def __init__(self):
        self.squash = 0.0
        self.walk = 0.0
        self.prev_ground = False
        self.prev_vy = 0.0
        self.moving = False
        self.in_air = False
        self.stretch = 0.0
        self.hurt = 0
        self.prev_invincible = 0
        self.running = False
        self.lean = 0.0

    def update(self, rect, vel_y, on_ground, move, facing, invincible, frame, particles, running=False):
        feet_x, feet_y = rect.centerx, rect.bottom
        if on_ground and not self.prev_ground and self.prev_vy > 3:          # landed
            self.squash = min(1.0, self.prev_vy / 10)
            particles.burst(feet_x, feet_y - 2, 6, (150, 145, 160), speed=1.6, life=18, size=2.5, gravity=-0.02)
        if self.prev_ground and not on_ground and vel_y < -5:                # jumped
            particles.burst(feet_x, feet_y - 2, 4, (150, 145, 160), speed=1.2, life=14, size=2, gravity=-0.02)
        self.moving = bool(move) and on_ground
        self.running = self.moving and running
        if self.moving:
            self.walk += 0.58 if self.running else 0.38
            self.lean = facing * (2.4 if self.running else 0.8)
            if frame % 7 == 0:
                particles.emit(feet_x - facing * 8, feet_y - 2, -facing * 0.4, -0.2, 14, 2.2, (140, 135, 150))
        else:
            self.lean *= 0.72
        self.in_air = not on_ground
        self.stretch = clamp(-vel_y / 40, -0.10, 0.16) if not on_ground else 0.0
        self.squash = max(0.0, self.squash - 0.11)
        if invincible > self.prev_invincible:
            self.hurt = 8
        self.hurt = max(0, self.hurt - 1)
        self.prev_invincible = invincible
        self.prev_ground = on_ground
        self.prev_vy = vel_y

    def draw(self, surface, rect, facing, invincible, frame):
        if invincible > 0 and (frame // 4) % 2 == 0:
            return                                              # blink while invincible: skip this frame entirely
        if not self.in_air:
            pygame.draw.ellipse(surface, (18, 16, 24), (rect.centerx - 13, rect.bottom - 5, 26, 8))
        sx = 1 + 0.24 * self.squash - 0.6 * self.stretch
        sy = 1 - 0.24 * self.squash + self.stretch
        cx = rect.centerx + round(self.lean)
        base_y = rect.bottom - 4 * sy
        h = 46 * sy
        coat = (93, 25, 29) if self.hurt else (39, 41, 48)
        coat_edge = (150, 48, 48) if self.hurt else (79, 79, 86)
        face_color = (175, 170, 166)

        breathe = 0 if (self.moving or self.in_air) else int(round(math.sin(frame * 0.07)))
        wave = math.sin(frame * 0.25 + self.walk)
        bounce = abs(math.sin(self.walk * 2)) * (2.3 if self.running else 1.0) if self.moving else 0
        top_y = base_y - h + bounce
        head_cx, head_cy = cx + facing * 1.5, top_y + 8 * sy + breathe

        # A narrow, uneven coat replaces the old round, stacked body silhouette.
        lift1 = max(0.0, math.sin(self.walk)) * 3 if self.moving else 0
        lift2 = max(0.0, -math.sin(self.walk)) * 3 if self.moving else 0
        stride = math.sin(self.walk)
        stride_len = 6 if self.running else 4
        leg_color = (27, 28, 34)
        for side, phase in ((-1, stride), (1, -stride)):
            hip = (int(cx + side * 4 * sx), int(top_y + 34 * sy))
            knee = (int(cx + side * 4 * sx + phase * stride_len * 0.45),
                    int(top_y + (39 if self.in_air else 41) * sy - max(0, phase) * 2))
            foot_x = int(cx + side * 4 * sx + phase * stride_len)
            foot_y = int(base_y - 2 - (max(0, phase) * 3 if self.moving else 0))
            if self.in_air:
                knee = (knee[0] - side * 2, int(top_y + 39 * sy))
                foot_y = int(base_y - 7)
            pygame.draw.lines(surface, leg_color, False, [hip, knee, (foot_x, foot_y - 1)], 4)
            pygame.draw.circle(surface, (45, 42, 45), knee, 2)
            pygame.draw.ellipse(surface, (18, 18, 22), (foot_x - 5, foot_y - 2, 10, 5))

        coat_points = [(cx - 5 * sx, top_y + 14 * sy), (cx - 11 * sx, top_y + 20 * sy),
                       (cx - 9 * sx, top_y + 36 * sy), (cx - 6 * sx, top_y + 40 * sy),
                       (cx + 8 * sx, top_y + 38 * sy), (cx + 10 * sx, top_y + 21 * sy),
                       (cx + 4 * sx, top_y + 14 * sy)]
        pygame.draw.polygon(surface, coat, coat_points)
        pygame.draw.lines(surface, coat_edge, False, [coat_points[1], (cx - 6 * sx, top_y + 24 * sy),
                                                       (cx - 4 * sx, top_y + 38 * sy)], 1)
        pygame.draw.line(surface, (22, 23, 28), (cx + 2 * sx, top_y + 24 * sy),
                         (cx + 3 * sx, top_y + 36 * sy), 1)
        for button_y in (27, 32):
            pygame.draw.circle(surface, (118, 101, 77), (int(cx + 1 * sx), int(top_y + button_y * sy)), 1)
        # Narrow sleeves and pale hands make the body read as a person, not a snow figure.
        sleeve_end_y = top_y + 35 * sy
        arm_swing = stride * (5 if self.running else 3) if self.moving else 0
        jump_tuck = -3 if self.in_air else 0
        left_hand = (int(cx - 9 * sx - arm_swing), int(sleeve_end_y + jump_tuck))
        right_hand = (int(cx + 8 * sx + arm_swing), int(sleeve_end_y - jump_tuck))
        pygame.draw.lines(surface, coat, False, [(cx - 7 * sx, top_y + 17 * sy),
                                                  (cx - 12 * sx - arm_swing * 0.5, top_y + 24 * sy + lift1),
                                                  left_hand], 4)
        pygame.draw.lines(surface, coat, False, [(cx + 6 * sx, top_y + 17 * sy),
                                                  (cx + 11 * sx + arm_swing * 0.5, top_y + 25 * sy + lift2),
                                                  right_hand], 4)
        pygame.draw.circle(surface, face_color, left_hand, 2)
        pygame.draw.circle(surface, face_color, right_hand, 2)

        # The red scarf is loose and dragged to one side, like a strip of warning tape.
        scarf = (110, 15, 15) if self.hurt else (153, 35, 43)
        flutter = wave * (4 if self.running else 2) if self.moving else math.sin(frame * 0.045) * 1.5
        pygame.draw.polygon(surface, scarf, [(cx - 7 * sx, top_y + 15 * sy),
                                             (cx + 6 * sx, top_y + 16 * sy),
                                             (cx + 4 * sx, top_y + 21 * sy),
                                             (cx - 6 * sx, top_y + 20 * sy)])
        trail = -1 if facing > 0 else 1
        pygame.draw.polygon(surface, scarf, [(cx + trail * 5 * sx, top_y + 18 * sy),
                                             (cx + trail * 13 * sx, top_y + 19 * sy + flutter),
                                             (cx + trail * 10 * sx, top_y + 24 * sy + flutter),
                                             (cx + trail * 4 * sx, top_y + 21 * sy)])

        # The hood is a dark, pointed silhouette. No face details appear before the reveal.
        hood = (24, 25, 30)
        lining = (64, 63, 67)
        pygame.draw.polygon(surface, hood, [(cx - 10 * sx, top_y + 18 * sy),
                                            (cx - 11 * sx, top_y + 8 * sy),
                                            (cx - 7 * sx, top_y + 1 * sy),
                                            (cx, top_y - 2 * sy),
                                            (cx + 8 * sx, top_y + 2 * sy),
                                            (cx + 11 * sx, top_y + 9 * sy),
                                            (cx + 8 * sx, top_y + 18 * sy)])
        # Hood lining frames an empty black opening, rather than a visible head.
        pygame.draw.polygon(surface, lining, [(cx - 7 * sx, top_y + 7 * sy),
                                              (cx - 4 * sx, top_y + 4 * sy),
                                              (cx + 4 * sx, top_y + 4 * sy),
                                              (cx + 7 * sx, top_y + 8 * sy),
                                              (cx + 6 * sx, top_y + 16 * sy),
                                              (cx - 6 * sx, top_y + 16 * sy)])
        pygame.draw.polygon(surface, (4, 5, 8), [(cx - 5 * sx, top_y + 8 * sy),
                                                  (cx - 3 * sx, top_y + 6 * sy),
                                                  (cx + 3 * sx, top_y + 6 * sy),
                                                  (cx + 5 * sx, top_y + 9 * sy),
                                                  (cx + 5 * sx, top_y + 16 * sy),
                                                  (cx - 5 * sx, top_y + 16 * sy)])
        pygame.draw.line(surface, (86, 84, 87), (cx - 8 * sx, top_y + 8 * sy),
                         (cx - 6 * sx, top_y + 17 * sy), 1)
        pygame.draw.line(surface, (18, 19, 24), (cx + 7 * sx, top_y + 8 * sy),
                         (cx + 6 * sx, top_y + 17 * sy), 1)


# ------------------------------------------------------------------
# monsters
# ------------------------------------------------------------------
def draw_monster(surface, m, frame, player):
    {"patroller": _patroller, "flyer": _flyer, "chaser": _chaser, "shooter": _shooter,
     "doorstalker": _doorstalker, "beamer": _beamer, "summoner": _summoner,
     "guardian": _guardian, "warden": _warden, "secret_boss": _witness}.get(m.kind, _patroller)(surface, m, frame, player)
    if getattr(m, "is_copy", False) and not m.defeated:
        # Designation 05 is almost the same picture, but its color channels cannot agree.
        r = m.rect
        if frame % 3 != 0:
            pygame.draw.rect(surface, (95, 25, 35), r.inflate(4, 4).move(2, 0), 1)
            pygame.draw.rect(surface, (28, 91, 105), r.inflate(2, 2).move(-2, 0), 1)
        pygame.draw.line(surface, (190, 206, 214), (r.left - 2, r.centery), (r.left + 3, r.centery), 1)


def draw_charge_item(surface, rect, frame):
    """The charge: a small glowing cell with a bolt on it. Pick it up, then touch the presence."""
    pulse = 0.5 + 0.5 * math.sin(frame * 0.12)
    cx, cy = rect.centerx, rect.centery + int(math.sin(frame * 0.09) * 3)
    add_glow(surface, cx, cy, int(26 + 6 * pulse), (18, 40, 70))
    body = pygame.Rect(0, 0, 16, 22)
    body.center = (cx, cy)
    pygame.draw.rect(surface, (30, 60, 100), body, border_radius=3)
    pygame.draw.rect(surface, (140, 200, 255), body, 2, border_radius=3)
    pygame.draw.rect(surface, (140, 200, 255), (cx - 3, body.top - 3, 6, 3))
    bolt = [(cx + 2, cy - 8), (cx - 3, cy + 1), (cx, cy + 1), (cx - 2, cy + 8), (cx + 4, cy - 2), (cx + 1, cy - 2)]
    pygame.draw.polygon(surface, mix((200, 230, 255), (255, 255, 255), pulse), bolt)


def _beamer(surface, m, frame, player):
    """THE SIGNAL: a projector whose bright sweep marks the danger lane."""
    if m.defeated:
        return
    r = m.rect
    cx, cy = r.centerx, r.centery
    face = 1 if player.centerx >= cx else -1
    lit = m.state in ("telegraph", "beam", "exposed")
    pulse = 0.5 + 0.5 * math.sin(frame * (0.7 if m.state == "telegraph" else 0.22))
    add_glow(surface, cx + face * 18, cy, 48 if lit else 26,
             (72, 21, 23) if lit else (30, 31, 44))
    # Heavy tripod feet; the machine has a clear silhouette unlike a floating television.
    pygame.draw.line(surface, (54, 49, 48), (cx - 10, r.bottom - 5), (cx - 22, r.bottom + 12), 4)
    pygame.draw.line(surface, (54, 49, 48), (cx + 10, r.bottom - 5), (cx + 22, r.bottom + 12), 4)
    pygame.draw.line(surface, (69, 61, 54), (cx, r.bottom - 5), (cx, r.bottom + 15), 4)
    pygame.draw.line(surface, (23, 22, 25), (cx - 20, r.bottom + 13), (cx + 20, r.bottom + 13), 3)
    # Two exposed reels turn at different rates, as though one is winding the room backward.
    for side, radius in ((-1, 12), (1, 10)):
        rx, ry = cx + side * 17, r.top + 4
        pygame.draw.circle(surface, (58, 54, 53), (rx, ry), radius + 3)
        pygame.draw.circle(surface, (151, 134, 111), (rx, ry), radius, 2)
        pygame.draw.circle(surface, (15, 14, 18), (rx, ry), 3)
        for spoke in range(3):
            a = frame * (0.035 if side < 0 else -0.052) + spoke * math.tau / 3
            pygame.draw.line(surface, (118, 105, 91), (rx, ry),
                             (int(rx + math.cos(a) * (radius - 2)), int(ry + math.sin(a) * (radius - 2))), 1)
    pygame.draw.line(surface, (187, 164, 120), (cx - 7, r.top + 4), (cx + 8, r.top + 4), 2)
    pygame.draw.line(surface, (42, 39, 42), (cx - 17, r.top + 15), (cx + 15, r.top + 15), 5)
    casing = pygame.Rect(r.x - 5, r.y + 13, r.w + 10, r.h - 9)
    pygame.draw.polygon(surface, (71, 65, 62), [(casing.left + 5, casing.top), (casing.right - 5, casing.top),
                                                (casing.right, casing.bottom - 5), (casing.left, casing.bottom - 5)])
    pygame.draw.polygon(surface, (137, 123, 100), [(casing.left + 5, casing.top), (casing.right - 5, casing.top),
                                                   (casing.right, casing.bottom - 5), (casing.left, casing.bottom - 5)], 2)
    # Case screws, an embossed model number, and the square heat vents of an old projector.
    for bx in (casing.left + 5, casing.right - 5):
        for by in (casing.top + 5, casing.bottom - 8):
            pygame.draw.circle(surface, (192, 169, 125), (bx, by), 2)
            pygame.draw.line(surface, (38, 35, 36), (bx - 1, by), (bx + 1, by), 1)
    for vent in range(4):
        vx = cx - 12 + vent * 8
        pygame.draw.line(surface, (38, 36, 39), (vx, casing.bottom - 5), (vx + 3, casing.bottom - 2), 1)
    pygame.draw.rect(surface, (37, 34, 37), (cx - 8, casing.top + 24, 16, 5))
    for digit in range(3):
        pygame.draw.line(surface, (176, 55, 51), (cx - 5 + digit * 5, casing.top + 25),
                         (cx - 3 + digit * 5, casing.top + 27), 1)
    pygame.draw.rect(surface, (24, 22, 25), (cx - 13, casing.top + 6, 26, 15), border_radius=3)
    lens_x, lens_y = cx + face * 9, casing.top + 13
    lens_color = (236, 223, 180) if m.state == "exposed" else (184, 48, 50) if lit else (83, 93, 101)
    pygame.draw.circle(surface, (8, 8, 11), (lens_x, lens_y), 8)
    pygame.draw.circle(surface, lens_color, (lens_x, lens_y), 5, 2)
    pygame.draw.circle(surface, (235, 229, 204), (lens_x, lens_y), 2 if lit else 1)
    # Shutter leaves iris open in three uneven blades; the outer glass catches a cold highlight.
    for blade in range(3):
        a = frame * 0.025 + blade * math.tau / 3
        inner = (int(lens_x + math.cos(a) * 3), int(lens_y + math.sin(a) * 3))
        outer = (int(lens_x + math.cos(a + 0.7) * 7), int(lens_y + math.sin(a + 0.7) * 7))
        pygame.draw.line(surface, (52, 53, 59), inner, outer, 1)
    # A strip of celluloid leaks from the housing and winds around one leg.
    ribbon_y = casing.bottom - 5 + int(math.sin(frame * 0.08) * 3)
    pygame.draw.lines(surface, (153, 133, 94), False,
                      [(cx - 8, ribbon_y), (cx - 18, ribbon_y + 5), (cx - 14, r.bottom + 6),
                       (cx - 4, r.bottom + 11)], 2)
    for k in range(3):
        pygame.draw.circle(surface, (24, 22, 25), (cx - 14 + k * 3, ribbon_y + 4 + k * 2), 1)
    if m.state == "telegraph":
        target_y = max(24, min(H - 24, int(m.beam_y)))
        pygame.draw.line(surface, (170, 37, 39), (BEAM_SAFE_LANE, target_y),
                         (W - BEAM_SAFE_LANE, target_y), 2)
        pygame.draw.circle(surface, (225, 68, 61), (player.centerx, target_y), int(5 + pulse * 5), 1)
    elif m.state == "exposed":
        pygame.draw.circle(surface, (225, 220, 184), (lens_x, lens_y), 11 + int(pulse * 3), 1)
    beam = m.beam_rect
    if beam is not None:
        pygame.draw.rect(surface, (223, 219, 205), beam)
        for stripe in range(beam.left, beam.right, 17):
            offset = int((frame * 11 + stripe * 3) % 23)
            pygame.draw.line(surface, (62, 66, 71), (stripe + offset, beam.top),
                             (stripe + offset - 8, beam.bottom), 2)
        pygame.draw.line(surface, (255, 245, 220), (beam.left, beam.centery), (beam.right, beam.centery), 1)


def _summoner(surface, m, frame, player):
    """THE COUNSEL: a dead attorney whose verdict is aimed at the last place you stood."""
    if m.defeated:
        return
    r = m.rect
    cx, by = r.centerx, r.bottom
    edge = (156, 131, 92)
    pulse = 0.5 + 0.5 * math.sin(frame * 0.18)
    calling = m.state in ("warning", "appeal_warning")
    sentencing = m.state == "sentence"
    opened = m.state == "open"
    sway = int(math.sin(frame * 0.045) * 3)
    add_glow(surface, cx, r.top + 19, 34 if calling or opened else 23,
             (76, 25, 27) if calling else (46, 35, 45))
    # A court robe flares into a ragged hem; its collar and lapels frame a hollow face.
    pygame.draw.polygon(surface, (36, 32, 34), [(cx - 8 + sway, r.top + 16),
                                                (cx + 8 + sway, r.top + 16),
                                                (cx + 19, r.top + 36), (cx + 24, by - 5),
                                                (cx + 16, by), (cx - 16, by),
                                                (cx - 24, by - 5), (cx - 19, r.top + 36)])
    pygame.draw.lines(surface, edge, False,
                      [(cx - 18, by - 5), (cx - 13, r.top + 34), (cx - 6, r.top + 21),
                       (cx + 6, r.top + 21), (cx + 13, r.top + 34), (cx + 18, by - 5)], 2)
    pygame.draw.arc(surface, (24, 21, 24), (cx - 15, r.top + 24, 30, 34), 0, math.pi, 4)
    # Powdered wig curls, stiff collar points, and robe seams establish the dead lawyer silhouette.
    for side in (-1, 0, 1):
        pygame.draw.circle(surface, (187, 181, 165), (cx + side * 7, r.top + 1), 4)
        pygame.draw.circle(surface, (77, 72, 70), (cx + side * 7, r.top + 1), 4, 1)
    pygame.draw.polygon(surface, (210, 201, 181), [(cx - 10, r.top + 16), (cx, r.top + 22),
                                                   (cx - 4, r.top + 29), (cx - 15, r.top + 20)])
    pygame.draw.polygon(surface, (210, 201, 181), [(cx + 10, r.top + 16), (cx, r.top + 22),
                                                   (cx + 4, r.top + 29), (cx + 15, r.top + 20)])
    pygame.draw.line(surface, (115, 97, 80), (cx - 11, r.top + 29), (cx - 4, by - 7), 2)
    pygame.draw.line(surface, (115, 97, 80), (cx + 11, r.top + 29), (cx + 4, by - 7), 2)
    # Torn legal pages are stitched into the hem in place of the old bell ribs.
    for band_y in (r.top + 37, r.top + 47, r.top + 57):
        pygame.draw.line(surface, (101, 83, 67), (cx - 16, band_y), (cx + 16, band_y - 2), 1)
    for mark in range(5):
        mx = cx - 13 + mark * 6
        pygame.draw.line(surface, (163, 133, 94), (mx, r.top + 41), (mx + 2, r.top + 45), 1)
    # A shredded legal ribbon trails from the robe.
    cord_sway = int(math.sin(frame * 0.07) * 4)
    pygame.draw.lines(surface, (49, 39, 38), False,
                      [(cx + 20, r.top + 34), (cx + 28, r.top + 42 + cord_sway),
                       (cx + 25, r.top + 54), (cx + 33, r.top + 61 + cord_sway)], 2)
    pygame.draw.circle(surface, (164, 131, 87), (cx + 33, r.top + 61 + cord_sway), 3, 1)
    # The face is a black void beneath the wig; the red pinhole appears during recovery.
    mouth_r = 11 + int(pulse * 2) if calling else 8
    mouth_color = (193, 149, 98) if opened else edge
    pygame.draw.ellipse(surface, (23, 19, 21), (cx - mouth_r, r.top + 3, mouth_r * 2, 20))
    pygame.draw.ellipse(surface, mouth_color, (cx - mouth_r, r.top + 3, mouth_r * 2, 20), 2)
    pygame.draw.ellipse(surface, (7, 6, 9), (cx - mouth_r + 4, r.top + 8, mouth_r * 2 - 8, 10))
    if opened:
        pygame.draw.ellipse(surface, (225, 204, 165), (cx - 5, r.top + 10, 10, 7))
        pygame.draw.circle(surface, (15, 11, 13), (cx, r.top + 13), 2)
    else:
        for tooth in (-5, 0, 5):
            pygame.draw.line(surface, (153, 125, 94), (cx + tooth, r.top + 8), (cx + tooth, r.top + 12), 1)
    # The left arm holds cracked scales; the right arm lifts a judge's gavel to strike.
    for side in (-1, 1):
        shoulder = (cx + side * 13, r.top + 31)
        elbow = (cx + side * (28 + int(pulse * 3)), r.top + 15 + int(math.sin(frame * 0.18) * 3))
        pygame.draw.lines(surface, (40, 35, 37), False, [shoulder, elbow], 4)
        pygame.draw.circle(surface, edge, elbow, 4, 1)
    pygame.draw.line(surface, (182, 152, 103), (cx - 25, r.top + 8), (cx + 22, r.top + 8), 2)
    pygame.draw.line(surface, (182, 152, 103), (cx - 1, r.top + 5), (cx - 1, r.top + 18), 2)
    for side in (-1, 1):
        sx = cx + side * 18
        pygame.draw.line(surface, (156, 131, 92), (sx, r.top + 8), (sx, r.top + 17), 1)
        pygame.draw.arc(surface, (201, 174, 127), (sx - 7, r.top + 15, 14, 7), 0, math.pi, 1)
    gavel_x = int(m.verdict_x) if sentencing else cx + 23
    gavel_y = r.top + 19 if not sentencing else int(m.verdict_y - 55 + (14 - max(0, m.timer)) * 4)
    pygame.draw.line(surface, (104, 66, 43), (gavel_x - 11, gavel_y + 9), (gavel_x + 7, gavel_y - 9), 4)
    pygame.draw.rect(surface, (174, 138, 91), (gavel_x - 9, gavel_y - 14, 16, 8), border_radius=2)
    pygame.draw.rect(surface, (72, 51, 43), (gavel_x - 9, gavel_y - 14, 16, 8), 1, border_radius=2)
    # The red court seal marks your feet; its flash means the gavel is falling now.
    if m.state in ("warning", "sentence"):
        tx = int(m.verdict_x)
        ty = int(m.verdict_y)
        seal = pygame.Rect(tx - 54, ty - 8, 108, 16)
        seal_color = (238, 54, 50) if calling else (245, 220, 188)
        pygame.draw.ellipse(surface, (48, 12, 15), seal.inflate(8, 6))
        pygame.draw.ellipse(surface, seal_color, seal, 2 if calling else 4)
        pygame.draw.line(surface, seal_color, (tx - 33, ty), (tx + 33, ty), 1)
        pygame.draw.line(surface, seal_color, (tx, ty - 7), (tx, ty + 7), 1)
        if sentencing:
            pygame.draw.ellipse(surface, (242, 229, 198), seal.inflate(15, 12), 1)
    if m.state == "appeal_warning":
        dx, dy = player.centerx - cx, player.centery - (r.top + 18)
        distance = max(1.0, math.hypot(dx, dy))
        ux, uy = dx / distance, dy / distance
        for offset in (-0.32, 0.0, 0.32):
            angle = math.atan2(uy, ux) + offset
            end = (int(cx + math.cos(angle) * 170),
                   int(r.top + 18 + math.sin(angle) * 170))
            pygame.draw.line(surface, (151, 48, 47), (cx, r.top + 18), end, 1)
            pygame.draw.circle(surface, (211, 73, 59), end, 4, 1)
    if opened:
        add_glow(surface, cx, r.top + 14, 27, (126, 97, 54))
        pygame.draw.ellipse(surface, (239, 218, 173), (cx - 7, r.top + 8, 14, 14), 2)


def _guardian(surface, m, frame, player):
    """THE GATE: a walking iron exit that slams down, sends waves, and opens."""
    if m.defeated:
        return
    r = m.rect
    cx = r.centerx
    charging = m.state == "windup"
    slamming = m.state == "slam"
    recoiling = m.state == "recoil"
    stunned = m.state == "stunned"
    shake = int(math.sin(frame * 1.4) * 3) if slamming else 0
    lift = 3 if m.state == "windup" and m.timer < 22 else 0
    top_y = r.top - lift + (7 if slamming else 0) + shake
    add_glow(surface, cx, r.centery, 36 if slamming or recoiling else 20,
             (91, 24, 22) if slamming or recoiling else (41, 40, 47))
    # Crown bars make it look like a gate first, creature second.
    pygame.draw.rect(surface, (28, 27, 31), (cx - 21, top_y + 8, 42, 42))
    pygame.draw.rect(surface, (111, 101, 91), (cx - 21, top_y + 8, 42, 42), 3)
    for bx in range(cx - 15, cx + 16, 8):
        pygame.draw.line(surface, (89, 84, 80), (bx, top_y + 10), (bx, top_y + 47), 3)
        pygame.draw.line(surface, (27, 25, 27), (bx + 2, top_y + 10), (bx + 2, top_y + 47), 1)
    lintel = [(cx - 25, top_y + 12), (cx - 18, top_y - 7), (cx - 8, top_y + 2),
              (cx, top_y - 12), (cx + 8, top_y + 2), (cx + 18, top_y - 7),
              (cx + 25, top_y + 12)]
    pygame.draw.lines(surface, (147, 132, 107), False, lintel, 4)
    pygame.draw.line(surface, (39, 35, 35), (cx - 25, top_y + 12), (cx + 25, top_y + 12), 5)
    # Three keyholes glow like a row of watching windows. Their direction follows the player.
    for i, yy in enumerate((top_y + 21, top_y + 32, top_y + 42)):
        color = (211, 56, 45) if (charging or slamming) and i == 1 else (180, 153, 104) if stunned else (88, 60, 52)
        pygame.draw.circle(surface, (7, 6, 8), (cx + (player.centerx > cx and 1 or -1) * (8 if i == 1 else 0), yy), 4)
        pygame.draw.circle(surface, color, (cx, yy - 1), 2)
        pygame.draw.polygon(surface, color, [(cx - 2, yy), (cx + 2, yy), (cx + 1, yy + 5), (cx - 1, yy + 5)])
    # The body is carried on six iron struts. They brace outward before the slam.
    for side in (-1, 1):
        shoulder = (cx + side * 17, top_y + 18)
        knee = (cx + side * (26 if slamming else 21), r.bottom - 9 + (shake if side < 0 else -shake))
        foot = (cx + side * (31 if slamming else 25), r.bottom - 2)
        pygame.draw.lines(surface, (37, 34, 35), False, [shoulder, knee, foot], 4)
        pygame.draw.circle(surface, (134, 112, 83), knee, 3)
        for spike in range(2):
            sx = cx + side * (20 + spike * 4)
            sy = top_y + 19 + spike * 12
            pygame.draw.polygon(surface, (158, 147, 125), [(sx, sy), (sx + side * 10, sy + 4), (sx, sy + 8)])
    # A top plate visibly springs open after the floor impact: that is the stomp window.
    seam = (222, 203, 159) if stunned else (57, 49, 43)
    pygame.draw.line(surface, seam, (cx - 17, top_y + 8), (cx - 12, top_y - (3 if stunned else 0)), 3)
    pygame.draw.line(surface, seam, (cx + 17, top_y + 8), (cx + 12, top_y - (3 if stunned else 0)), 3)
    # A numbered service plate, rivets, and the reserve spring distinguish its final assault.
    plate = pygame.Rect(cx - 12, top_y + 51, 24, 10)
    pygame.draw.rect(surface, (67, 59, 51), plate)
    pygame.draw.rect(surface, (154, 132, 99), plate, 1)
    for i in range(4):
        pygame.draw.line(surface, (196, 177, 139), (plate.left + 4 + i * 4, plate.top + 3),
                         (plate.left + 4 + i * 4, plate.bottom - 3), 1)
    for side in (-1, 1):
        pygame.draw.circle(surface, (174, 147, 103), (cx + side * 18, top_y + 31), 2)
    if getattr(m, "special_mode", False):
        spring = (226, 114, 65) if recoiling else (182, 134, 87)
        for coil in range(4):
            yy = top_y - 13 + coil * 4
            pygame.draw.line(surface, spring, (cx - 5 + (coil % 2) * 10, yy),
                             (cx + 5 - (coil % 2) * 10, yy + 3), 2)
        if recoiling:
            for arc in range(3):
                pygame.draw.arc(surface, (174, 71, 54),
                                pygame.Rect(cx - 35 - arc * 7, top_y - 18 - arc * 4,
                                            70 + arc * 14, 56 + arc * 8), 0.15, 2.95, 1)
    if charging:
        for n in range(3):
            pygame.draw.line(surface, (114, 46, 42), (cx - 32 - n * 8, r.bottom - 8),
                             (cx - 25 - n * 8, r.bottom - 8), 2)
    if stunned:
        add_glow(surface, cx, top_y + 2, 24, (76, 54, 34))
        pygame.draw.line(surface, (231, 211, 165), (cx - 10, top_y + 2), (cx + 10, top_y + 2), 2)


def _witness(surface, m, frame, player):
    """A sealed personnel file that learned to stand, stalk, and strike."""
    if m.defeated:
        return
    r = m.rect
    cx = r.centerx
    slam = m.state == "slam"
    open_state = m.state == "stunned"
    sway = int(math.sin(frame * 0.09) * 2)
    add_glow(surface, cx, r.centery, 38 if slam else 23, (63, 28, 34) if slam else (34, 38, 43))
    # A tall black coat hangs from a rectangular file cover, with loose paper edges for shoulders.
    coat = [(cx - 17, r.top + 20), (cx + 17, r.top + 20), (cx + 25, r.bottom - 4),
            (cx, r.bottom - 10), (cx - 25, r.bottom - 4)]
    pygame.draw.polygon(surface, (19, 18, 22), coat)
    pygame.draw.lines(surface, (112, 91, 76), True, coat, 2)
    pygame.draw.polygon(surface, (42, 39, 42), [(cx - 15, r.top + 5), (cx + 15, r.top + 5),
                                                (cx + 12, r.top + 31), (cx - 12, r.top + 31)])
    pygame.draw.rect(surface, (151, 128, 94), (cx - 18, r.top + 2, 36, 31), 2)
    # The face is a camera aperture; the shutter narrows when it winds up.
    eye_y = r.top + 17
    pygame.draw.circle(surface, (7, 8, 10), (cx, eye_y), 8)
    lens = (187, 47, 54) if slam else (116, 147, 154) if open_state else (84, 108, 111)
    pygame.draw.circle(surface, lens, (cx, eye_y), 4)
    pygame.draw.circle(surface, (9, 9, 12), (cx, eye_y), 2)
    if m.boss_hp > 4:
        pygame.draw.line(surface, (198, 172, 114), (cx - 11, eye_y - 11), (cx + 11, eye_y - 11), 2)
    if m.boss_hp > 2:
        pygame.draw.rect(surface, (134, 105, 74), (cx - 13, r.top + 39, 26, 17), 1)
    for side in (-1, 1):
        points = [(cx + side * 16, r.top + 24), (cx + side * 31, r.top + 16 + sway),
                  (cx + side * 22, r.top + 41), (cx + side * 34, r.top + 47),
                  (cx + side * 14, r.top + 48)]
        pygame.draw.polygon(surface, (174, 164, 143) if open_state else (91, 83, 77), points)
        pygame.draw.lines(surface, (184, 160, 117), True, points, 1)
    for side in (-1, 1):
        foot_y = r.bottom - 2 + (5 if slam else 0)
        pygame.draw.line(surface, (38, 35, 38), (cx + side * 8, r.bottom - 19),
                         (cx + side * 16, foot_y), 4)
        pygame.draw.circle(surface, (158, 54, 58) if slam else (125, 107, 82),
                           (cx + side * 16, foot_y), 3)


def _warden(surface, m, frame, player):
    """THE RECORD: a living index card that files each escape attempt as another face."""
    r = m.rect
    cx, cy = r.centerx, r.centery
    glitch = random.random() < (0.10 + 0.08 * m.phase)
    body = (16, 14, 20)
    # A broken timecode halo and sprocket holes mark it as the tape's clerk, not another humanoid.
    halo = pygame.Rect(cx - 33, cy - 36, 66, 66)
    halo_color = (174, 43, 50) if m.phase >= 3 else (88, 75, 90)
    for segment in range(4):
        start = frame * 0.008 + segment * math.pi / 2
        pygame.draw.arc(surface, halo_color, halo, start, start + 0.72, 2)
    for side in (-1, 1):
        for hole in range(4):
            hy = r.top + 22 + hole * 11
            pygame.draw.rect(surface, (91, 81, 91), (cx + side * 24 - 2, hy, 4, 3))
    # The coat is a stacked file: color tabs, paper edges, and a stamped case number.
    for tab, color in enumerate(((114, 74, 61), (95, 91, 112), (132, 103, 71))):
        ty = r.top + 24 + tab * 11
        pygame.draw.rect(surface, color, (r.left + 3, ty, 5, 7))
        pygame.draw.line(surface, (35, 29, 36), (r.left + 5, ty + 2), (r.left + 5, ty + 5), 1)
    pygame.draw.rect(surface, (74, 64, 71), (r.right - 8, r.top + 9, 5, 30), 1)
    for tick in range(4):
        pygame.draw.line(surface, (146, 67, 72), (r.right - 7, r.top + 14 + tick * 6),
                         (r.right - 4, r.top + 14 + tick * 6), 1)

    if m.phase == 1:
        face = 1 if m.direction >= 0 else -1
        sway = math.sin(frame * 0.1) * 3
        add_glow(surface, cx + face * 3, r.top + 8, 16, (30, 10, 10))
        coat_points = [(cx - 20, r.bottom), (cx - 17, r.top + 25), (cx - 16 + sway, r.top + 18),
                       (cx - 8 + sway, r.top + 12), (cx + 1 + sway, r.top + 19),
                       (cx + 14 + sway, r.top + 14), (cx + 17 + sway, r.top + 24), (cx + 20, r.bottom)]
        pygame.draw.polygon(surface, body, coat_points)
        pygame.draw.lines(surface, (57, 51, 61), False, coat_points[1:-1], 2)
        pygame.draw.line(surface, (73, 67, 74), (cx + sway, r.top + 23), (cx + sway, r.bottom - 5), 1)
        pygame.draw.rect(surface, (63, 57, 67), (cx - 15, r.top - 5, 30, 23))
        pygame.draw.rect(surface, (160, 143, 118), (cx - 15, r.top - 5, 30, 23), 1)
        pygame.draw.line(surface, (9, 8, 12), (cx - 10, r.top + 1), (cx + 10, r.top + 1), 2)
        pygame.draw.line(surface, (9, 8, 12), (cx - 10, r.top + 6), (cx + 10, r.top + 6), 2)
        pygame.draw.rect(surface, (137, 35, 41), (cx - 3, r.top + 9, 6, 2))
        scan = int(frame * 1.3) % 26
        pygame.draw.line(surface, mix(body, (0, 0, 0), 0.3), (cx - 13, r.top - 4 + scan), (cx + 13, r.top - 4 + scan), 1)
        pygame.draw.circle(surface, (220, 42, 42), (cx + face * 2, r.top + 10), 2)

    elif m.phase == 2:
        charging = m.aligned and m.cooldown < 20
        add_glow(surface, cx, cy, 38 if charging else 25, (70, 14, 14) if charging else (30, 20, 50))
        # The outline remains visible even when the rest of the body breaks into tape lines.
        silhouette = [(cx - 20, r.bottom), (cx - 15, r.top + 20), (cx - 9, r.top + 11),
                      (cx + 8, r.top + 11), (cx + 17, r.top + 23), (cx + 20, r.bottom)]
        pygame.draw.lines(surface, (78, 67, 85), False, silhouette, 2)
        rows = 15
        for i in range(rows):
            t = i / (rows - 1)
            y = r.top + t * r.h
            tear = math.sin(frame * 0.2 + i * 1.1) * 4
            w = (22 - abs(t - 0.5) * 24)
            col = mix(body, (210, 115, 125) if m.aligned else (175, 170, 205),
                      0.48 + 0.28 * math.sin(frame * 0.1 + i))
            pygame.draw.line(surface, col, (cx - w + tear, y), (cx + w + tear, y), 3 if i % 4 == 0 else 2)
        for side in (-1, 1):
            shoulder = (cx + side * 15, r.top + 22)
            hand = (cx + side * 27 + int(math.sin(frame * 0.13) * 3), r.top + 38)
            pygame.draw.line(surface, (112, 99, 128), shoulder, hand, 2)
            pygame.draw.line(surface, (112, 99, 128), hand, (hand[0] + side * 5, hand[1] + 7), 1)
        lens = (230, 60, 60) if charging else (150, 150, 200)
        pygame.draw.circle(surface, (34, 31, 43), (cx, cy), 13, 2)
        pygame.draw.circle(surface, lens, (cx, cy), 8, 2)
        pygame.draw.circle(surface, (8, 7, 12), (cx, cy), 4)
        for side in (-1, 1):
            pygame.draw.line(surface, lens, (cx + side * 12, cy), (cx + side * 18, cy), 1)
        # A few separated fragments orbit its lens instead of a plain static oval.
        for bit in range(4):
            a = frame * 0.035 + bit * math.pi / 2
            bx = cx + math.cos(a) * 25
            by = cy + math.sin(a) * 25
            pygame.draw.rect(surface, (109, 92, 130), (int(bx), int(by), 3, 2))

    else:  # phase 3: chasing
        face = getattr(m, "face", 1)
        lean = face * 10
        add_glow(surface, cx + lean, cy, 25, (60, 10, 10))
        pygame.draw.polygon(surface, body, [(cx - 22, r.bottom), (cx + 22, r.bottom), (cx + 18 + lean, r.top + 14), (cx - 18 + lean, r.top + 14)])
        pygame.draw.polygon(surface, (25, 21, 28), [(cx - 22, r.top + 19), (cx - 11 + lean, r.top + 9),
                                                      (cx + 6 + lean, r.top + 13), (cx + 20 + lean, r.top + 25),
                                                      (cx + 17, r.bottom - 4), (cx - 20, r.bottom - 1)])
        pygame.draw.line(surface, (93, 45, 52), (cx + lean, r.top + 20), (cx + lean, r.bottom - 7), 2)
        for i in range(5):
            tx = cx - face * (14 + i * 7)
            pygame.draw.line(surface, mix(body, (190, 40, 40), 0.5 - i * 0.08), (tx, r.top + 10), (tx + lean * 0.3, r.bottom - 6), 3)
        pygame.draw.ellipse(surface, mix(body, (40, 10, 10), 0.5), (cx - 14 + lean, r.top - 6, 28, 26))
        pygame.draw.polygon(surface, (5, 5, 8), [(cx - 9 + lean, r.top + 1), (cx + 8 + lean, r.top),
                                                  (cx + 10 + lean, r.top + 12), (cx - 8 + lean, r.top + 12)])
        pygame.draw.rect(surface, (5, 4, 8), (cx - 13 + lean, r.top - 3, 26, 19))
        pygame.draw.rect(surface, (124, 106, 121), (cx - 13 + lean, r.top - 3, 26, 19), 1)
        for code in range(3):
            pygame.draw.line(surface, (197, 174, 151), (cx - 9 + lean, r.top + code * 5),
                             (cx + 9 + lean, r.top + code * 5), 1)
        pygame.draw.circle(surface, (235, 40, 40), (cx + face * 5 + lean, r.top + 6), 3)
        if m.exposed_timer > 0:
            pygame.draw.ellipse(surface, (218, 224, 214),
                                (cx + lean - 13, cy - 8, 26, 17), 1)
        # Pursuit tears loose strips of signed paper from its coat.
        if m.phase_timer < 50:
            for strip in range(3):
                sx = cx - face * (20 + strip * 6)
                flutter = int(math.sin(frame * 0.23 + strip) * 4)
                pygame.draw.polygon(surface, (164, 143, 127),
                                    [(sx, r.bottom - 17), (sx + 5, r.bottom - 14),
                                     (sx + 2 + flutter, r.bottom + 3), (sx - 3, r.bottom - 1)])
                pygame.draw.line(surface, (91, 53, 60), (sx, r.bottom - 10), (sx + 2, r.bottom - 7), 1)

    if glitch:
        dx = random.choice((-3, -2, 2, 3))
        pygame.draw.line(surface, (220, 50, 50), (r.left + dx, cy), (r.right + dx, cy), 1)
        pygame.draw.line(surface, (50, 190, 230), (r.left - dx, cy + 4), (r.right - dx, cy + 4), 1)


def draw_boss_door(surface, rect, state, frame):
    """A plain door-frame set into the wall. state: 'idle', 'telegraph' (about to activate) or 'manifest'
    (the figure has just stepped through). Purely scenery -- the game handles collisions separately."""
    pygame.draw.rect(surface, (20, 18, 24), rect.inflate(10, 10))
    if state == "telegraph":
        pulse = 0.5 + 0.5 * math.sin(frame * 0.6)
        pygame.draw.rect(surface, mix((60, 20, 20), (200, 40, 40), pulse), rect.inflate(10, 10), 3)
        add_glow(surface, rect.centerx, rect.centery, int(30 + 20 * pulse), (55, 10, 10))
    elif state == "manifest":
        add_glow(surface, rect.centerx, rect.centery, 50, (70, 65, 60))
        pygame.draw.rect(surface, (235, 230, 220), rect)
    pygame.draw.rect(surface, (7, 6, 9), rect)
    pygame.draw.rect(surface, (40, 36, 44), rect, 2)
    pygame.draw.line(surface, (40, 36, 44), (rect.centerx, rect.top), (rect.centerx, rect.bottom), 1)


def _doorstalker(surface, m, frame, player):
    """THE GLITCH: a door panel that reappears for a second targeted rush."""
    r = m.rect
    if m.state not in ("manifest", "exposed"):
        return
    cx, top, bot = r.centerx, r.top, r.bottom
    moving = m.state == "manifest"
    lean = int(m.dash_dir * (7 + 2 * math.sin(frame * 0.8))) if moving else 0
    body = (24, 17, 18)
    # A broken doorframe hangs behind its body, so the silhouette reads as architecture.
    pygame.draw.lines(surface, (74, 56, 51), False,
                      [(cx - 18, bot), (cx - 18, top + 7), (cx - 11, top - 8),
                       (cx + 11, top - 8), (cx + 18, top + 7), (cx + 18, bot)], 3)
    pygame.draw.polygon(surface, body, [(cx - 11 + lean, bot), (cx + 11 + lean, bot),
                                        (cx + 9 + lean, top + 10), (cx + 7 + lean, top),
                                        (cx - 8 + lean, top + 2)])
    # Scored timber grain, a splintered repair seam, and mismatched old varnish.
    for i in range(5):
        gy = top + 38 + i * 5
        pygame.draw.line(surface, (47, 32, 31), (cx - 7 + lean, gy), (cx + 7 + lean, gy + (i % 2)), 1)
    pygame.draw.line(surface, (91, 62, 49), (cx - 3 + lean, top + 31), (cx - 1 + lean, bot - 8), 1)
    pygame.draw.polygon(surface, (58, 42, 38), [(cx + 4 + lean, top + 25), (cx + 8 + lean, top + 28),
                                                (cx + 6 + lean, top + 37)], 1)
    for bolt_y in (top + 7, bot - 9):
        pygame.draw.circle(surface, (173, 133, 78), (cx + lean, bolt_y), 2)
        pygame.draw.line(surface, (45, 32, 29), (cx + lean - 1, bolt_y), (cx + lean + 1, bolt_y), 1)
    pygame.draw.polygon(surface, (54, 35, 33), [(cx - 7 + lean, top + 15),
                                                (cx + 7 + lean, top + 15),
                                                (cx + 8 + lean, bot - 7), (cx - 8 + lean, bot - 7)], 1)
    # The keyhole is vertical and much too deep; a little brass glint is the only eye.
    pygame.draw.circle(surface, (4, 4, 6), (cx + lean, top + 15), 5)
    pygame.draw.polygon(surface, (4, 4, 6), [(cx + lean - 3, top + 17),
                                             (cx + lean + 3, top + 17),
                                             (cx + lean + 2, top + 28),
                                             (cx + lean - 2, top + 28)])
    pygame.draw.circle(surface, (181, 139, 79) if m.state == "exposed" else (111, 66, 53),
                       (cx + lean, top + 14), 2)
    # Hinges work like elbows. During the dash the arms lag behind; on a miss they hang open.
    lag = -m.dash_dir * 8 if moving else 0
    for side in (-1, 1):
        shoulder = (cx + side * 8 + lean, top + 25)
        elbow = (cx + side * 15 + lag, top + 34 + int(math.sin(frame * 0.18 + side) * 2))
        wrist = (cx + side * 10 + lag, bot - 2)
        pygame.draw.lines(surface, (38, 29, 29), False, [shoulder, elbow, wrist], 4)
        pygame.draw.circle(surface, (135, 103, 76), elbow, 3)
        pygame.draw.rect(surface, (134, 94, 66), (elbow[0] - 3, elbow[1] - 2, 6, 4))
        for finger in (-1, 0, 1):
            pygame.draw.line(surface, (42, 31, 31), wrist,
                             (wrist[0] + side * (5 + finger * 2), wrist[1] + 5 + abs(finger) * 2), 1)
    for i in range(3):
        pygame.draw.circle(surface, (122, 99, 75), (cx - 7 + lean, top + 35 + i * 11), 1)
    if moving:
        for i in range(1, 4):
            tx = cx - m.dash_dir * (i * 10)
            pygame.draw.line(surface, (47, 38, 39), (tx, top + 6), (tx, bot - 4), max(1, 4 - i))
    if m.state == "exposed":
        pulse = int(110 + 80 * (0.5 + 0.5 * math.sin(frame * 0.3)))
        pygame.draw.line(surface, (pulse, 174, 125), (cx + lean, top + 30), (cx + lean, bot - 7), 2)


def _glitch_offset(surface, poly, frame, seed, color, chance=0.10):
    """Occasionally draws a torn, color-split copy of a shape a few pixels off -- a cheap VHS glitch."""
    if random.random() < chance:
        dx = random.choice((-3, -2, 2, 3))
        pygame.draw.polygon(surface, mix(color, (255, 40, 40), 0.5), [(x + dx, y) for x, y in poly], 1)
        pygame.draw.polygon(surface, mix(color, (40, 200, 255), 0.5), [(x - dx, y) for x, y in poly], 1)


def _patroller(surface, m, frame, player):
    """DESIGNATION 01. A figure in a plain grey coverall with no face -- just a smooth, blank oval.
    It repeats the same walk exactly, every time, and occasionally flickers like a bad tape."""
    r = m.rect
    face = 1 if m.direction >= 0 else -1
    step = math.sin(frame * 0.35)
    cx = r.centerx
    top_y = r.y - 4
    body = mix((60, 58, 66), (0, 0, 0), 0.0)
    torso = [(cx - 10, r.bottom - 2), (cx + 10, r.bottom - 2), (cx + 9, top_y + 14), (cx - 9, top_y + 14)]
    pygame.draw.polygon(surface, body, torso)
    _glitch_offset(surface, torso, frame, cx, body)
    pygame.draw.rect(surface, (35, 34, 40), (cx - 9 + step * 4 * face, r.bottom - 5, 6, 5))
    pygame.draw.rect(surface, (35, 34, 40), (cx + 3 - step * 4 * face, r.bottom - 5, 6, 5))
    pygame.draw.rect(surface, mix(body, (0, 0, 0), 0.15), (cx - 12 - step * 2, top_y + 16, 5, 14))
    pygame.draw.rect(surface, mix(body, (0, 0, 0), 0.15), (cx + 7 + step * 2, top_y + 16, 5, 14))
    head_c = (222, 216, 208)
    pygame.draw.ellipse(surface, head_c, (cx - 8, top_y - 2, 16, 18))
    scan = int(frame * 1.7) % 18
    pygame.draw.line(surface, mix(head_c, (0, 0, 0), 0.25), (cx - 8, top_y - 2 + scan), (cx + 8, top_y - 2 + scan), 1)
    distance = math.hypot(player.centerx - cx, player.centery - (top_y + 6)) if player else 999
    if distance < 190 or (frame // 5 + int(m.x)) % 90 < 3:
        gaze = -1 if player and player.centerx < cx else 1
        for dx in (-4, 4):
            pygame.draw.ellipse(surface, (5, 3, 8), (cx + dx - 2, top_y + 4, 4, 5))
            pygame.draw.circle(surface, (230, 225, 220), (cx + dx + gaze, top_y + 6), 1)
    # A blank, upside-down badge and a seam where a mouth should be.
    pygame.draw.line(surface, (35, 32, 37), (cx - 2, top_y + 17), (cx + 2, top_y + 17), 1)
    pygame.draw.rect(surface, (91, 88, 92), (cx - 3, top_y + 24, 6, 7), 1)


def _flyer(surface, m, frame, player):
    """DESIGNATION 02. A shape made of broken scanlines, roughly the outline of a person, hanging
    where it should not be able to hang. It has no wings -- it just does not fall."""
    r = m.rect
    cx, cy = r.centerx, r.centery
    wailing = m.wail_cooldown > 560 or getattr(m, "dive_state", "idle") == "warning"
    add_glow(surface, cx, cy, 22, (18, 18, 32))
    rows = 13
    for i in range(rows):
        t = i / (rows - 1)
        y = cy - 20 + t * 40
        tear = math.sin(frame * 0.22 + i * 1.3) * (3 if wailing else 1.4)
        width = (10 - abs(t - 0.5) * 14) * (1 if random.random() > 0.06 else 0.3)
        col = mix((18, 18, 30), (215, 215, 235), clamp(0.4 + 0.5 * math.sin(frame * 0.1 + i), 0.0, 1.0))
        pygame.draw.line(surface, col, (cx - width + tear, y), (cx + width + tear, y), 2)
    # The shape's arms only resolve on alternating frames; there are no wings to explain the hover.
    if frame % 8 < 6:
        arm_col = (110, 112, 132) if not wailing else (172, 46, 55)
        for side in (-1, 1):
            pts = [(cx + side * 7, cy - 2), (cx + side * 13, cy + 10),
                   (cx + side * 12, cy + 25), (cx + side * 17, cy + 34)]
            pygame.draw.lines(surface, arm_col, False, pts, 2)
    if random.random() < 0.08:
        dx = random.choice((-4, -3, 3, 4))
        yb = cy + random.randint(-16, 16)
        pygame.draw.line(surface, (230, 60, 60), (cx - 10 + dx, yb), (cx + 10 + dx, yb), 1)
        pygame.draw.line(surface, (60, 200, 230), (cx - 10 - dx, yb), (cx + 10 - dx, yb), 1)
    for dx in (-4, 4):
        pygame.draw.rect(surface, (5, 5, 8), (cx + dx - 1, cy - 8, 3, 6 if wailing else 3))
    if getattr(m, "dive_state", "idle") == "warning":
        progress = 1.0 - clamp(getattr(m, "dive_warning", 54) / 54.0, 0.0, 1.0)
        red = int(105 + 140 * progress)
        for i in range(1 + int(progress * 4)):
            yy = cy + 21 + i * 4
            half = 10 + i * 3 + int(progress * 7)
            pygame.draw.line(surface, (red, 25, 42), (cx - half, yy), (cx + half, yy), 1 + int(progress * 2))
        for side in (-1, 1):
            length = 5 + int(progress * 9)
            pygame.draw.line(surface, (red, 45, 55), (cx + side * 25, cy + 43),
                             (cx + side * (25 - length), cy + 43 - length), 2)


def _chaser(surface, m, frame, player):
    """DESIGNATION 03. Sits perfectly still, head down, arms around its knees. It does not breathe
    visibly. When it wakes it unfolds all at once and covers ground far too fast for its stride."""
    r = m.rect
    face = getattr(m, "face", 1)
    cx, by = r.centerx, r.bottom
    col = (31, 29, 37)
    edge = (91, 86, 99)
    progress = getattr(m, "wake_progress", 1.0 if m.awake else 0.0)
    if progress < 1.0:
        twitch = 1 if (frame // 130 + int(m.x)) % 55 == 0 else 0
        # Folded low like a patient hiding under a blanket, with arms circling its knees.
        pygame.draw.ellipse(surface, col, (cx - 15, r.y + 9 - twitch, 30, 31))
        pygame.draw.arc(surface, edge, (cx - 15, r.y + 9 - twitch, 30, 31), math.pi * 1.02, math.pi * 1.92, 2)
        reveal = clamp(progress / 0.72, 0.0, 1.0)
        head_y = int((r.y + 13) * (1.0 - reveal) + (r.y - 24) * reveal)
        head_x = cx - face * int(8 * reveal)
        pygame.draw.ellipse(surface, (24, 21, 28), (head_x - 9, head_y - 9, 18, 18))
        pygame.draw.arc(surface, edge, (cx - 12, r.y + 12, 24, 23), math.pi * 1.05, math.pi * 1.95, 2)
        pygame.draw.line(surface, edge, (cx - 11, r.bottom - 4), (cx + 11, r.bottom - 4), 2)
        eye_color = (int(49 + 150 * reveal), 26, 31)
        pygame.draw.circle(surface, eye_color if twitch or reveal > 0.42 else (49, 26, 31), (head_x, head_y), 2)
        if reveal > 0.55:
            pygame.draw.line(surface, edge, (cx, r.y + 15), (head_x, head_y + 7), 2)
        for k in range(3):
            t = (frame * 0.015 + k * 0.33) % 1.0
            zx, zy = cx + 12 + t * 10, r.y - 6 - t * 22
            pygame.draw.circle(surface, mix((0, 0, 0), (140, 130, 150), 1 - t), (int(zx), int(zy)), 2)
        return
    # On waking, the body pulls upright but the arms still drag at the floor.
    shoulders, hips = r.y + 3, r.y + 24
    head_x, head_y = cx - face * 8, r.y - 24
    torso = [(cx - 7, hips), (cx + 7, hips), (cx + 6, shoulders + 4), (cx - 6, shoulders)]
    pygame.draw.polygon(surface, col, torso)
    pygame.draw.lines(surface, edge, False, [(cx - 6, shoulders + 3), (cx - 4, r.y + 14), (cx + 3, hips - 2)], 2)
    pygame.draw.line(surface, col, (cx - 4, hips), (cx - 10, by), 5)
    pygame.draw.line(surface, col, (cx + 4, hips), (cx + 11, by - 2), 5)
    pygame.draw.line(surface, edge, (cx - 10, by - 3), (cx - 5, by - 1), 1)
    pygame.draw.line(surface, edge, (cx + 8, by - 5), (cx + 13, by - 3), 1)
    elbow = (cx - face * 17, r.y + 13)
    wrist = (cx - face * 24, by - 1)
    far_elbow = (cx + face * 13, r.y + 18)
    far_wrist = (cx + face * 20, by - 6)
    pygame.draw.lines(surface, col, False, [(cx - face * 5, shoulders), elbow, wrist], 4)
    pygame.draw.lines(surface, col, False, [(cx + face * 5, shoulders + 3), far_elbow, far_wrist], 3)
    pygame.draw.circle(surface, edge, wrist, 2)
    pygame.draw.circle(surface, edge, far_wrist, 2)
    # The head sits too high and too far to one side, as if the joints were spliced.
    pygame.draw.line(surface, edge, (cx + face * 2, shoulders + 2), (head_x, head_y + 7), 2)
    pygame.draw.circle(surface, col, (head_x, head_y), 9)
    pygame.draw.ellipse(surface, (6, 5, 8), (head_x - 5, head_y - 1, 10, 4))
    pygame.draw.line(surface, (215, 24, 25), (head_x - 4, head_y), (head_x + 4, head_y), 2)
    add_glow(surface, head_x, head_y, 14, (55, 6, 6))


def _shooter(surface, m, frame, player):
    """DESIGNATION 04. A camera on a tripod. Its monitor shows a live, slightly delayed feed of
    whoever is standing in front of it. The red light means it is recording. It always means that."""
    r = m.rect
    cx, cy = r.centerx, r.centery - 2
    pygame.draw.line(surface, (40, 40, 44), (cx - 10, r.bottom), (cx - 3, cy + 12), 2)
    pygame.draw.line(surface, (40, 40, 44), (cx + 10, r.bottom), (cx + 3, cy + 12), 2)
    pygame.draw.line(surface, (40, 40, 44), (cx, r.bottom), (cx, cy + 12), 2)
    charging = m.aligned and m.cooldown < 25
    if m.aligned:
        add_glow(surface, cx, cy, 30 if charging else 20, (60, 8, 8) if charging else (10, 10, 10))
    pygame.draw.rect(surface, (30, 30, 34), (r.x, cy - 13, r.w, 26), border_radius=3)
    pygame.draw.rect(surface, (18, 18, 20), (r.x, cy - 13, r.w, 26), 2, border_radius=3)
    screen_r = pygame.Rect(r.x + 4, cy - 9, r.w - 8, 18)
    pygame.draw.rect(surface, (10, 40, 16), screen_r)
    px = player.centerx - r.x
    silh = clamp(px * screen_r.w / 800, 2, screen_r.w - 2)
    sy = clamp((player.centery / 500) * screen_r.h, 2, screen_r.h - 2)
    # Its tiny green monitor shows the player's live position, not a generic scan bar.
    pygame.draw.line(surface, (28, 94, 56), (screen_r.x + 2, screen_r.y + sy), (screen_r.right - 2, screen_r.y + sy), 1)
    pygame.draw.ellipse(surface, (72, 205, 115), (screen_r.x + silh - 2, screen_r.y + sy - 3, 4, 6))
    pygame.draw.circle(surface, (12, 20, 15), (screen_r.centerx, screen_r.centery), 2, 1)
    if random.random() < 0.15:
        ny = screen_r.y + random.randint(1, screen_r.h - 2)
        pygame.draw.line(surface, (140, 255, 170), (screen_r.x, ny), (screen_r.right, ny), 1)
    rec_on = (frame // 15) % 2 == 0
    if charging or rec_on:
        pygame.draw.circle(surface, (230, 30, 30), (r.right - 3, cy - 10), 3)
    if (frame + int(m.x)) % 220 < 4:                            # a slow mechanical blink of the lens cover
        pygame.draw.rect(surface, (30, 30, 34), screen_r)


# ------------------------------------------------------------------
# jumpscares
# ------------------------------------------------------------------
def draw_jumpscare(surface, frame, big=True, boss_kind=None):
    """A distorted, too-wide face that fills most of the screen for a moment. Drawn straight onto
    the picture, no separate picture -- safe to call mid-frame at any point."""
    surface.fill((6, 5, 8))
    cx, cy = W // 2, H // 2
    jitter = random.randint(-10, 10) if big else random.randint(-4, 4)
    scale = 1.0 if big else 0.6
    add_glow(surface, cx, cy, int(280 * scale), (60, 15, 15))         # ambient light BEHIND the face, drawn first
    w, h = int(260 * scale), int(300 * scale)
    face = pygame.Rect(cx - w // 2 + jitter, cy - h // 2, w, h)
    palette = {"doorstalker": (143, 126, 112), "beamer": (123, 137, 151),
               "summoner": (160, 133, 115), "guardian": (139, 126, 99),
               "warden": (153, 126, 139), "secret_boss": (125, 112, 96)}
    skin = palette.get(boss_kind, (205, 195, 190))
    pygame.draw.ellipse(surface, skin, face)
    for _ in range(6 if big else 3):                             # torn scanlines across the face
        y = random.randint(face.top, face.bottom)
        dx = random.randint(-30, 30)
        pygame.draw.rect(surface, mix(skin, (0, 0, 0), 0.4), (face.left, y, face.w, random.randint(2, 6)))
        pygame.draw.line(surface, (230, 50, 50), (face.left + dx, y), (face.right + dx, y), 1)
        pygame.draw.line(surface, (50, 200, 230), (face.left - dx, y + 2), (face.right - dx, y + 2), 1)
    eye_w, eye_h = int(34 * scale), int(50 * scale)
    for ex in (cx - w // 4, cx + w // 4):
        pygame.draw.ellipse(surface, (5, 5, 6), (ex - eye_w // 2 + jitter, cy - int(30 * scale), eye_w, eye_h))
    mouth = pygame.Rect(cx - int(70 * scale) + jitter, cy + int(50 * scale), int(140 * scale), int(70 * scale))
    pygame.draw.ellipse(surface, (10, 6, 8), mouth)
    for i in range(9 if big else 5):
        tx = mouth.left + i * mouth.w / (9 if big else 5)
        pygame.draw.line(surface, (235, 230, 220), (tx, mouth.top), (tx, mouth.top + int(14 * scale)), 2)
    for _ in range(3 if big else 1):                              # a couple of extra glitch bars, direct draws only
        y = random.randint(0, H - 10)
        pygame.draw.rect(surface, mix(skin, (0, 0, 0), 0.5), (0, y, W, random.randint(3, 8)))
    # Each boss reveal carries a visual cue from its room design.
    if boss_kind == "doorstalker":
        pygame.draw.line(surface, (35, 22, 22), (cx, face.top), (cx, face.bottom), 9)
        pygame.draw.circle(surface, (210, 45, 40), (cx, cy), 10)
        for y in (cy - 55, cy + 55):
            pygame.draw.circle(surface, (46, 35, 31), (cx - 82, y), 8)
            pygame.draw.circle(surface, (46, 35, 31), (cx + 82, y), 8)
    elif boss_kind == "beamer":
        pygame.draw.circle(surface, (18, 22, 30), (cx, cy), 72, 13)
        pygame.draw.circle(surface, (220, 50, 47), (cx, cy), 24, 7)
        pygame.draw.line(surface, (210, 48, 48), (0, cy), (W, cy), 3)
    elif boss_kind == "summoner":
        for dx in range(-72, 73, 24):
            pygame.draw.circle(surface, (222, 214, 196), (cx + dx, face.top + 27), 15)
            pygame.draw.circle(surface, (39, 31, 32), (cx + dx, face.top + 27), 15, 3)
        pygame.draw.line(surface, (181, 148, 99), (cx - 90, cy - 7), (cx + 90, cy - 7), 5)
        pygame.draw.line(surface, (181, 148, 99), (cx, cy - 9), (cx, cy + 26), 4)
        for dx in (-60, 60):
            pygame.draw.line(surface, (181, 148, 99), (cx + dx, cy - 7), (cx + dx, cy + 39), 2)
            pygame.draw.arc(surface, (226, 205, 163), (cx + dx - 33, cy + 28, 66, 25), 0, math.pi, 4)
        pygame.draw.line(surface, (130, 78, 49), (cx + 62, cy - 5), (cx + 112, cy - 60), 13)
        pygame.draw.rect(surface, (189, 148, 102), (cx + 91, cy - 82, 43, 20), border_radius=5)
        pygame.draw.ellipse(surface, (226, 43, 44), (cx - 34, cy + 66, 68, 20), 4)
    elif boss_kind == "guardian":
        for dx in (-92, -48, 48, 92):
            pygame.draw.line(surface, (40, 34, 28), (cx + dx, cy - 30), (cx + int(dx * 1.35), face.bottom), 13)
        pygame.draw.rect(surface, (38, 32, 28), (cx - 112, cy - 40, 224, 82), 10)
    elif boss_kind == "warden":
        for dx in (-115, 115):
            for dy in range(-105, 106, 28):
                pygame.draw.circle(surface, (31, 25, 34), (cx + dx, cy + dy), 6)
        pygame.draw.rect(surface, (225, 218, 202), (cx - 46, cy - 64, 92, 128), 3)
        for dy in (-30, 0):
            pygame.draw.line(surface, (182, 37, 45), (cx - 34, cy + dy), (cx + 34, cy + dy), 4)
    elif boss_kind == "secret_boss":
        pygame.draw.rect(surface, (23, 21, 24), (cx - 92, cy - 104, 184, 218), 8)
        pygame.draw.rect(surface, (178, 147, 102), (cx - 92, cy - 104, 184, 218), 3)
        pygame.draw.circle(surface, (8, 8, 10), (cx, cy - 29), 38)
        pygame.draw.circle(surface, (183, 49, 55), (cx, cy - 29), 22, 6)
        pygame.draw.circle(surface, (240, 225, 191), (cx, cy - 29), 5)
        for dy in (31, 60, 89):
            pygame.draw.line(surface, (182, 156, 111), (cx - 60, cy + dy), (cx + 60, cy + dy), 3)
            pygame.draw.line(surface, (45, 37, 34), (cx - 60, cy + dy + 8), (cx + 42, cy + dy + 8), 2)


def jumpscare_sequence(screen, clock, frames=16, big=True, boss_kind=None):
    """Blocks for a moment and shows the scare face. Call this the way analog.static_burst is called."""
    for _ in range(frames):
        pygame.event.pump()
        draw_jumpscare(screen, 0, big, boss_kind)
        pygame.display.flip()
        clock.tick(60)


def draw_surveillance_overlay(surface, frame, boss_kind, phase=1):
    """CCTV framing makes boss rooms feel like watched footage."""
    w, h = surface.get_size()
    edge = (104, 40, 43) if phase >= 3 else (72, 70, 75)
    pygame.draw.rect(surface, edge, (8, 8, w - 16, h - 16), 2)
    for x, sx in ((14, 1), (w - 14, -1)):
        for y, sy in ((14, 1), (h - 14, -1)):
            pygame.draw.line(surface, edge, (x, y), (x + sx * 19, y), 3)
            pygame.draw.line(surface, edge, (x, y), (x, y + sy * 19), 3)
    if frame % 60 < 42:
        pygame.draw.circle(surface, (205, 38, 38), (w - 34, 28), 5)
    if phase >= 3 or boss_kind in ("doorstalker", "guardian"):
        y = (frame * 13) % h
        pygame.draw.line(surface, (105, 48, 50), (12, y), (w - 12, y), 1)


# ------------------------------------------------------------------
# Run this file by itself to see the pictures:  python3 visuals.py   (Left/Right = chapter, Esc quits)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import json, os
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    clock = pygame.time.Clock()
    here = os.path.dirname(os.path.abspath(__file__))
    chapters = json.load(open(os.path.join(here, "data", "chapters.json")))
    names = list(chapters)
    ch, frame = 0, 0
    bg = Background(chapters[names[0]], 0, 1, 0, 8)
    particles, sprite = Particles(), PlayerSprite()
    px = 400
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                running = False
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                ch = (ch + (1 if e.key == pygame.K_RIGHT else -1)) % len(names)
                bg = Background(chapters[names[ch]], ch, ch * 9 + 3, 4, 8)
        keys = pygame.key.get_pressed()
        move = (keys[pygame.K_d] or keys[pygame.K_a]) and 1
        px = clamp(px + (keys[pygame.K_d] - keys[pygame.K_a]) * 4, 30, 770)
        frame += 1
        screen.fill((0, 0, 0))
        bg.draw(screen, frame, px)
        draw_platform(screen, pygame.Rect(0, 460, 800, 40), chapters[names[ch]], frame)
        rect = pygame.Rect(int(px) - 14, 420, 28, 40)
        sprite.update(rect, 0, True, move, 1, 0, frame, particles)
        sprite.draw(screen, rect, 1, 0, frame)
        particles.update()
        particles.draw(screen)
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
