"""Single source of truth for TestFlow theme colors and contrast checks."""

from __future__ import annotations

PALETTES = {
    "ocean": {"light": "#2547C4", "dark": "#8FA6FF"},
    "amber": {"light": "#8F5400", "dark": "#E0A24A"},
    "sakura": {"light": "#A62456", "dark": "#E37AA0"},
    "holo": {"light": "#5B34C7", "dark": "#A58BF5"},
}

NEUTRALS = {
    "light": {
        "bg": "#F3F5F8", "surface": "#FFFFFF", "surface_alt": "#F7F9FB",
        "text": "#1B2434", "muted": "#4B596B", "border": "#7F8B9B",
        "success": "#166534", "error": "#A02F2F", "skipped": "#52637C",
    },
    "dark": {
        "bg": "#151B27", "surface": "#1E2735", "surface_alt": "#263242",
        "text": "#E8EDF5", "muted": "#B9C4D3", "border": "#9BAABE",
        "success": "#85D8A0", "error": "#FF9E9E", "skipped": "#C2CEDF",
    },
}


def palette(theme: str, mode: str) -> dict[str, str]:
    result = {**NEUTRALS[mode], "accent": PALETTES[theme][mode]}
    result["on_accent"] = "#FFFFFF" if mode == "light" else "#111725"
    result["focus"] = result["accent"]
    result["link"] = result["accent"]
    result["icon"] = result["muted"]
    result["progress"] = result["accent"]
    return result


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(fg: str, bg: str) -> float:
    high, low = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def audit() -> list[tuple[str, str, str, str, float, float]]:
    failures = []
    for theme in PALETTES:
        for mode in NEUTRALS:
            colors = palette(theme, mode)
            foregrounds = {
                "text": 7.0, "muted": 4.5, "accent": 4.5,
                "success": 3.0, "error": 3.0, "skipped": 3.0,
                "border": 3.0, "focus": 3.0, "link": 4.5,
                "icon": 3.0, "progress": 3.0,
            }
            pairs = [
                (foreground, background, minimum)
                for background in ("bg", "surface", "surface_alt")
                for foreground, minimum in foregrounds.items()
            ]
            pairs.extend(("on_accent", background, 4.5) for background in ("accent", "success", "error"))
            assert len(pairs) == 36
            for foreground, background, minimum in pairs:
                actual = contrast(colors[foreground], colors[background])
                if actual < minimum:
                    failures.append((theme, mode, foreground, background, actual, minimum))
    return failures


if __name__ == "__main__":
    failures = audit()
    for theme, mode, foreground, background, actual, minimum in failures:
        print(f"{theme}/{mode}: {foreground} on {background}: {actual:.2f} < {minimum:.1f}")
    print(f"Checked 288 color pairs; {len(failures)} failures")
    raise SystemExit(bool(failures))
