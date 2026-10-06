#!/usr/bin/env python3
"""Draw the Chinese translation of world.execute(me); into the empty right half of the film's
bottom band ("stdout · tokens"), in the same chip/cursor language the band uses for the English
lyric. The overlay is composited onto the finished film, so nothing else about the picture changes.

  python3 zh_band.py test            -> out_test/t_<time>.png strips, for eyeballing
  python3 zh_band.py render          -> pipes the overlay into ffmpeg and writes out/film_zh.mp4
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
TRACKS = ROOT / "zh_tracks2.json"
VIDEO = Path(os.environ.get("WEM_SOURCE", str(ROOT / "source.mp4"))).resolve()
OUTDIR = ROOT / "out"

FPS = 24
SCALE = 1.5                      # the film layout is 1280x720; the download is 1920x1080
W, H = 1920, 1080
END = 211.875
BEAT = 60.0 / 130.0              # engine.BEAT, 130 BPM
BREAK = 2.0

# --- the band, in 1080p coordinates (1280x720 box 24,616,1256,680)
BOX = (36, 924, 1884, 1020)
CHIP_TOP, CHIP_BOT = 942, 984
LABEL_Y = 986                    # the label sits on the token-id row, far right (that strip stays empty)
RIGHT = 1845                     # right edge of the last chip / of the label
BG = (4, 7, 15)                  # tuikit deepsea BG
UI = (200, 214, 234)             # tuikit deepsea UI colour
_CJK_SPEC = os.environ.get("WEM_CJK_FONT",
                          "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc#2")
_CJK_PATH, _, _CJK_IDX = _CJK_SPEC.partition("#")
CJK = (_CJK_PATH, int(_CJK_IDX or 0))
def _repo_font(*parts) -> str:
    """The film's own fonts live in the repo; find them from wherever this script sits."""
    for base in (ROOT, *ROOT.parents):
        p = base.joinpath(*parts)
        if p.exists():
            return str(p)
    return str(ROOT.joinpath(*parts))


MONO_B = os.environ.get("WEM_MONO_FONT") or _repo_font(
    "film", "ai_mascot_mv_world_execute_20260926", "fonts", "SpaceMono-Bold.ttf")

F_CH = 28                        # CJK glyph size
PAD, GAP = 3, 7                  # per chip, and between chips (the band uses -3/+3 and +6)


def mix(c, level, base=BG):
    level = max(0.0, min(1.0, level))
    return tuple(int(base[i] + (c[i] - base[i]) * level) for i in range(3))


def load() -> list[dict]:
    tracks = json.loads(TRACKS.read_text(encoding="utf-8"))
    out = []
    for k, tr in enumerate(tracks):
        nxt = tracks[k + 1]["start"] if k + 1 < len(tracks) else END
        end = tr["end"]
        if nxt - end > BREAK:
            tr["show_until"], tr["fade_until"] = end + BEAT, end + 2 * BEAT
        else:
            tr["show_until"] = tr["fade_until"] = nxt
        n = len(tr["zh"])
        step = max(0.045, min(0.25, (end - tr["start"]) / n))
        tr["char_at"] = [tr["start"] + j * step for j in range(n)]
        tr["live"] = [tr["start"], nxt]
        out.append(tr)
    return out


def current(tracks, t):
    for tr in tracks:
        if tr["start"] - 0.0 <= t < tr["fade_until"]:
            a = 1.0 if t < tr["show_until"] else 1.0 - (t - tr["show_until"]) / (tr["fade_until"] - tr["show_until"])
            return tr, max(0.0, min(1.0, a))
    return None, 1.0


def _font():
    return ImageFont.truetype(CJK[0], F_CH, index=CJK[1])


ALPHABET = "".join(sorted({c for tr in json.loads(TRACKS.read_text(encoding="utf-8")) for c in tr["zh"]}))

# how present the band's frame is over the film (12 fps, from the border line of the box): the label only
# shows as much as the band's own label does, so it never floats where the band has faded out
_PRESENT = ROOT / "box_present.json"
_GAIN = ROOT / "band_gain.json"


def _series(path, t: float, fps: float, default: float):
    try:
        v = json.loads(path.read_text())
    except OSError:
        return default
    i = max(0.0, min(t * fps, len(v) - 1.001))
    a, b = int(i), min(int(i) + 1, len(v) - 1)
    return v[a] + (v[b] - v[a]) * (i - a)


