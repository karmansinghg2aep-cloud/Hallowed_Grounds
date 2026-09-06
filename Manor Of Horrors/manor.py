"""
HAUNTED MANSION ESCAPE - Main Engine
------------------------------------------
A data-driven room system: the ROOMS list at the bottom holds every
room's layout. To add a new room later, you just add a new entry to
that list - you don't need to touch the engine code above it.

Two reusable monster behaviors power every monster in the game:
- "patroller": walks back and forth between two x positions, ignores you
- "chaser": sleeps until you're close, then chases you

Different monsters (werewolf, vampire, zombie, etc.) are just these
two behaviors with different colors, speeds, and names.
"""

import pygame
import json
import os

pygame.init()

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 500
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Hallowed Grounds")

# ---- COLORS ----
COLOR_BG = (18, 14, 26)
COLOR_PLATFORM = (90, 80, 110)
COLOR_PLAYER = (240, 220, 80)
COLOR_PLAYER_HIT = (255, 90, 90)
COLOR_KEY = (250, 200, 40)
COLOR_DOOR_LOCKED = (120, 40, 40)
COLOR_DOOR_OPEN = (60, 200, 90)
COLOR_TEXT = (230, 230, 230)
COLOR_LIFE_FULL = (220, 40, 60)
COLOR_LIFE_EMPTY = (70, 40, 45)

# ---- PHYSICS SETTINGS ----
GRAVITY = 0.7
JUMP_STRENGTH = -14
MOVE_SPEED = 5
PLAYER_WIDTH = 30
PLAYER_HEIGHT = 40

STARTING_LIVES = 3
INVINCIBILITY_FRAMES = 90  # ~1.5 seconds at 60fps
KNOCKBACK_DISTANCE = 40  # how far sideways a hit pushes the player


def load_json_data(filename):
    """
    Loads a JSON file from the 'data' folder that sits next to this
    script - using the script's own location (not wherever the game
    happens to be launched from) so it works no matter what folder
    you run the game from.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, "data", filename)
    with open(filepath, "r") as f:
        return json.load(f)


def save_filepath(slot_number):
    """
    Builds the path to a given save slot's file, e.g. slot 1 ->
    .../data/saves/save1.json. Using the script's own location, same
    reasoning as load_json_data, so it works regardless of which
    folder the game gets launched from.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "data", "saves", f"save{slot_number}.json")


def load_save(slot_number):
    """
    Returns the saved progress dict for this slot, or None if this
    slot has never been saved to (empty slot).
    """
    filepath = save_filepath(slot_number)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        return json.load(f)


def write_save(slot_number, room_index, lives, collected_scrolls):
    """
    Writes the current progress to this save slot, creating the
    'saves' folder the first time any save happens.
    """
    filepath = save_filepath(slot_number)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data = {
        "room_index": room_index,
        "lives": lives,
        "collected_scrolls": collected_scrolls,
    }
    with open(filepath, "w") as f:
        json.dump(data, f)


