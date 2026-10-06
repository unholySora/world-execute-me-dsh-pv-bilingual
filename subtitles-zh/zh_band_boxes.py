#!/usr/bin/env python3
"""Symmetric version: two frames in the lower band, opening outwards from the middle.

  left frame  : the translation, right-aligned against the middle rule
  right frame : the film's own English band, moved there — its title, its `>` prompt, its chips
                and its token ids, cut out of the picture and re-laid-out by a single shift, so it
                reads exactly as the film drew it, only on the right.

Two *separate* boxes with a gap between them, as in the reference sketch: the left one carries the
translation, the right one carries the film's own English band (its `stdout · tokens` legend, its `>`
prompt, its chips and its token ids).

The English is not redrawn: every frame, the band's interior is cut out of the film, the vacated
pixels are filled from the row's own background, and the content — legend included — is written back
shifted by a constant, so the legend lands on the right box's top rule exactly as the film drew it.
The film's outer rules (x35, x1885) and the top/bottom rules stay and become the two boxes' outer
edges; across the gap the film's top/bottom rules are blanked and the two facing edges are drawn in
the film's own rule colour, sampled from that same frame, so they dim and pulse with it.

When the film hides the band, the whole strip goes transparent, so the picture passes through
untouched.

  python3 zh_band_sym.py test         -> out_sym/t_<time>.png strips
  python3 zh_band_sym.py render       -> out_sym/film_zh_sym.mp4
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import zh_band as zb

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "out"
W, H = 1920, 1080

# the band's box is (36,924)-(1884,1020) with "stdout · tokens" set into its top rule
STRIP = (30, 900, 1890, 1028)            # the overlay strip: the whole band plus its margin
INNER = (39, 910, 1881, 1019)            # everything that gets cut and moved
BOX_TOP, BOX_BOT = 924, 1020             # the band's own box, so the middle rule spans the same
RULE_ROWS = slice(923 - INNER[1], 928 - INNER[1])   # the box's own top rule: never moves
LEGEND = (84, 910, 258, 936)             # the legend's box: the film's own tell for "band is up"
RULE_ROWS_FILL = (924, 925)                # the film's top rule: the rows to close
LEG_BLOCK = (64, 910, 268, 940)          # the legend travels as a block, padding included, so the
                                         # right box's top rule gets the film's own fieldset gap
LEG_SHIFT = 856                          # … and with the film's own inset from its box's left edge,
                                         # which is more than the content's shift (824) can give it
RULE_FILL = (53, 269)                    # the film's fieldset gap: closed again, so the left box
                                         # reads as a complete frame with no hole in its top rule

SHIFT = 824                              # how far the English moves right
GAP0, GAP1 = 846, 884                    # the two facing edges: 2 px each, 36 px of air between
CN_RIGHT = GAP0 - 26                     # the translation's right edge, the band's own inset
CHIP_TOP, CHIP_BOT = 942, 984
LABEL_Y = 988
CN_LEFT = 63                             # the deleted line's left edge: the box's own 26 px inset
DEL_LEAD = 0.22                          # a line starts being deleted this long before its successor
DEL_DUR = 0.32                           # how long the strike-and-slide takes
DEL_DIM = 0.52                           # how far the deleted line dims down
F_CH, PAD, GAP = zb.F_CH, zb.PAD, zb.GAP
UI, BG = zb.UI, zb.BG

LEGEND_ON = 0.5                          # normalized correlation of the legend against itself


def frame_at(t: float) -> np.ndarray:
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(zb.VIDEO), "-frames:v", "1",
                          "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    return np.frombuffer(p.stdout.read(W * H * 3), np.uint8).reshape(H, W, 3)


def frame_stream():
    """The film, frame by frame at its own rate, so the strip can be built from its pixels."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", "0", "-i", str(zb.VIDEO), "-vf", f"fps={zb.FPS}",
                          "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE, bufsize=10 ** 8)
    while True:
        b = p.stdout.read(W * H * 3)
        if len(b) < W * H * 3:
            return
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)


