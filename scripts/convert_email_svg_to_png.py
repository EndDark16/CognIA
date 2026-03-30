import sys
from pathlib import Path
from typing import Optional


def _fail(message: str) -> int:
    print(message)
    return 1


def _cairo_hint(exc: Exception) -> Optional[str]:
    message = str(exc)
    if "no library called" not in message and "libcairo" not in message:
        return None

    return (
        "Failed to import cairosvg because the native Cairo library is missing.\n"
        "Install a Cairo runtime and ensure `libcairo-2.dll` is on PATH.\n"
        "Windows options (pick one):\n"
        "1. Install MSYS2, then run `pacman -S mingw-w64-x86_64-cairo`, and add "
        "`C:\\msys64\\mingw64\\bin` to PATH.\n"
        "2. Install GTK for Windows (includes Cairo) and add its `bin` folder to PATH."
    )


def main() -> int:
    try:
        import cairosvg
    except Exception as exc:
        hint = _cairo_hint(exc)
        if hint:
            return _fail(hint)
        return _fail(
            "Failed to import cairosvg. Run: python -m pip install cairosvg\n"
            f"Details: {exc}"
        )

    base = Path(__file__).resolve().parents[1] / "static" / "email" / "logo"
    svg_files = [
        base / "cognia-logo-light.svg",
        base / "cognia-logo-dark.svg",
        base / "cognia-signature.svg",
    ]

    missing = [f.name for f in svg_files if not f.exists()]
    if missing:
        return _fail(f"Missing SVG files: {', '.join(missing)}")

    for svg in svg_files:
        png = svg.with_suffix(".png")
        cairosvg.svg2png(url=str(svg), write_to=str(png))
        print(f"OK: {svg.name} -> {png.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