# =====================================================================
# MONSTER - one class, two behaviors ("patroller" and "chaser")
# =====================================================================
class Monster:
    def __init__(self, kind, x, y, size=34, color=(150, 30, 30), **settings):
        self.kind = kind
        self.x = float(x)
        self.y = float(y)
        self.size = size
        self.color = tuple(color)  # JSON gives us a list; pygame wants a tuple
        self.settings = settings

        if kind == "patroller":
            self.direction = 1  # 1 = moving right, -1 = moving left
            self.speed = settings.get("speed", 2)
            self.left_bound = settings.get("range", (x - 60, x + 60))[0]
            self.right_bound = settings.get("range", (x - 60, x + 60))[1]

        elif kind == "chaser":
            self.awake = False
            self.speed = settings.get("speed", 2.2)
            self.detect_radius = settings.get("detect_radius", 160)
            self.sleep_again_radius = settings.get("sleep_radius", 260)

    def update(self, player_rect):
        if self.kind == "patroller":
            self.x += self.speed * self.direction
            if self.x <= self.left_bound:
                self.x = self.left_bound
                self.direction = 1
            elif self.x >= self.right_bound:
                self.x = self.right_bound
                self.direction = -1

        elif self.kind == "chaser":
            player_center_x = player_rect.centerx
            distance = abs(player_center_x - (self.x + self.size / 2))

            if not self.awake and distance < self.detect_radius:
                self.awake = True
            elif self.awake and distance > self.sleep_again_radius:
                self.awake = False

            if self.awake:
                if player_center_x < self.x:
                    self.x -= self.speed
                elif player_center_x > self.x:
                    self.x += self.speed

    def rect(self):
        return pygame.Rect(self.x, self.y, self.size, self.size)

    def draw(self, surface):
        color = self.color
        if self.kind == "chaser" and not self.awake:
            # dim the color while asleep, so the player gets a visual hint
            color = tuple(c // 2 for c in self.color)
        pygame.draw.rect(surface, color, self.rect())


# =====================================================================
# ROOM DATA - loaded from data/rooms.json. To add a new room, edit
# that file - you don't need to touch this Python file at all.
# =====================================================================
ROOMS = load_json_data("rooms.json")


def build_monsters(room):
    chapter = CHAPTERS[room["chapter"]]
    difficulty = chapter["difficulty"]

    monsters = []
    for m in room["monsters"]:
        kind = m["kind"]
        x, y, size, color = m["x"], m["y"], m["size"], m["color"]
        extra_settings = {k: v for k, v in m.items() if k not in ("kind", "x", "y", "size", "color")}

        # Scale up speed (and, for chasers, how alert they are) based on
        # which chapter this room belongs to - later chapters = harder.
        if "speed" in extra_settings:
            extra_settings["speed"] = extra_settings["speed"] * difficulty
        if "detect_radius" in extra_settings:
            extra_settings["detect_radius"] = extra_settings["detect_radius"] * difficulty

        monsters.append(Monster(kind, x, y, size=size, color=color, **extra_settings))
    return monsters


# =====================================================================
# BACKGROUND THEMES - each room gets its own palette + decorations
# =====================================================================
def draw_background(surface, theme):
    surface.fill(theme["sky"])

    if theme["style"] == "moonlit":
        pygame.draw.circle(surface, theme["accent"], (700, 80), 40)  # moon
        for star_x, star_y in theme.get("stars", []):
            pygame.draw.circle(surface, (255, 255, 255), (star_x, star_y), 2)

    elif theme["style"] == "cobweb":
        # simple cobweb triangles tucked in the corners
        pygame.draw.polygon(surface, theme["accent"], [(0, 0), (90, 0), (0, 90)])
        pygame.draw.polygon(surface, theme["accent"], [(WINDOW_WIDTH, 0), (WINDOW_WIDTH - 90, 0), (WINDOW_WIDTH, 90)])

    elif theme["style"] == "torchlit":
        for tx in theme.get("torch_x", []):
            pygame.draw.circle(surface, theme["accent"], (tx, 60), 26)  # glow
            pygame.draw.rect(surface, (70, 45, 30), (tx - 4, 60, 8, 40))  # torch post


# =====================================================================
# CHAPTERS - groups of ~10 rooms sharing one theme AND one difficulty
# level, loaded from data/chapters.json. Add a new chapter there once
# you want a new "wing" of the mansion; every room just points at a
# chapter by its key.
# =====================================================================
CHAPTERS = load_json_data("chapters.json")


# =====================================================================
# CHARACTER SILHOUETTES - built from a few shapes instead of one square
# =====================================================================
def draw_player(surface, rect, color):
    # body
    pygame.draw.rect(surface, color, (rect.x, rect.y + 10, rect.width, rect.height - 10), border_radius=4)
    # head
    pygame.draw.circle(surface, color, (rect.centerx, rect.y + 8), 9)


def draw_monster(surface, monster):
    rect = monster.rect()
    color = monster.color
    if monster.kind == "chaser" and not monster.awake:
        color = tuple(c // 2 for c in monster.color)

    if monster.kind == "patroller":
        # a hunched, wide silhouette with two "ear" triangles
        pygame.draw.ellipse(surface, color, rect)
        ear_size = rect.width // 4
        pygame.draw.polygon(surface, color, [
            (rect.x + 4, rect.y + 6), (rect.x + 4 + ear_size, rect.y - 8), (rect.x + 4 + ear_size * 2, rect.y + 6)
        ])
    else:
        # a caped silhouette: triangle "cape" + round head
        pygame.draw.polygon(surface, color, [
            (rect.centerx, rect.y), (rect.x, rect.bottom), (rect.right, rect.bottom)
        ])
        pygame.draw.circle(surface, color, (rect.centerx, rect.y + 8), 8)


def draw_text_center(surface, text, font, color, y):
    surf = font.render(text, True, color)
    surface.blit(surf, (WINDOW_WIDTH // 2 - surf.get_width() // 2, y))


def draw_lives(surface, font, lives):
    label = font.render("Lives:", True, COLOR_TEXT)
    surface.blit(label, (10, 10))
    for i in range(STARTING_LIVES):
        cx = 90 + i * 30
        cy = 22
        color = COLOR_LIFE_FULL if i < lives else COLOR_LIFE_EMPTY
        pygame.draw.circle(surface, color, (cx, cy), 10)


def run_menu(title, options, font, big_font, subtitle=None):
    """
    A generic, reusable menu: shows a title and a vertical list of
    text options. UP/DOWN (or W/S) move the selection, SPACE or
    ENTER confirms. Returns the option string that was chosen.

    This one function powers BOTH the main menu and the pause menu -
    same reusable-behavior idea as our two monster types earlier.
    """
    clock = pygame.time.Clock()
    selected = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected = (selected - 1) % len(options)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected = (selected + 1) % len(options)
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    return options[selected]

        screen.fill(COLOR_BG)
        draw_text_center(screen, title, big_font, COLOR_TEXT, 100)
        if subtitle:
            draw_text_center(screen, subtitle, font, (150, 150, 165), 150)

        start_y = 230
        for i, option in enumerate(options):
            is_selected = (i == selected)
            color = COLOR_KEY if is_selected else COLOR_TEXT
            label = ("> " if is_selected else "   ") + option
            draw_text_center(screen, label, font, color, start_y + i * 40)

        pygame.display.flip()
        clock.tick(60)


def show_loading_screen(font, big_font):
    """
    A brief branding moment before the main menu. Our data loads
    instantly, so this is purely a pacing/polish choice - lots of
    real games do this even when there's nothing to actually wait for.
    """
    clock = pygame.time.Clock()
    for _ in range(60):  # about 1 second at 60fps
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

        screen.fill(COLOR_BG)
        draw_text_center(screen, "HALLOWED GROUNDS", big_font, COLOR_TEXT, 220)
        draw_text_center(screen, "Loading...", font, COLOR_KEY, 280)
        pygame.display.flip()
        clock.tick(60)


def show_main_menu(font, big_font):
    choice = run_menu(
        "HALLOWED GROUNDS",
        ["Start Game", "Quit"],
        font, big_font,
        subtitle="A pixel-art escape room platformer",
    )
    return "start" if choice == "Start Game" else "quit"


def show_slot_picker(font, big_font):
    """
    Lets the player choose one of 3 save slots. Each slot's label
    shows whether it's empty or which room it's currently at, so the
    player can tell progress apart from a blank slot at a glance.
    Returns (slot_number, save_data) where save_data is None for an
    empty slot.
    """
    saves = [load_save(1), load_save(2), load_save(3)]

    labels = []
    for i, save_data in enumerate(saves):
        slot_number = i + 1
        if save_data is None:
            labels.append(f"Save {slot_number} (Empty)")
        elif save_data["room_index"] >= len(ROOMS):
            labels.append(f"Save {slot_number} (Completed)")
        else:
            labels.append(f"Save {slot_number} (Room {save_data['room_index'] + 1})")

    choice = run_menu("SELECT SAVE SLOT", labels, font, big_font)
    chosen_index = labels.index(choice)
    slot_number = chosen_index + 1
    return slot_number, saves[chosen_index]


def wait_for_space(font, big_font, lines, title="ESCAPE ROOM"):
    clock = pygame.time.Clock()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                waiting = False

        screen.fill(COLOR_BG)
        draw_text_center(screen, title, big_font, COLOR_TEXT, 80)
        for i, line in enumerate(lines):
            draw_text_center(screen, line, font, COLOR_TEXT, 200 + i * 35)
        draw_text_center(screen, "Press SPACE to continue", font, COLOR_KEY, 420)

        pygame.display.flip()
        clock.tick(60)


def wrap_text(text, font, max_width):
    """
    Breaks a long string into a list of lines that each fit within
    max_width pixels, measuring actual text width with the given font.
    """
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines


def show_scroll(font, big_font, text, title="A weathered scroll"):
    """
    Displays one piece of scroll text, word-wrapped and paginated if
    too long for one screen. SPACE advances/closes.
    """
    clock = pygame.time.Clock()
    lines = wrap_text(text, font, 640)

    lines_per_page = 8
    pages = [lines[i:i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
    if not pages:
        pages = [[]]

    page_index = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                page_index += 1
                if page_index >= len(pages):
                    return

        screen.fill(COLOR_BG)
        draw_text_center(screen, title, big_font, COLOR_KEY, 60)

        for i, line in enumerate(pages[page_index]):
            draw_text_center(screen, line, font, COLOR_TEXT, 140 + i * 30)

        is_last_page = (page_index == len(pages) - 1)
        footer = "Press SPACE to close" if is_last_page else "Press SPACE to continue"
        draw_text_center(screen, footer, font, COLOR_KEY, WINDOW_HEIGHT - 40)

        pygame.display.flip()
        clock.tick(60)


def show_journal(collected_scrolls, font, big_font):
    """
    Lets the player re-read every scroll they've collected so far.
    """
    if not collected_scrolls:
        clock = pygame.time.Clock()
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    waiting = False

            screen.fill(COLOR_BG)
            draw_text_center(screen, "JOURNAL", big_font, COLOR_TEXT, 100)
            draw_text_center(screen, "No scrolls found yet.", font, COLOR_TEXT, 220)
            draw_text_center(screen, "Press SPACE to close", font, COLOR_KEY, 420)
            pygame.display.flip()
            clock.tick(60)
        return

    for i, scroll_text in enumerate(collected_scrolls):
        title = f"Journal entry {i + 1} of {len(collected_scrolls)}"
        show_scroll(font, big_font, scroll_text, title=title)


def play_room(room, lives, collected_scrolls, font, big_font):
    """
    Runs one room until the player either escapes it, loses all
    their lives, or pauses and quits to the menu.
    Returns ("escaped", lives, None), ("dead", lives, death_info), or
    ("quit_to_menu", lives, None).
    """
    platform_rects = [pygame.Rect(p) for p in room["platforms"]]
    door_rect = pygame.Rect(room["door"])
    key_pos = room["key"]
    key_rect = pygame.Rect(key_pos[0], key_pos[1], 24, 24) if key_pos else None
    monsters = build_monsters(room)

    scroll_rect = pygame.Rect(room["scroll_pos"][0], room["scroll_pos"][1], 20, 24) if room.get("scroll") else None
    scroll_collected = False

    start_x, start_y = room["player_start"]
    player_x, player_y = float(start_x), float(start_y)
    velocity_y = 0.0
    on_ground = False
    has_key = key_rect is None  # if there's no key in this room, treat as already "collected"
    invincible_timer = 0

    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                while True:
                    choice = run_menu("PAUSED", ["Resume", "Journal", "Restart Room", "Quit to Menu"], font, big_font)
                    if choice == "Journal":
                        show_journal(collected_scrolls, font, big_font)
                        continue  # show the pause menu again after closing the journal
                    elif choice == "Restart Room":
                        player_x, player_y = float(start_x), float(start_y)
                        velocity_y = 0.0
                        on_ground = False
                        has_key = key_rect is None
                        invincible_timer = 0
                        monsters = build_monsters(room)
                        break
                    elif choice == "Quit to Menu":
                        return "quit_to_menu", lives, None
                    else:
                        break  # Resume: just fall through to normal gameplay

        keys = pygame.key.get_pressed()

        if keys[pygame.K_a]:
            player_x -= MOVE_SPEED
        if keys[pygame.K_d]:
            player_x += MOVE_SPEED
        player_x = max(0, min(WINDOW_WIDTH - PLAYER_WIDTH, player_x))

        if keys[pygame.K_SPACE] and on_ground:
            velocity_y = JUMP_STRENGTH

        velocity_y += GRAVITY
        player_y += velocity_y

        player_rect = pygame.Rect(player_x, player_y, PLAYER_WIDTH, PLAYER_HEIGHT)
        on_ground = False
        for plat in platform_rects:
            if player_rect.colliderect(plat):
                if velocity_y >= 0 and (player_rect.bottom - velocity_y) <= plat.top + 1:
                    # Falling and landing on top of the platform.
                    player_y = plat.top - PLAYER_HEIGHT
                    velocity_y = 0
                    on_ground = True
                elif velocity_y < 0 and (player_rect.top - velocity_y) >= plat.bottom - 1:
                    # BUG FIX: moving upward and bonking your head on the
                    # underside of a platform. Without this case, jumping
                    # up into a platform from below let you phase straight
                    # through it, since only the "landing on top" case was
                    # handled before.
                    player_y = plat.bottom
                    velocity_y = 0

        if player_y > WINDOW_HEIGHT:
            player_x, player_y = float(start_x), float(start_y)
            velocity_y = 0

        player_rect = pygame.Rect(player_x, player_y, PLAYER_WIDTH, PLAYER_HEIGHT)

        if not has_key and key_rect and player_rect.colliderect(key_rect):
            has_key = True

        if scroll_rect and not scroll_collected and player_rect.colliderect(scroll_rect):
            scroll_collected = True
            show_scroll(font, big_font, room["scroll"])
            collected_scrolls.append(room["scroll"])

        # Update monsters and check for collisions with the player
        if invincible_timer > 0:
            invincible_timer -= 1

        for monster in monsters:
            monster.update(player_rect)
            if invincible_timer == 0 and player_rect.colliderect(monster.rect()):
                lives -= 1
                invincible_timer = INVINCIBILITY_FRAMES

                # Knockback: push the player away from the monster
                # horizontally, instead of teleporting back to the
                # room's start. If the player is to the left of the
                # monster, push them further left, and vice versa.
                monster_center = monster.rect().centerx
                if player_rect.centerx < monster_center:
                    player_x -= KNOCKBACK_DISTANCE
                else:
                    player_x += KNOCKBACK_DISTANCE
                player_x = max(0, min(WINDOW_WIDTH - PLAYER_WIDTH, player_x))

                if lives <= 0:
                    return "dead", lives, {"monster_kind": monster.kind, "room_name": room["name"]}
                break  # only lose one life per hit, even with multiple monsters

        if has_key and player_rect.colliderect(door_rect):
            return "escaped", lives, None

        # ---- DRAW ----
        theme = CHAPTERS[room["chapter"]]
        draw_background(screen, theme)
        for plat in platform_rects:
            pygame.draw.rect(screen, COLOR_PLATFORM, plat)

        if not has_key and key_rect:
            pygame.draw.rect(screen, COLOR_KEY, key_rect)

        if scroll_rect and not scroll_collected:
            pygame.draw.rect(screen, (200, 200, 240), scroll_rect)

        door_color = COLOR_DOOR_OPEN if has_key else COLOR_DOOR_LOCKED
        pygame.draw.rect(screen, door_color, door_rect)

        for monster in monsters:
            draw_monster(screen, monster)

        # Flash the player while invincible, so it's clear they got hit
        if invincible_timer == 0 or invincible_timer % 10 < 5:
            player_color = COLOR_PLAYER_HIT if invincible_timer > 0 else COLOR_PLAYER
            draw_player(screen, player_rect, player_color)

        room_name_surf = font.render(room["name"], True, COLOR_TEXT)
        screen.blit(room_name_surf, (WINDOW_WIDTH - room_name_surf.get_width() - 10, 10))
        draw_lives(screen, font, lives)

        hint_surf = font.render("ESC to pause", True, (140, 140, 150))
        screen.blit(hint_surf, (10, WINDOW_HEIGHT - 30))

        pygame.display.flip()
        clock.tick(60)


def build_death_message(death_info):
    """
    Returns a list of flavor-text lines for the death screen, varying
    based on which TYPE of monster caught the player and which room
    they were in. Falls back to a generic message if we don't have
    that info for some reason.
    """
    if death_info is None:
        return ["The mansion has claimed you.", "GAME OVER"]

    room_name = death_info.get("room_name", "the mansion")
    kind = death_info.get("monster_kind")

    if kind == "patroller":
        return [
            f"The wolf caught you in {room_name}.",
            "Its jaws did not hesitate.",
            "GAME OVER",
        ]
    elif kind == "chaser":
        return [
            f"It was waiting for you in {room_name}.",
            "You never saw it wake.",
            "GAME OVER",
        ]
    else:
        return [f"The mansion has claimed you in {room_name}.", "GAME OVER"]


def main():
    font = pygame.font.SysFont(None, 28)
    big_font = pygame.font.SysFont(None, 48)

    show_loading_screen(font, big_font)

    while True:
        menu_choice = show_main_menu(font, big_font)
        if menu_choice == "quit":
            break  # exits the outer while loop, game closes below

        slot_number, save_data = show_slot_picker(font, big_font)

        if save_data is not None and save_data["room_index"] >= len(ROOMS):
            # This slot already finished every room. Ask before doing
            # anything, instead of silently looping zero rooms.
            confirm_choice = run_menu(
                "SAVE COMPLETE",
                ["Restart Run", "Back to Main Menu"],
                font, big_font,
            )
            if confirm_choice == "Back to Main Menu":
                continue  # jump straight back to show_main_menu(), skip everything below
            else:
                # "Restart Run": treat exactly like an empty slot.
                save_data = None

        if save_data is None:
            # Empty slot (or a completed slot the player chose to
            # restart): start completely fresh.
            starting_room_index = 0
            lives = STARTING_LIVES
            collected_scrolls = []
        else:
            # Resume: pick up exactly where this slot left off.
            starting_room_index = save_data["room_index"]
            lives = save_data["lives"]
            collected_scrolls = save_data["collected_scrolls"]

        wait_for_space(
            font, big_font,
            [
                "You wake up on a cold stone floor. The door is sealed shut.",
                "Somewhere in this mansion, a way out exists.",
                "Find the keys. Avoid what hunts you. Escape.",
            ],
            title="HALLOWED GROUNDS",
        )

        sent_back_to_menu = False

        # enumerate(..., start=N) gives us the real room_index alongside
        # each room, even though we're only looping over the remaining
        # rooms (ROOMS[starting_room_index:]) - so saves always record
        # the correct absolute position in the full ROOMS list.
        for room_index, room in enumerate(ROOMS[starting_room_index:], start=starting_room_index):
            result, lives, death_info = play_room(room, lives, collected_scrolls, font, big_font)

            if result == "dead":
                wait_for_space(
                    font, big_font,
                    build_death_message(death_info),
                    title="YOU DIED",
                )
                sent_back_to_menu = True
                break
            elif result == "quit_to_menu":
                sent_back_to_menu = True
                break
            elif result == "escaped":
                # Automatic save: the player just made real progress,
                # so lock it in. room_index + 1 because they should
                # resume at the NEXT room, not replay the one they
                # just finished.
                write_save(slot_number, room_index + 1, lives, collected_scrolls)

        if sent_back_to_menu:
            continue  # skip the victory screen, go straight back to the main menu

        wait_for_space(
            font, big_font,
            ["The front door swings open.", "Moonlight. Fresh air. Freedom."],
            title="YOU ESCAPED!",
        )
        # after winning, loop back around to the main menu too (fall through)

    pygame.quit()


if __name__ == "__main__":
    main()