def fonts():
    return (ImageFont.truetype(zb.CJK[0], F_CH, index=zb.CJK[1]),
            ImageFont.truetype(zb.CJK[0], 15, index=zb.CJK[1]),
            ImageFont.truetype(zb.MONO_B, 14))


def legend_template() -> np.ndarray:
    """The band's legend, lifted off a frame where the band is certainly up."""
    f = frame_at(122.0)[LEGEND[1]:LEGEND[3], LEGEND[0]:LEGEND[2]].max(axis=2).astype(np.float64)
    return (f - f.mean()) / (f.std() + 1e-6)


def legend_present(frame: np.ndarray, tpl: np.ndarray) -> bool:
    """The band's legend is drawn whenever the band is up — drained, dimmed, at any opacity.
    Matching it with a zero-mean, unit-variance correlation ignores the brightness entirely,
    which is what the film's own `pulse` and colour-drain keep changing."""
    g = frame[LEGEND[1]:LEGEND[3], LEGEND[0]:LEGEND[2]].max(axis=2).astype(np.float64)
    g = g - g.mean()
    denom = np.sqrt((g ** 2).sum()) * np.sqrt((tpl ** 2).sum())
    return bool(denom > 1e-6 and (g * tpl).sum() / denom > LEGEND_ON)


def cut_and_shift(frame: np.ndarray) -> np.ndarray:
    """Return the strip: the film's band with its content moved right by SHIFT.

    The legend is not part of that mask — it travels as a whole block, so it lands on the right box's
    top rule carrying its own background, which cuts the rule there exactly the way the film's own
    fieldset gap sits under it. Its source area is vacated like everything else, and the film's gap
    across the left box's top rule is closed again in draw_faces().
    """
    reg = frame[STRIP[1]:STRIP[3], STRIP[0]:STRIP[2]].copy()
    iy0, iy1 = INNER[1] - STRIP[1], INNER[3] - STRIP[1]
    ix0, ix1 = INNER[0] - STRIP[0], INNER[2] - STRIP[0]
    inner = reg[iy0:iy1, ix0:ix1]
    v = inner.max(axis=2).astype(np.int16)
    # this row's own background, per channel: the chip strips cover about half of a busy row, so
    # a low percentile is the only one that lands on the flat part. Filling with a scalar grey
    # (even the right level) would leave the chips visible as neutral patches on this blue-black.
    bg = np.percentile(inner, 2, axis=1).astype(np.int16)          # (h, 3)
    bgv = bg.max(axis=1, keepdims=True)                            # (h, 1)
    mask = v > bgv + 5                                             # the drawn content on top of it
    mask[RULE_ROWS] = False                                        # the box's own rule stays put
    lr = slice(LEG_BLOCK[1] - INNER[1], LEG_BLOCK[3] - INNER[1])   # the legend's rows …
    lc = slice(LEG_BLOCK[0] - INNER[0], LEG_BLOCK[2] - INNER[0])   # … and columns
    mask[lr, lc] = False
    erase = mask.copy()
    erase[lr, lc] = True                                           # its source is vacated all the same
    if not erase.any():
        return reg
    # fill each erased run from the un-drawn pixels either side of it, so the band's own faint
    # background gradient survives the cut (a flat fill leaves visible patches on this near-black)
    h, w, _ = inner.shape
    idx = np.arange(w, dtype=np.int32)[None, :]
    li = np.maximum.accumulate(np.where(erase, -1, idx), axis=1)
    ri = np.minimum.accumulate(np.where(erase, w, idx)[:, ::-1], axis=1)[:, ::-1]
    ys, xs = np.nonzero(erase)
    l, r = li[ys, xs], ri[ys, xs]
    vl = inner[ys, np.clip(l, 0, w - 1)].astype(np.float32)
    vr = inner[ys, np.clip(r, 0, w - 1)].astype(np.float32)
    wg = ((r - xs) / np.maximum(r - l, 1)).astype(np.float32)[:, None]
    fill = np.where(l[:, None] < 0, vr, np.where(r[:, None] >= w, vl, vl * wg + vr * (1 - wg)))
    plate = inner.copy()
    plate[ys, xs] = np.clip(fill + 0.5, 0, 255).astype(np.uint8)
    ys, xs = np.nonzero(mask[:, : w - SHIFT])
    plate[ys, xs + SHIFT, :] = inner[ys, xs, :]                    # the content, written back shifted
    plate[lr, slice(LEG_BLOCK[0] + LEG_SHIFT - INNER[0], LEG_BLOCK[2] + LEG_SHIFT - INNER[0])] = inner[lr, lc]
    reg[iy0:iy1, ix0:ix1] = plate
    return reg


