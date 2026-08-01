"""Render the checked-in GitHub preview assets from sanitized real command output."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SANS = "/System/Library/Fonts/Helvetica.ttc"
MONO = "/System/Library/Fonts/Menlo.ttc"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def terminal() -> None:
    image = Image.new("RGB", (1600, 760), "#0b1020")
    draw = ImageDraw.Draw(image)
    rounded(draw, (70, 70, 1530, 690), 26, "#111827")
    rounded(draw, (70, 70, 1530, 148), 26, "#1f2937")
    draw.rectangle((70, 122, 1530, 148), fill="#1f2937")
    for index, color in enumerate(("#fb7185", "#fbbf24", "#34d399")):
        draw.ellipse((106 + index * 34, 98, 126 + index * 34, 118), fill=color)

    title = font(SANS, 27)
    code = font(MONO, 30)
    small = font(SANS, 23)

    draw.text((220, 96), "cert-renewer · Docker quickstart", font=title, fill="#e5e7eb")
    command = [
        "$ docker run --rm \\",
        '    -v "$PWD/config.toml:/config/config.toml:ro" \\',
        '    -v "$PWD/secrets:/run/secrets:ro" \\',
        '    -v "$PWD/certificates:/certificates" \\',
        "    ghcr.io/vendora-bit/cert-renewer:latest check",
    ]
    y = 195
    for line in command:
        draw.text((124, y), line, font=code, fill="#d1d5db")
        y += 52
    draw.text((124, y + 12), '{"certificates": 1, "event": "configuration_valid",', font=code, fill="#6ee7b7")
    draw.text((124, y + 64), ' "level": "info", "timestamp": "2026-08-01T17:44:17Z"}', font=code, fill="#6ee7b7")
    draw.text((124, 620), "Real output from the unprivileged production image.", font=small, fill="#9ca3af")
    image.save(ASSETS / "cert-renewer-check.png", optimize=True)


def social() -> None:
    image = Image.new("RGB", (1280, 640), "#0b1020")
    draw = ImageDraw.Draw(image)
    rounded(draw, (0, 0, 1280, 640), 0, "#0b1020")
    for x, y, r, color in (
        (1002, 130, 160, "#172554"), (1115, 248, 100, "#1e3a8a"),
        (920, 440, 210, "#0f766e"), (1120, 485, 135, "#164e63"),
    ):
        draw.ellipse((x-r, y-r, x+r, y+r), fill=color)

    brand = font(SANS, 28)
    name = font(SANS, 78)
    body = font(SANS, 33)
    draw.text((92, 80), "VENDORA INFRASTRUCTURE", font=brand, fill="#93c5fd")
    draw.text((88, 178), "cert-renewer", font=name, fill="#f8fafc")
    draw.text((92, 292), "Safe multi-certificate Let's Encrypt", font=body, fill="#d1d5db")
    draw.text((92, 342), "reconciliation for Docker and systemd.", font=body, fill="#d1d5db")

    rounded(draw, (92, 452, 325, 507), 16, "#1d4ed8")
    draw.text((116, 464), "Cloudflare DNS-01", font=font(SANS, 22), fill="#eff6ff")
    rounded(draw, (346, 452, 564, 507), 16, "#065f46")
    draw.text((370, 464), "Atomic install", font=font(SANS, 22), fill="#ecfdf5")
    rounded(draw, (585, 452, 825, 507), 16, "#312e81")
    draw.text((609, 464), "No Docker socket", font=font(SANS, 22), fill="#eef2ff")

    draw.text((92, 563), "github.com/vendora-bit/cert-renewer", font=font(MONO, 22), fill="#94a3b8")
    image.save(ASSETS / "social-preview.png", optimize=True)


if __name__ == "__main__":
    terminal()
    social()

