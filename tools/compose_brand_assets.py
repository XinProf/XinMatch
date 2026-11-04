"""Compose the branded splash screen from the backdrop artwork + the app logo.

The splash is a static PNG shipped in ``assets/`` and shown by
``xinmatch.ui.app._maybe_show_splash``; this script makes it reproducible so a
logo refresh or a version bump does not need hand-editing the bitmap.

Layout (2730×1536, same as the artwork):

* backdrop  — the crystal/pattern illustration, untouched
* bottom-left — ``XinMatch`` wordmark + version + a hairline accent rule
* bottom-right — the logo plate, with a soft glow so it separates from the
  dark backdrop

Usage::

    python -m tools.compose_brand_assets \
        --backdrop assets/splash_backdrop.png --logo assets/logo_transparent.png \
        --out assets/splash.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = Path(r"C:\Windows\Fonts")
#: 首选 Segoe UI（Win10/11 自带），缺失时退回 Arial / PIL 默认位图字体。
FONT_CANDIDATES = {
    "bold": ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"),
    "regular": ("segoeui.ttf", "arial.ttf"),
}


def _font(kind: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in FONT_CANDIDATES[kind]:
        path = FONT_DIR / name
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _plate_with_glow(logo: Image.Image, size: int) -> Image.Image:
    """Resize the logo plate and add a soft outer glow on a padded canvas."""
    plate = logo.convert("RGBA").resize((size, size), Image.LANCZOS)
    pad = int(size * 0.22)
    canvas = Image.new("RGBA", (size + 2 * pad, size + 2 * pad), (0, 0, 0, 0))
    # Glow = the plate's alpha, blurred and tinted white; drawn under the plate.
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    glow.paste((255, 255, 255, 110), (pad, pad, pad + size, pad + size),
               plate.getchannel("A"))
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.10))
    canvas = Image.alpha_composite(canvas, glow)
    canvas.paste(plate, (pad, pad), plate)
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backdrop", type=Path, default=Path("assets/splash_backdrop.png"))
    ap.add_argument("--logo", type=Path, default=Path("assets/logo_transparent.png"))
    ap.add_argument("--out", type=Path, default=Path("assets/splash.png"))
    ap.add_argument("--version", default=None,
                    help="版本字符串；缺省读 xinmatch.__version__")
    args = ap.parse_args()

    version = args.version
    if version is None:
        from xinmatch import __version__

        version = __version__

    base = Image.open(args.backdrop).convert("RGBA")
    w, h = base.size
    logo = Image.open(args.logo)

    # ---- right side: logo plate -------------------------------------------
    plate_size = int(h * 0.30)
    plate = _plate_with_glow(logo, plate_size)
    margin = int(h * 0.075)
    base.alpha_composite(plate, (w - plate.width - margin, h - plate.height - margin))

    # ---- left side: wordmark + version ------------------------------------
    # 左下角先压一层柔和暗角，避免文字压在亮峰上（原插画该处有强峰与高光）。
    scrim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.ellipse(
        (int(w * 0.005), int(h * 0.50), int(w * 0.50), int(h * 1.06)),
        fill=(2, 10, 29, 150),
    )
    scrim = scrim.filter(ImageFilter.GaussianBlur(h * 0.045))
    base = Image.alpha_composite(base, scrim)

    draw = ImageDraw.Draw(base)
    size_name = int(h * 0.125)
    size_ver = int(h * 0.052)
    size_tag = int(h * 0.034)
    x = int(w * 0.055)
    y_name = int(h * 0.615)
    draw.text((x, y_name), "XinMatch", font=_font("bold", size_name),
              fill=(255, 255, 255, 245))
    # 版本 + 细横线
    y_ver = y_name + int(size_name * 1.16)
    draw.line([(x + 2, y_ver - int(size_ver * 0.55)),
               (x + 2 + int(w * 0.055), y_ver - int(size_ver * 0.55))],
              fill=(120, 190, 255, 220), width=max(2, h // 400))
    draw.text((x + 2, y_ver), f"v{version}", font=_font("regular", size_ver),
              fill=(198, 226, 255, 235))
    draw.text((x + 2, y_ver + int(size_ver * 1.5)),
              "Powder XRD phase identification", font=_font("regular", size_tag),
              fill=(176, 205, 232, 232))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(args.out, optimize=True)
    print(f"splash -> {args.out}  ({w}x{h}, version={version})")


if __name__ == "__main__":
    main()