CHIP_STEP = int(round(F_CH + PAD * 2 + GAP))


def cn_state(tracks, t: float):
    """(live, dead): the line being shown on the right, and the one pushed out to the left.

    A line is deleted from DEL_LEAD before its successor shows up — it takes the strike and slides
    left, then stays there in that state until the next line starts being deleted in its turn.
    """
    live = dead = None
    for tr in tracks:
        if tr["start"] > t:
            break
        if t >= tr["show_until"] - DEL_LEAD:
            dead = tr
        else:
            live = tr
    return live, dead


def _chips(ld, tr, x: float, top: int, bot: int, level: float, f_chip, S: int = 1) -> None:
    """The line's chips, drawn left to right from x, at the given brightness, at S× scale."""
    for j, ch in enumerate(tr["zh"]):
        ld.rectangle([x, top, x + (F_CH + PAD * 2) * S, bot],
                     fill=zb.mix(UI, (0.13 if j % 2 == 0 else 0.22) * level))
        bb = ld.textbbox((0, 0), ch, font=f_chip)
        ld.text((x + PAD * S + (F_CH * S - (bb[2] - bb[0])) / 2 - bb[0],
                 (top + bot) / 2 - (bb[3] + bb[1]) / 2), ch, font=f_chip, fill=zb.mix(UI, level))
        x += CHIP_STEP * S


def draw_faces(reg: np.ndarray, frame: np.ndarray, ox: int, oy: int) -> None:
    """Blank the film's top/bottom rules across the gap and give each box its own facing edge.

    The film's own frame is only two rules wide, so the gap is made by covering the rules there with
    the box's background, then the two facing edges are painted in the colour the film's own rule has
    *in this frame* — that is what keeps them in step with the film's `pulse` and its colour drain.
    """
    frc = frame[960, 35:37].max(axis=0)                     # the film's rule colour, this frame
    # the film's top rule carries the fieldset gap its legend sat in. The legend now lives on the
    # right box, so that gap is closed again: the left box's top rule then runs unbroken, which is
    # what the reference sketch shows. Filled with the film's own rule colour for this frame, so it
    # still dims and pulses with the film.
    for row in RULE_ROWS_FILL:
        seg = frame[row, 300:500]
        reg[row - oy, RULE_FILL[0] - ox:RULE_FILL[1] - ox] = np.median(seg, axis=0)
    for gy in (924, 925, 1020, 1021):
        src_y = 930 if gy < 1000 else 1014                  # the background just inside the box
        reg[gy - oy, GAP0 - ox:GAP1 + 2 - ox] = reg[src_y - oy, GAP0 - ox:GAP1 + 2 - ox]
    for gx in (GAP0, GAP0 + 1, GAP1, GAP1 + 1):
        reg[BOX_TOP - oy:BOX_BOT - oy + 1, gx - ox] = frc


