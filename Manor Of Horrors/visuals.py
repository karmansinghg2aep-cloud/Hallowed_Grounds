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
        self.stars = [(x + 20, y, rng.uniform(0, 6.28)) for (x, y) in self.chapter.get("stars", [])]
        self.stars += [(rng.randint(0, W), rng.randint(10, 250), rng.uniform(0, 6.28)) for _ in range(30)]
        self.buildings = []
        self.windows = []
        x = -10
        while x < W + 20:
            w, h = rng.randint(55, 110), rng.randint(40, 105)
            top = 462 - h
            kind = rng.random()
            self.buildings.append((x, top, w, h, kind, rng.randint(18, 40)))
            for wx in range(x + 10, x + w - 12, 22):
                for wy in range(top + 12, top + h - 8, 26):
                    if rng.random() < 0.28:
                        self.windows.append((wx, wy, rng.uniform(0, 6.28)))
            x += w + rng.randint(-10, 8)
        self.tall_windows = [rng.randint(90, 170), rng.randint(330, 420), rng.randint(560, 650)]
        self.portraits = [(rng.randint(30, 720), rng.randint(60, 150)) for _ in range(rng.randint(2, 3))]

    def _draw_moonlit(self, surface, frame):
        h_gradient(surface, mix(self.sky, (0, 0, 0), 0.35), mix(self.sky, (85, 75, 120), 0.45), 0, 260)
        pygame.draw.rect(surface, mix(self.sky, (85, 75, 120), 0.45), (0, 260, W, H - 260))
        mx, my = 730, 84
        add_glow(surface, mx, my, 90, (55, 50, 35))
        pygame.draw.circle(surface, self.accent, (mx, my), 34)
        pygame.draw.circle(surface, mix(self.sky, (0, 0, 0), 0.35), (mx + 14, my - 8), 30)
        for x, y, ph in self.stars:
            b = 150 + int(90 * math.sin(frame * 0.05 + ph))
            surface.fill((b, b, b - 30), (x, y, 2, 2))
        col = mix(self.sky, (0, 0, 0), 0.55)
        for x, top, w, h, kind, spike in self.buildings:
            pygame.draw.rect(surface, col, (x, top, w, h + 10))
            if kind < 0.4:
                pygame.draw.polygon(surface, col, [(x - 4, top), (x + w + 4, top), (x + w // 2, top - spike)])
            elif kind < 0.6:
                pygame.draw.rect(surface, col, (x + w // 2 - 7, top - 45, 14, 46))
                pygame.draw.polygon(surface, col, [(x + w // 2 - 10, top - 45), (x + w // 2 + 10, top - 45), (x + w // 2, top - 66)])
        for wx, wy, ph in self.windows:
            if math.sin(frame * 0.02 + ph * 3) > -0.3:
                surface.fill((215, 170, 80), (wx, wy, 5, 7))
        for wx in self.tall_windows:
            win = pygame.Rect(wx, 120, 54, 130)
            beam = mix(self.sky, (190, 190, 150), 0.12)
            pygame.draw.polygon(surface, beam, [(win.x + 6, win.bottom), (win.right - 6, win.bottom), (win.right + 90, 460), (win.x - 60, 460)])
            frame_col = mix(self.sky, (0, 0, 0), 0.55)
            pygame.draw.rect(surface, frame_col, win.inflate(10, 10), border_radius=4)
            pygame.draw.rect(surface, mix(self.sky, (140, 150, 190), 0.35), win, border_top_left_radius=27, border_top_right_radius=27)
            pygame.draw.line(surface, frame_col, (win.centerx, win.y), (win.centerx, win.bottom), 2)
            pygame.draw.line(surface, frame_col, (win.x, win.y + 60), (win.right, win.y + 60), 2)
        for fx, fy in self.portraits:
            pygame.draw.rect(surface, (58, 44, 40), (fx, fy, 34, 44))
            pygame.draw.rect(surface, (12, 10, 14), (fx + 4, fy + 4, 26, 36))
            pygame.draw.circle(surface, (30, 26, 34), (fx + 17, fy + 16), 7)
            pygame.draw.ellipse(surface, (30, 26, 34), (fx + 8, fy + 24, 18, 16))

    # ---------- Tape 2: the old hallways (cobweb) ----------
    def _layout_cobweb(self):
        rng = self.rng
        self.stripe_x = list(range(0, W + 20, 30))
        self.doors = [rng.randint(60, 140), rng.randint(360, 440), rng.randint(600, 690)]
        self.pictures = [(rng.randint(30, 720), rng.randint(60, 170), rng.randint(-4, 4)) for _ in range(3)]
        self.torches = [(150, 250), (650, 250)]
        self.spider = [rng.randint(120, 680), 0.0, 1]

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
            pygame.draw.rect(surface, (60, 44, 34), (sx - 5, sy, 10, 22))
            pygame.draw.rect(surface, (90, 70, 40), (sx - 9, sy - 4, 18, 6))
            flame(surface, sx, sy - 4, frame, sx, 0.7, (255, 190, 90))
        cx = 400 + math.sin(frame * 0.02) * 10
        pygame.draw.line(surface, (70, 60, 50), (400, 0), (cx, 92), 2)
        pygame.draw.arc(surface, (110, 95, 60), (cx - 46, 86, 92, 34), math.pi, math.tau, 3)
        for dx in (-46, -23, 0, 23, 46):
            flame(surface, cx + dx, 92 + (16 - abs(dx) * 0.28), frame, dx, 0.45)
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
            pygame.draw.rect(surface, (60, 42, 30), (tx - 4, ty, 8, 30))
            pygame.draw.rect(surface, (95, 90, 96), (tx - 9, ty - 2, 18, 5))
            flame(surface, tx, ty - 2, frame, tx, 1.0)
            if frame % 9 == 0:
                self.motes.append([tx + random.uniform(-4, 4), ty - 20, random.uniform(0.6, 1.2), random.uniform(0, 6), 9])
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
        edge = int(clamp(pr * 60, 0, 60))
        if edge > 0:
            pygame.draw.rect(surface, mix(self.sky, (230, 235, 240), 0.5), (0, 0, edge, H))
            pygame.draw.rect(surface, mix(self.sky, (230, 235, 240), 0.5), (W - edge, 0, edge, H))
        monitor_line(surface, frame, self.sky, 0.35 + 0.5 * pr)

    # ---------- drawing ----------
    def draw(self, surface, frame, player_x=400):
        getattr(self, "_draw_" + self.style, lambda *a: None)(surface, frame)
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
    for k in range(1, 5):
        sign = -1 if pr["vx"] > 0 else 1
        pygame.draw.circle(surface, mix((0, 0, 0), (70, 140, 80), 1 - k * 0.2), (cx + sign * k * 5, cy), max(1, pr["size"] // 2 - k))
    add_glow(surface, cx, cy, 16, (25, 75, 34))
    pygame.draw.circle(surface, (70, 120, 70), (cx, cy), pr["size"] // 2 + 3)
    pygame.draw.circle(surface, (180, 250, 180), (cx, cy), pr["size"] // 2)


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

    def update(self, rect, vel_y, on_ground, move, facing, invincible, frame, particles):
        feet_x, feet_y = rect.centerx, rect.bottom
        if on_ground and not self.prev_ground and self.prev_vy > 3:          # landed
            self.squash = min(1.0, self.prev_vy / 10)
            particles.burst(feet_x, feet_y - 2, 6, (150, 145, 160), speed=1.6, life=18, size=2.5, gravity=-0.02)
        if self.prev_ground and not on_ground and vel_y < -5:                # jumped
            particles.burst(feet_x, feet_y - 2, 4, (150, 145, 160), speed=1.2, life=14, size=2, gravity=-0.02)
        self.moving = bool(move) and on_ground
        if self.moving:
            self.walk += 0.38
            if frame % 7 == 0:
                particles.emit(feet_x - facing * 8, feet_y - 2, -facing * 0.4, -0.2, 14, 2.2, (140, 135, 150))
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
        cx = rect.centerx
        base_y = rect.bottom - 4 * sy
        h = 46 * sy
        body_color = (150, 30, 30) if self.hurt else (228, 228, 238)
        scarf = (110, 15, 15) if self.hurt else (170, 42, 52)

        breathe = 0 if (self.moving or self.in_air) else int(round(math.sin(frame * 0.07)))
        wave = math.sin(frame * 0.25 + self.walk)
        top_y = base_y - h
        pygame.draw.polygon(surface, scarf, [
            (cx + 6 * sx, top_y + 17 * sy + breathe), (cx - 7 * sx, top_y + 15 * sy + breathe + wave * 3),
            (cx - 14 * sx, top_y + 21 * sy + breathe + wave * 4), (cx - 4 * sx, top_y + 23 * sy + breathe), (cx + 6 * sx, top_y + 22 * sy + breathe)])

        lift1 = max(0.0, math.sin(self.walk)) * 3 if self.moving else 0
        lift2 = max(0.0, -math.sin(self.walk)) * 3 if self.moving else 0
        leg_h = (5 if self.in_air else 8) * sy
        leg_lift = (3 if self.in_air else 0) * sy
        pygame.draw.rect(surface, (56, 52, 66), (cx - 8 * sx, top_y + (32 + lift1) * sy + leg_lift, 6, leg_h - lift1 * sy), border_radius=2)
        pygame.draw.rect(surface, (56, 52, 66), (cx + 2 * sx, top_y + (32 + lift2) * sy + leg_lift, 6, leg_h - lift2 * sy), border_radius=2)

        pygame.draw.rect(surface, body_color, (cx - 11 * sx, top_y + 14 * sy + breathe, 22 * sx, 20 * sy), border_radius=6)
        head_cx, head_cy = cx, top_y + 9 * sy + breathe
        pygame.draw.circle(surface, body_color, (int(head_cx), int(head_cy)), int(10 * sx))
        pygame.draw.rect(surface, scarf, (cx - 10 * sx, top_y + 17 * sy + breathe, 20 * sx, 4 * sy), border_radius=2)

        blinking = (frame % 190) < 6
        eye_dx = facing * (3 if abs(facing) > 0.01 else 0)
        for dx in (-4, 4):
            ex = head_cx + (dx + eye_dx) * sx
            if blinking:
                pygame.draw.line(surface, (25, 22, 32), (ex - 2, head_cy), (ex + 2, head_cy), 2)
            else:
                pygame.draw.ellipse(surface, (25, 22, 32), (ex - 2, head_cy - 3 * sy, 4, 6 * sy))


# ------------------------------------------------------------------
# monsters
# ------------------------------------------------------------------
def draw_monster(surface, m, frame, player):
    {"patroller": _patroller, "flyer": _flyer, "chaser": _chaser, "shooter": _shooter,
     "doorstalker": _doorstalker, "beamer": _beamer, "summoner": _summoner,
     "guardian": _guardian, "warden": _warden}.get(m.kind, _patroller)(surface, m, frame, player)


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
    """The Projector: an old television on a thin body. It stares along one row of the room and, after a
    warning, sends a beam of static straight across it. Touch it while charged and it goes dark."""
    if m.defeated:
        return
    r = m.rect
    cx, cy = r.centerx, r.centery
    add_glow(surface, cx, cy, 30, (35, 34, 60))                        # always faintly visible against a dark room
    pygame.draw.rect(surface, (60, 56, 68), (cx - 5, r.bottom - 18, 10, 18))
    pygame.draw.rect(surface, (60, 56, 68), (cx - 14, r.bottom - 4, 28, 4))
    pygame.draw.rect(surface, (86, 82, 96), r, border_radius=8)
    pygame.draw.rect(surface, (140, 134, 150), r, 3, border_radius=8)
    screen_r = r.inflate(-14, -14)
    lit = m.state in ("telegraph", "beam")
    base = (210, 215, 225) if m.state == "beam" else ((150, 50, 50) if m.state == "telegraph" else (55, 60, 70))
    pygame.draw.rect(surface, base, screen_r, border_radius=4)
    for _ in range(14 if lit else 5):
        nx = random.randint(screen_r.left, screen_r.right - 2)
        ny = random.randint(screen_r.top, screen_r.bottom - 2)
        v = random.randint(70, 255) if lit else random.randint(40, 90)
        pygame.draw.rect(surface, (v, v, v), (nx, ny, 3, 2))
    if m.state == "telegraph":
        pulse = 0.5 + 0.5 * math.sin(frame * 0.7)
        add_glow(surface, cx, cy, int(26 + 12 * pulse), (60, 12, 12))
        y = cy
        for x in range(0, W, 14):                                  # a dotted warning line across the whole row
            if x < r.left or x > r.right:
                pygame.draw.line(surface, mix((60, 20, 20), (230, 60, 60), pulse), (x, y), (x + 6, y), 2)
    beam = m.beam_rect
    if beam is not None:
        pygame.draw.rect(surface, (235, 238, 245), beam)
        for _ in range(60):
            nx = random.randint(0, W - 6)
            ny = beam.top + random.randint(0, max(1, beam.h - 2))
            v = random.randint(20, 120)
            pygame.draw.rect(surface, (v, v, v), (nx, ny, random.randint(4, 24), 2))
        add_glow(surface, cx, cy, 36, (70, 74, 82))


def _summoner(surface, m, frame, player):
    """The Caller: a hunched figure with its arms raised. A ring tightens above it just before it
    calls something in. Touch it while charged and the ring collapses."""
    if m.defeated:
        return
    r = m.rect
    cx, by = r.centerx, r.bottom
    add_glow(surface, cx, r.centery, 26, (40, 22, 55))                # always faintly visible against a dark room
    body = (68, 58, 80)
    sway = math.sin(frame * 0.05) * 2
    pygame.draw.polygon(surface, body, [(cx - 18, by), (cx + 18, by), (cx + 11 + sway, r.top + 20), (cx - 11 + sway, r.top + 20)])
    pygame.draw.line(surface, body, (cx - 9 + sway, r.top + 24), (cx - 24, r.top - 4 + math.sin(frame * 0.2) * 3), 4)
    pygame.draw.line(surface, body, (cx + 9 + sway, r.top + 24), (cx + 24, r.top - 4 - math.sin(frame * 0.2) * 3), 4)
    pygame.draw.ellipse(surface, body, (cx - 9 + sway, r.top + 6, 18, 20))
    pygame.draw.circle(surface, (230, 50, 50), (cx - 3 + int(sway), r.top + 16), 2)
    pygame.draw.circle(surface, (230, 50, 50), (cx + 4 + int(sway), r.top + 16), 2)
    soon = m.timer < 45                                            # about to summon: the ring closes in and brightens
    t = 1 - (m.timer / 45) if soon else 0
    ring_r = int(34 - 18 * t) if soon else 34
    ring_c = mix((60, 30, 90), (230, 120, 255), t) if soon else (70, 35, 100)
    pygame.draw.circle(surface, ring_c, (cx, r.top - 22), ring_r, 2)
    pygame.draw.circle(surface, ring_c, (cx, r.top - 22), max(3, ring_r - 8), 1)
    if soon:
        add_glow(surface, cx, r.top - 22, 20, (45, 20, 70))


def _guardian(surface, m, frame, player):
    """The Guardian: a squat, armored slab that plods back and forth. Its sides are lined with spikes,
    its top is a flat plate striped like a warning sign. The top is the only safe place to touch it."""
    if m.defeated:
        return
    r = m.rect
    face = 1 if m.direction >= 0 else -1
    pygame.draw.rect(surface, (44, 42, 50), r, border_radius=6)
    pygame.draw.rect(surface, (20, 19, 24), r, 3, border_radius=6)
    top = pygame.Rect(r.x - 3, r.y - 8, r.w + 6, 10)                # the flat stomp plate
    pygame.draw.rect(surface, (60, 58, 66), top, border_radius=3)
    for i in range(0, top.w, 12):
        pygame.draw.polygon(surface, (215, 185, 60), [(top.x + i, top.bottom), (top.x + i + 6, top.top), (top.x + i + 12, top.bottom)])
    pygame.draw.rect(surface, (20, 19, 24), top, 2, border_radius=3)
    for k in range(3):                                              # side spikes
        sy = r.y + 12 + k * 14
        pygame.draw.polygon(surface, (150, 150, 158), [(r.left, sy), (r.left - 9, sy + 5), (r.left, sy + 10)])
        pygame.draw.polygon(surface, (150, 150, 158), [(r.right, sy), (r.right + 9, sy + 5), (r.right, sy + 10)])
    ex = r.centerx + face * 8
    pygame.draw.circle(surface, (215, 40, 40), (ex, r.y + r.h // 2), 5)
    add_glow(surface, ex, r.y + r.h // 2, 14, (55, 10, 10))
    step = int(math.sin(frame * 0.2) * 3)
    pygame.draw.rect(surface, (20, 19, 24), (r.x + 8, r.bottom - 3 + step, 12, 5))
    pygame.draw.rect(surface, (20, 19, 24), (r.right - 20, r.bottom - 3 - step, 12, 5))


def _warden(surface, m, frame, player):
    """The Warden: never finished as its own Designation, so it is built from pieces of all four.
    Phase 1: a blank, oversized figure like 01. Phase 2: torn scanlines and a firing lens, like 02 and 04.
    Phase 3: the same shape, but chasing, with 03's red glow bleeding through the tears."""
    r = m.rect
    cx, cy = r.centerx, r.centery
    glitch = random.random() < (0.10 + 0.08 * m.phase)
    body = (16, 14, 20)

    if m.phase == 1:
        face = 1 if m.direction >= 0 else -1
        sway = math.sin(frame * 0.1) * 3
        pygame.draw.polygon(surface, body, [(cx - 20, r.bottom), (cx + 20, r.bottom), (cx + 16 + sway, r.top + 18), (cx - 16 + sway, r.top + 18)])
        pygame.draw.ellipse(surface, mix(body, (60, 56, 66), 0.6), (cx - 13, r.top - 4, 26, 28))
        scan = int(frame * 1.3) % 26
        pygame.draw.line(surface, mix(body, (0, 0, 0), 0.3), (cx - 13, r.top - 4 + scan), (cx + 13, r.top - 4 + scan), 1)
        add_glow(surface, cx + face * 3, r.top + 8, 16, (30, 10, 10))

    elif m.phase == 2:
        rows = 15
        for i in range(rows):
            t = i / (rows - 1)
            y = r.top + t * r.h
            tear = math.sin(frame * 0.2 + i * 1.1) * 4
            w = (22 - abs(t - 0.5) * 24)
            col = mix(body, (200, 90, 90) if m.aligned else (150, 150, 210), 0.35 + 0.4 * math.sin(frame * 0.1 + i))
            pygame.draw.line(surface, col, (cx - w + tear, y), (cx + w + tear, y), 2)
        charging = m.aligned and m.cooldown < 20
        add_glow(surface, cx, cy, 46 if charging else 30, (70, 14, 14) if charging else (30, 20, 50))
        pygame.draw.circle(surface, (230, 60, 60) if charging else (150, 150, 200), (cx, cy), 7)

    else:  # phase 3: chasing
        face = getattr(m, "face", 1)
        lean = face * 10
        pygame.draw.polygon(surface, body, [(cx - 22, r.bottom), (cx + 22, r.bottom), (cx + 18 + lean, r.top + 14), (cx - 18 + lean, r.top + 14)])
        for i in range(5):
            tx = cx - face * (14 + i * 7)
            pygame.draw.line(surface, mix(body, (190, 40, 40), 0.5 - i * 0.08), (tx, r.top + 10), (tx + lean * 0.3, r.bottom - 6), 3)
        pygame.draw.ellipse(surface, mix(body, (40, 10, 10), 0.5), (cx - 14 + lean, r.top - 6, 28, 26))
        pygame.draw.circle(surface, (235, 40, 40), (cx + face * 5 + lean, r.top + 6), 4)
        add_glow(surface, cx + lean, cy, 34, (60, 10, 10))

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
    """A tall, faceless figure that only exists for the moment it steps out of a door and dashes
    through the room. Deliberately blank -- there is nothing to recognize, only to avoid."""
    r = m.rect
    if m.state != "manifest":
        return                                                     # hidden or still behind the door: draw nothing
    cx, top, bot = r.centerx, r.top, r.bottom
    lean = m.dash_dir * 5
    body = (12, 11, 15)
    for i in range(4):                                              # a torn trail behind the dash
        tx = cx - m.dash_dir * (10 + i * 9)
        pygame.draw.line(surface, mix(body, (30, 28, 34), 1 - i * 0.2), (tx, top + 6), (tx + lean * 0.4, bot - 4), max(1, 4 - i))
    pygame.draw.polygon(surface, body, [(cx - 9, bot), (cx + 9, bot), (cx + 7 + lean, top + 14), (cx - 7 + lean, top + 14)])
    pygame.draw.line(surface, body, (cx - 7 + lean, top + 16), (cx - 9 + lean * 1.4, top + 40), 4)
    pygame.draw.line(surface, body, (cx + 7 + lean, top + 16), (cx + 9 + lean * 1.4, top + 40), 4)
    pygame.draw.ellipse(surface, body, (cx - 8 + lean, top, 16, 18))
    if random.random() < 0.4:
        dx = random.choice((-2, 2))
        pygame.draw.line(surface, (210, 50, 50), (cx - 8 + lean + dx, top + 8), (cx + 8 + lean + dx, top + 8), 1)
        pygame.draw.line(surface, (50, 190, 220), (cx - 8 + lean - dx, top + 10), (cx + 8 + lean - dx, top + 10), 1)


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
    if (frame // 5 + int(m.x)) % 90 < 3:
        for dx in (-4, 4):
            pygame.draw.circle(surface, (0, 0, 0), (cx + dx, top_y + 6), 2)


def _flyer(surface, m, frame, player):
    """DESIGNATION 02. A shape made of broken scanlines, roughly the outline of a person, hanging
    where it should not be able to hang. It has no wings -- it just does not fall."""
    r = m.rect
    cx, cy = r.centerx, r.centery
    wailing = m.wail_cooldown > 560
    add_glow(surface, cx, cy, 22, (18, 18, 32))
    rows = 13
    for i in range(rows):
        t = i / (rows - 1)
        y = cy - 20 + t * 40
        tear = math.sin(frame * 0.22 + i * 1.3) * (3 if wailing else 1.4)
        width = (10 - abs(t - 0.5) * 14) * (1 if random.random() > 0.06 else 0.3)
        col = mix((18, 18, 30), (215, 215, 235), clamp(0.4 + 0.5 * math.sin(frame * 0.1 + i), 0.0, 1.0))
        pygame.draw.line(surface, col, (cx - width + tear, y), (cx + width + tear, y), 2)
    if random.random() < 0.08:
        dx = random.choice((-4, -3, 3, 4))
        yb = cy + random.randint(-16, 16)
        pygame.draw.line(surface, (230, 60, 60), (cx - 10 + dx, yb), (cx + 10 + dx, yb), 1)
        pygame.draw.line(surface, (60, 200, 230), (cx - 10 - dx, yb), (cx + 10 - dx, yb), 1)
    for dx in (-4, 4):
        pygame.draw.rect(surface, (5, 5, 8), (cx + dx - 1, cy - 8, 3, 6 if wailing else 3))


def _chaser(surface, m, frame, player):
    """DESIGNATION 03. Sits perfectly still, head down, arms around its knees. It does not breathe
    visibly. When it wakes it unfolds all at once and covers ground far too fast for its stride."""
    r = m.rect
    face = getattr(m, "face", 1)
    cx, by = r.centerx, r.bottom
    col = mix((40, 36, 46), (0, 0, 0), 0.0)
    if not m.awake:
        twitch = 1 if (frame // 130 + int(m.x)) % 55 == 0 else 0
        pygame.draw.ellipse(surface, col, (r.x + 3, r.y + 10 - twitch, r.w - 6, r.h - 10))
        pygame.draw.circle(surface, mix(col, (0, 0, 0), 0.2), (cx, r.y + 9), 7)
        for k in range(3):
            t = (frame * 0.015 + k * 0.33) % 1.0
            zx, zy = cx + 12 + t * 10, r.y - 6 - t * 22
            pygame.draw.circle(surface, mix((0, 0, 0), (140, 130, 150), 1 - t), (int(zx), int(zy)), 2)
        return
    pygame.draw.line(surface, col, (cx, by), (cx - face * 12, r.y + 6), 7)
    stride = math.sin(frame * 0.6) * 10
    pygame.draw.line(surface, col, (cx - 4, by), (cx - 4 + stride, by + 5), 4)
    pygame.draw.line(surface, col, (cx + 4, by), (cx + 4 - stride, by + 5), 4)
    pygame.draw.line(surface, col, (cx - face * 10, r.y + 6), (cx - face * 4 + math.sin(frame * 0.6) * 6, r.y - 6), 5)
    pygame.draw.line(surface, col, (cx - face * 10, r.y + 6), (cx - face * 16 - math.sin(frame * 0.6) * 6, r.y + 2), 5)
    hx, hy = cx - face * 10, r.y - 4
    pygame.draw.circle(surface, col, (hx, hy), 7)
    pygame.draw.line(surface, (215, 15, 15), (hx - 4, hy - 1), (hx + 4, hy - 1), 1)
    add_glow(surface, hx, hy, 14, (55, 6, 6))


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
    pygame.draw.rect(surface, (60, 220, 90), (screen_r.x + silh - 1, screen_r.y + 3, 2, screen_r.h - 6))
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
def draw_jumpscare(surface, frame, big=True):
    """A distorted, too-wide face that fills most of the screen for a moment. Drawn straight onto
    the picture, no separate picture -- safe to call mid-frame at any point."""
    surface.fill((6, 5, 8))
    cx, cy = W // 2, H // 2
    jitter = random.randint(-10, 10) if big else random.randint(-4, 4)
    scale = 1.0 if big else 0.6
    add_glow(surface, cx, cy, int(280 * scale), (60, 15, 15))         # ambient light BEHIND the face, drawn first
    w, h = int(260 * scale), int(300 * scale)
    face = pygame.Rect(cx - w // 2 + jitter, cy - h // 2, w, h)
    skin = (205, 195, 190)
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


def jumpscare_sequence(screen, clock, frames=16, big=True):
    """Blocks for a moment and shows the scare face. Call this the way analog.static_burst is called."""
    for _ in range(frames):
        pygame.event.pump()
        draw_jumpscare(screen, 0, big)
        pygame.display.flip()
        clock.tick(60)


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