def band_gain(t: float) -> float:
    """The film drains its system colour in places ("you have left"): measured off the band's own text."""
    return max(0.3, min(1.0, _series(_GAIN, t, 12, 1.0)))


def label_alpha(t: float) -> float:
    cnt = _series(_PRESENT, t, 12, 1500)
    return max(0.0, min(1.0, (cnt - 60) / 300))


def draw_band(img: Image.Image, t: float, tracks, label: bool = True, origin=(0, 0)) -> None:
    ox, oy = origin
    d = ImageDraw.Draw(img)
    g = band_gain(t)
    if label and label_alpha(t) > 0.02:
        f = ImageFont.truetype(MONO_B, 19)
        fc = ImageFont.truetype(CJK[0], 20, index=CJK[1])
        txt_cjk, txt_m = "译文", " · zh"
        wc = d.textlength(txt_cjk, font=fc)
        wm = d.textlength(txt_m, font=f)
        x = RIGHT - wc - wm - ox
        a = mix(UI, 0.42 * label_alpha(t) * g)
        d.text((x, LABEL_Y - oy), txt_cjk, font=fc, fill=a)
        d.text((x + wc, LABEL_Y + 1 - oy), txt_m, font=f, fill=a)
    tr, alpha = current(tracks, t)
    if tr is None or alpha <= 0:
        return
    f = _font()
    n_out = len(tr["zh"])                   # 常驻：整句一次显示，不做逐字渐入
    step = int(round(F_CH + PAD * 2 + GAP))
    top, bot = CHIP_TOP - oy, CHIP_BOT - oy
    x = RIGHT - ox
    for j in range(n_out - 1, -1, -1):
        ch = tr["zh"][j]
        cw = F_CH + PAD * 2
        x0 = x - cw
        d.rectangle([x0, top, x, bot], fill=mix(UI, (0.13 if j % 2 == 0 else 0.22) * g))
        bb = d.textbbox((0, 0), ch, font=f)
        d.text((x0 + (cw - (bb[2] - bb[0])) / 2 - bb[0], (top + bot) / 2 - (bb[3] + bb[1]) / 2),
               ch, font=f, fill=mix(UI, 0.95 * g))
        x -= step
    if int(t * 3) % 2 == 0:                 # 句尾常驻闪烁光标（和片子里英文光标同节奏）
        d.rectangle([RIGHT - ox + 3, top + 4, RIGHT - ox + 19, bot - 4], fill=mix(UI, 0.9 * g))
    if alpha < 0.999:
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))


REGION = (1000, 900, 1920, 1030)


def strip(t, tracks):
    img = Image.new("RGBA", (REGION[2] - REGION[0], REGION[3] - REGION[1]), (0, 0, 0, 0))
    draw_band(img, t, tracks, origin=REGION[:2])
    return img


def main():
    tracks = load()
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    if mode == "test":
        OUTDIR.mkdir(exist_ok=True)
        for t in (0.5, 1.2, 2.5, 4.0, 6.5, 8.0, 31.4, 59.3, 62.5, 96.0, 155.5, 159.5, 161.0, 184.7, 205.5):
            strip(t, tracks).save(OUTDIR / f"t_{t:07.3f}.png")
        print("wrote", len(list(OUTDIR.glob('t_*.png'))), "test strips to", OUTDIR)
        return
    # render: pipe the overlay strips into ffmpeg over the film
    OUTDIR.mkdir(exist_ok=True)
    rw, rh = REGION[2] - REGION[0], REGION[3] - REGION[1]
    t0, t1 = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (0.0, END)
    n_frames = int(round((t1 - t0) * FPS))
    out = OUTDIR / ("film_zh.mp4" if t0 == 0 else "seg_zh.mp4")
    cmd = ["ffmpeg", "-v", "warning", "-stats", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{rw}x{rh}", "-r", str(FPS), "-i", "-",
           "-ss", str(t0), "-i", str(VIDEO),
           "-filter_complex", f"[0:v]format=rgba[ov];[1:v][ov]overlay={REGION[0]}:{REGION[1]}:format=auto[v]",
           "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
           "-t", str(t1 - t0), "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(n_frames):
        t = t0 + n / FPS
        p.stdin.write(strip(t, tracks).tobytes())
        if n % 240 == 0:
            print(f"  frame {n}/{n_frames} t={t:6.1f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()