def text_layer(t: float, tracks, S: int = 1) -> Image.Image:
    """The Chinese layer on its own, drawn at S×.

    A 4K render uses S=2 so the translation is really rendered at 4K — the film underneath can only
    be scaled up (1080p is all the source has), but the lettering has no reason to inherit that.
    """
    sw, sh = (STRIP[2] - STRIP[0]) * S, (STRIP[3] - STRIP[1]) * S
    img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    g = zb.band_gain(t)
    f_chip = ImageFont.truetype(zb.CJK[0], F_CH * S, index=zb.CJK[1])
    f_lc = ImageFont.truetype(zb.CJK[0], 15 * S, index=zb.CJK[1])
    f_lm = ImageFont.truetype(zb.MONO_B, 14 * S)
    top, bot = (CHIP_TOP - STRIP[1]) * S, (CHIP_BOT - STRIP[1]) * S
    cn_right = (CN_RIGHT - STRIP[0]) * S
    cn_left = (CN_LEFT - STRIP[0]) * S
    # the live line sits right-aligned; the one it replaced takes the strike, slides left and stays
    # there in its dimmed, deleted state until the next line takes its place
    live, dead = cn_state(tracks, t)
    if dead is not None:
        p = min(1.0, max(0.0, (t - (dead["show_until"] - DEL_LEAD)) / DEL_DUR))
        e = 1 - (1 - p) ** 3                                     # fast out, then settle
        w = (len(dead["zh"]) * CHIP_STEP - GAP) * S
        x = (cn_right - w) + (cn_left - (cn_right - w)) * e
        lv = 0.95 - (0.95 - DEL_DIM) * e
        _chips(d, dead, x, top, bot, lv * g, f_chip, S)
        if p > 0.12:                                             # the strike sweeps in from the right
            sweep = w * min(1.0, (p - 0.12) / 0.5)
            y = (top + bot) // 2
            d.rectangle([x + w - sweep, y - 2 * S, x + w, y + S], fill=zb.mix(UI, min(1.0, lv * 1.2) * g))
    if live is not None:
        w = (len(live["zh"]) * CHIP_STEP - GAP) * S
        _chips(d, live, cn_right - w, top, bot, 0.95 * g, f_chip, S)
    if int(t * 3) % 2 == 0:                                      # the caret blinks, line or no line
        d.rectangle([cn_right + 4 * S, top + 4 * S, cn_right + 20 * S, bot - 4 * S], fill=zb.mix(UI, 0.9 * g))
    a = zb.mix(UI, 0.42 * g)                                      # the label, on the token-id row
    wc = d.textlength("译文", font=f_lc)
    wm = d.textlength(" · zh", font=f_lm)
    d.text((cn_right - wc - wm, (LABEL_Y - STRIP[1]) * S), "译文", font=f_lc, fill=a)
    d.text((cn_right - wm, (LABEL_Y - STRIP[1]) * S + S), " · zh", font=f_lm, fill=a)
    return img


def draw_elements(reg: np.ndarray, t: float, tracks, ox: int, oy: int, frame: np.ndarray) -> None:
    draw_faces(reg, frame, ox, oy)
    img = Image.fromarray(reg, "RGB").convert("RGBA")
    img.alpha_composite(text_layer(t, tracks, 1))
    reg[:] = np.array(img.convert("RGB"))


def strip_for4k(frame: np.ndarray, t: float, tracks, tpl: np.ndarray, S: int = 2):
    """The same strip at S×: the film part is the 1080p material scaled (all the source has), the
    lettering is drawn at S× so a 4K file really carries 4K text."""
    if not legend_present(frame, tpl):
        return None
    plate = cut_and_shift(frame)
    draw_faces(plate, frame, STRIP[0], STRIP[1])
    sw, sh = (STRIP[2] - STRIP[0]) * S, (STRIP[3] - STRIP[1]) * S
    big = Image.fromarray(plate, "RGB").resize((sw, sh), Image.LANCZOS).convert("RGBA")
    big.alpha_composite(text_layer(t, tracks, S))
    return np.array(big)


