"""Create the game's icon files from native pygame drawing primitives."""
from pathlib import Path
import io
import random
import struct

import pygame


ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"
SIZE = 1024


def make_icon():
    pygame.font.init()
    surface = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = (int(19 - 10 * t), int(17 - 10 * t), int(30 - 16 * t))
        pygame.draw.line(surface, color, (0, y), (SIZE, y))

    rng = random.Random(1107)
    for _ in range(170):
        x, y = rng.randrange(42, 982), rng.randrange(38, 660)
        shade = rng.randrange(42, 115)
        pygame.draw.circle(surface, (shade, shade, shade + 14, 170), (x, y), rng.choice((1, 1, 2)))

    # Moon and the black tree line establish the forest setting at icon size.
    pygame.draw.circle(surface, (183, 176, 139), (760, 270), 148)
    pygame.draw.circle(surface, (18, 15, 27), (818, 229), 137)
    for x, height, width in ((52, 430, 94), (139, 340, 76), (890, 375, 92), (972, 470, 112)):
        pygame.draw.rect(surface, (9, 9, 15), (x + width // 2 - 8, 390, 16, 355))
        for y in range(405, 750, 65):
            span = int(width * (1 - (y - 405) / 510))
            pygame.draw.polygon(surface, (10, 10, 16),
                                ((x + width // 2, y - height // 3),
                                 (x + width // 2 - span, y + 72),
                                 (x + width // 2 + span, y + 72)))

    # Main house silhouette, multiple roof lines, and mismatched lit windows.
    pygame.draw.rect(surface, (30, 24, 27), (205, 480, 620, 330))
    pygame.draw.polygon(surface, (24, 19, 25), ((166, 503), (419, 320), (661, 503)))
    pygame.draw.polygon(surface, (21, 17, 23), ((570, 475), (755, 337), (868, 475)))
    pygame.draw.line(surface, (89, 57, 50), (167, 504), (420, 319), 12)
    pygame.draw.line(surface, (89, 57, 50), (420, 319), (662, 504), 12)
    pygame.draw.line(surface, (84, 53, 47), (570, 477), (755, 337), 10)
    pygame.draw.line(surface, (84, 53, 47), (755, 337), (870, 477), 10)
    pygame.draw.rect(surface, (15, 13, 19), (403, 593, 126, 217))
    pygame.draw.ellipse(surface, (63, 45, 43), (403, 553, 126, 94))
    pygame.draw.line(surface, (89, 58, 47), (466, 590), (466, 808), 6)
    for x, y, w, h, glow in ((273, 547, 64, 92, (121, 43, 40)),
                             (650, 540, 62, 89, (164, 118, 72)),
                             (720, 618, 49, 72, (91, 33, 38)),
                             (313, 658, 53, 78, (144, 88, 57))):
        pygame.draw.rect(surface, (8, 8, 13), (x - 10, y - 10, w + 20, h + 20))
        pygame.draw.rect(surface, glow, (x, y, w, h))
        pygame.draw.line(surface, (34, 25, 27), (x + w // 2, y), (x + w // 2, y + h), 5)
        pygame.draw.line(surface, (34, 25, 27), (x, y + h // 2), (x + w, y + h // 2), 5)

    # Low fog and a damaged tracking line echo the game's VHS motif.
    fog = pygame.Surface((SIZE, 170), pygame.SRCALPHA)
    pygame.draw.ellipse(fog, (151, 147, 155, 28), (-70, 42, 660, 72))
    pygame.draw.ellipse(fog, (173, 159, 151, 20), (360, 55, 760, 80))
    surface.blit(fog, (0, 700))
    pygame.draw.line(surface, (165, 37, 43), (54, 822), (970, 822), 5)
    pygame.draw.line(surface, (237, 143, 126), (154, 827), (442, 827), 2)

    font = pygame.font.SysFont("Georgia", 74, bold=True)
    title = font.render("HALLOWED GROUNDS", True, (222, 214, 201))
    title_rect = title.get_rect(center=(SIZE // 2, 907))
    shadow = font.render("HALLOWED GROUNDS", True, (74, 29, 32))
    surface.blit(shadow, title_rect.move(4, 5))
    surface.blit(title, title_rect)

    # Outer tape label border and registration marks.
    pygame.draw.rect(surface, (116, 79, 68), (24, 24, SIZE - 48, SIZE - 48), 5, border_radius=30)
    pygame.draw.rect(surface, (37, 31, 40), (38, 38, SIZE - 76, SIZE - 76), 2, border_radius=24)
    for x in (54, SIZE - 54):
        pygame.draw.circle(surface, (178, 38, 44), (x, 54), 5)
        pygame.draw.circle(surface, (178, 38, 44), (x, SIZE - 54), 5)

    return surface


def make_ico(png_data):
    # PNG-compressed frames are supported in modern Windows icon resources.
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_data), 22)
    return struct.pack("<HHH", 0, 1, 1) + entry + png_data


def png_bytes(surface):
    buffer = io.BytesIO()
    pygame.image.save(surface, buffer, "hallowed_grounds.png")
    return buffer.getvalue()


def make_icns(icon):
    chunks = []
    for size, chunk_type in ((16, b"icp4"), (32, b"icp5"), (64, b"icp6"),
                             (128, b"ic07"), (256, b"ic08"), (512, b"ic09"), (1024, b"ic10")):
        frame = pygame.transform.smoothscale(icon, (size, size))
        image_data = png_bytes(frame)
        chunks.append(chunk_type + struct.pack(">I", len(image_data) + 8) + image_data)
    body = b"".join(chunks)
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = make_icon()
    pygame.image.save(icon, ASSET_DIR / "hallowed_grounds_icon.png")
    small_icon = pygame.transform.smoothscale(icon, (256, 256))
    (ASSET_DIR / "hallowed_grounds_icon.ico").write_bytes(make_ico(png_bytes(small_icon)))
    (ASSET_DIR / "hallowed_grounds_icon.icns").write_bytes(make_icns(icon))
    pygame.font.quit()
    print("Game icons created in", ASSET_DIR)


if __name__ == "__main__":
    main()