def strip_for(frame: np.ndarray, t: float, tracks, tpl: np.ndarray):
    if not legend_present(frame, tpl):
        return None                                        # the film has the band hidden: pass through
    reg = cut_and_shift(frame)
    draw_elements(reg, t, tracks, STRIP[0], STRIP[1], frame)
    return reg


def main():
    tracks = zb.load()
    tpl = legend_template()
    OUTDIR.mkdir(exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    if mode == "test":
        for t in (0.5, 6.5, 16.6, 61.0, 83.5, 122.0, 148.6, 148.0, 150.0, 160.0, 170.5, 189.0, 205.5):
            f = frame_at(t)
            s = strip_for(f, t, tracks, tpl)
            base = Image.fromarray(f[STRIP[1]:STRIP[3], STRIP[0]:STRIP[2]], "RGB").convert("RGBA")
            if s is None:
                print(f"  t={t}: band hidden, pass through")
            else:
                base.alpha_composite(Image.fromarray(np.dstack([s, np.full(s.shape[:2], 255, np.uint8)]), "RGBA"))
            base.convert("RGB").save(OUTDIR / f"t_{t:07.3f}.png")
        print("wrote strips to", OUTDIR)
        return
    t0, t1 = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (0.0, zb.END)
    name = sys.argv[4] if len(sys.argv) > 4 else "film_zh_boxes.mp4"
    out = OUTDIR / name
    if mode == "render4k":
        S = 2
        sw, sh = (STRIP[2] - STRIP[0]) * S, (STRIP[3] - STRIP[1]) * S
        enc = subprocess.Popen(
            ["ffmpeg", "-v", "warning", "-stats", "-y",
             "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{sw}x{sh}", "-r", str(zb.FPS), "-i", "-",
             "-ss", str(t0), "-i", str(zb.VIDEO),
             "-filter_complex", f"[1:v]scale=iw*{S}:ih*{S}:flags=lanczos[base];"
                                 f"[base][0:v]overlay={STRIP[0] * S}:{STRIP[1] * S}:format=auto[v]",
             "-map", "[v]", "-map", "1:a?", "-c:v", "libx265", "-preset", "medium", "-crf", "20",
             "-t", str(t1 - t0), "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)],
            stdin=subprocess.PIPE)
        dec, n = frame_stream(), 0
        while True:
            f = next(dec, None)
            if f is None:
                break
            t = t0 + n / zb.FPS
            if t >= t1:
                break
            s = strip_for4k(f, t, tracks, tpl, S)
            enc.stdin.write(bytes(sw * sh * 4) if s is None else np.ascontiguousarray(s).tobytes())
            n += 1
            if n % 240 == 0:
                print(f"  frame {n} t={t:6.1f}s", flush=True)
        enc.stdin.close()
        enc.wait()
        print("wrote", out)
        return
    sw, sh = STRIP[2] - STRIP[0], STRIP[3] - STRIP[1]
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "warning", "-stats", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{sw}x{sh}", "-r", str(zb.FPS), "-i", "-",
         "-ss", str(t0), "-i", str(zb.VIDEO),
         "-filter_complex", f"[0:v]format=rgba[ov];[1:v][ov]overlay={STRIP[0]}:{STRIP[1]}:format=auto[v]",
         "-map", "[v]", "-map", "1:a?", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
         "-t", str(t1 - t0), "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    dec = frame_stream()                                # the film, frame by frame, in step
    n = 0
    while True:
        f = next(dec, None)
        if f is None:
            break
        t = t0 + n / zb.FPS
        if t >= t1:
            break
        s = strip_for(f, t, tracks, tpl)
        if s is None:
            enc.stdin.write(bytes(sw * sh * 4))
        else:
            rgba = np.dstack([s, np.full((sh, sw), 255, np.uint8)])
            enc.stdin.write(np.ascontiguousarray(rgba).tobytes())
        n += 1
        if n % 240 == 0:
            print(f"  frame {n} t={t:6.1f}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("wrote", out)


if __name__ == "__main__":
    main()