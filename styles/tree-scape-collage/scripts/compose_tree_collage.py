#!/usr/bin/env python3
"""Compose 6–12 landscape photos beneath a fixed tree overlay."""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError as exc:  # pragma: no cover - environment-specific
    print(f"Missing dependency: {exc.name}. Install Pillow and NumPy.", file=sys.stderr)
    raise SystemExit(2) from exc


CANVAS = (1206, 2310)
MASK_SIZE = (603, 1155)
SLOT_NAMES = ("右上主窗", "左上主窗", "底部", "左下", "右下", "左中", "正中点景", "左上角")
ADJACENT = (
    (0, 1), (0, 4), (0, 6), (0, 7),
    (1, 5), (1, 6), (1, 7),
    (2, 3), (2, 4),
    (3, 5),
    (4, 6),
    (5, 6),
)
TARGET_LIGHTNESS = (0.45, 0.48, 0.44, 0.42, 0.50, 0.43, 0.57, 0.56)


@dataclass(frozen=True)
class Photo:
    path: Path
    quality: float
    hue: float
    saturation: float
    lightness: float

    @property
    def feature(self) -> np.ndarray:
        angle = self.hue * math.tau
        return np.array(
            [math.cos(angle), math.sin(angle), self.saturation, self.lightness],
            dtype=np.float32,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "tree-base.jpg")
    parser.add_argument("--keep-order", action="store_true", help="Use the first eight inputs in the supplied slot order.")
    parser.add_argument("--focus", help="Eight semicolon-separated normalized x,y crop anchors.")
    parser.add_argument("--grade", choices=("auto", "cohesive", "vivid", "none"), default="auto")
    parser.add_argument("--tree-strength", type=float, default=1.0, help="Tree opacity multiplier from 0.7 to 1.0.")
    return parser.parse_args()


def open_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def measure(path: Path) -> Photo:
    image = open_rgb(path)
    image.thumbnail((256, 256), Image.Resampling.LANCZOS)
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    hsv = np.asarray(image.convert("HSV"), dtype=np.float32) / 255.0
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    sat = float(np.median(hsv[..., 1]))
    light = float(np.mean(gray))
    valid = hsv[..., 1] > 0.08
    hue = float(np.median(hsv[..., 0][valid])) if np.any(valid) else 0.0
    dx = np.abs(np.diff(gray, axis=1)).mean() if gray.shape[1] > 1 else 0.0
    dy = np.abs(np.diff(gray, axis=0)).mean() if gray.shape[0] > 1 else 0.0
    hist = np.histogram(gray, bins=32, range=(0, 1), density=False)[0].astype(np.float64)
    hist /= max(hist.sum(), 1.0)
    entropy = float(-(hist[hist > 0] * np.log2(hist[hist > 0])).sum() / 5.0)
    clipping = float(((rgb < 0.01) | (rgb > 0.99)).all(axis=2).mean())
    quality = 0.42 * entropy + 0.28 * min((dx + dy) * 5.0, 1.0) + 0.22 * sat + 0.08 * (1.0 - clipping)
    return Photo(path=path, quality=quality, hue=hue, saturation=sat, lightness=light)


def feature_distance(a: Photo, b: Photo) -> float:
    weights = np.array([0.55, 0.55, 0.7, 0.9], dtype=np.float32)
    return float(np.linalg.norm((a.feature - b.feature) * weights))


def select_diverse(photos: list[Photo], count: int = 8) -> list[Photo]:
    chosen = [max(photos, key=lambda photo: photo.quality)]
    remaining = [photo for photo in photos if photo is not chosen[0]]
    while remaining and len(chosen) < min(count, len(photos)):
        next_photo = max(
            remaining,
            key=lambda photo: 0.55 * photo.quality + 0.45 * min(feature_distance(photo, item) for item in chosen),
        )
        chosen.append(next_photo)
        remaining.remove(next_photo)
    if len(chosen) < count:
        repeat_pool = sorted(chosen, key=lambda photo: photo.quality, reverse=True)
        index = 0
        while len(chosen) < count:
            chosen.append(repeat_pool[index % len(repeat_pool)])
            index += 1
    return chosen


def arrangement_cost(order: tuple[Photo, ...]) -> float:
    cost = 0.0
    for left, right in ADJACENT:
        distance = feature_distance(order[left], order[right])
        repeat = order[left].path == order[right].path
        cost += math.exp(-2.6 * distance) + (20.0 if repeat else 0.0)
    for index, photo in enumerate(order):
        cost += 0.25 * abs(photo.lightness - TARGET_LIGHTNESS[index])
    return cost


def arrange(photos: list[Photo]) -> list[Photo]:
    return list(min(itertools.permutations(photos, 8), key=arrangement_cost))


def parse_focus(value: str | None) -> list[tuple[float, float] | None]:
    if not value:
        return [None] * 8
    entries = value.split(";")
    if len(entries) != 8:
        raise ValueError("--focus must contain exactly eight semicolon-separated x,y pairs")
    result: list[tuple[float, float]] = []
    for entry in entries:
        x_text, y_text = entry.split(",", 1)
        x, y = float(x_text), float(y_text)
        result.append((min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)))
    return result


def crop_box_for_focus(size: tuple[int, int], aspect: float, focus: tuple[float, float]) -> tuple[int, int, int, int]:
    width, height = size
    if width / height >= aspect:
        crop_h = height
        crop_w = max(1, round(height * aspect))
    else:
        crop_w = width
        crop_h = max(1, round(width / aspect))
    center_x = focus[0] * width
    center_y = focus[1] * height
    left = round(min(max(center_x - crop_w / 2, 0), width - crop_w))
    top = round(min(max(center_y - crop_h / 2, 0), height - crop_h))
    return left, top, left + crop_w, top + crop_h


def saliency_focus(image: Image.Image, aspect: float, variant: int = 0) -> tuple[float, float]:
    preview = image.copy()
    preview.thumbnail((240, 240), Image.Resampling.LANCZOS)
    gray = np.asarray(preview.convert("L"), dtype=np.float32) / 255.0
    hsv = np.asarray(preview.convert("HSV"), dtype=np.float32) / 255.0
    edge = np.zeros_like(gray)
    edge[:, 1:] += np.abs(np.diff(gray, axis=1))
    edge[1:, :] += np.abs(np.diff(gray, axis=0))
    saliency = edge * 2.2 + hsv[..., 1] * 0.28 + np.abs(gray - np.median(gray)) * 0.18
    h, w = gray.shape
    if w / h >= aspect:
        crop_h, crop_w = h, max(1, round(h * aspect))
    else:
        crop_w, crop_h = w, max(1, round(w / aspect))
    integral = np.pad(saliency, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    candidates: list[tuple[float, int, int]] = []
    step_x = max(1, (w - crop_w) // 10 or 1)
    step_y = max(1, (h - crop_h) // 10 or 1)
    for top in range(0, h - crop_h + 1, step_y):
        for left in range(0, w - crop_w + 1, step_x):
            total = integral[top + crop_h, left + crop_w] - integral[top, left + crop_w] - integral[top + crop_h, left] + integral[top, left]
            center_penalty = 0.05 * (abs((left + crop_w / 2) / w - 0.5) + abs((top + crop_h / 2) / h - 0.5))
            candidates.append((float(total / (crop_w * crop_h) - center_penalty), left, top))
    candidates.sort(reverse=True)
    _, left, top = candidates[min(variant, len(candidates) - 1)]
    return ((left + crop_w / 2) / w, (top + crop_h / 2) / h)


def grade_image(image: Image.Image, mode: str, target_light: float) -> Image.Image:
    if mode == "none":
        return image
    sample = image.copy()
    sample.thumbnail((160, 160), Image.Resampling.BILINEAR)
    current = float(np.asarray(sample.convert("L"), dtype=np.float32).mean() / 255.0)
    strength = 0.20 if mode == "cohesive" else 0.10
    if mode == "vivid":
        image = ImageEnhance.Color(image).enhance(1.12)
        image = ImageEnhance.Contrast(image).enhance(1.06)
    elif mode == "cohesive":
        image = ImageEnhance.Color(image).enhance(0.94)
    else:
        image = ImageEnhance.Color(image).enhance(1.04)
    brightness = 1.0 + (target_light - current) * strength
    return ImageEnhance.Brightness(image).enhance(min(max(brightness, 0.92), 1.08))


def compose_background(
    order: list[Photo],
    focuses: list[tuple[float, float] | None],
    grade: str,
    cell_labels: np.ndarray,
) -> Image.Image:
    canvas = Image.new("RGB", CANVAS, "white")
    occurrences: dict[Path, int] = {}
    for index, photo in enumerate(order):
        mask = Image.fromarray(np.where(cell_labels == index + 1, 255, 0).astype(np.uint8), mode="L")
        bbox = mask.getbbox()
        if bbox is None:
            raise RuntimeError(f"Tree-derived cell {index + 1} is empty")
        left, top, right, bottom = bbox
        box_w, box_h = right - left, bottom - top
        source = open_rgb(photo.path)
        occurrence = occurrences.get(photo.path, 0)
        occurrences[photo.path] = occurrence + 1
        focus = focuses[index] or saliency_focus(source, box_w / box_h, variant=occurrence * 2)
        crop = crop_box_for_focus(source.size, box_w / box_h, focus)
        tile = source.crop(crop).resize((box_w, box_h), Image.Resampling.LANCZOS)
        effective_grade = "vivid" if grade == "auto" and photo.saturation > 0.32 else ("cohesive" if grade == "auto" else grade)
        tile = grade_image(tile, effective_grade, TARGET_LIGHTNESS[index])
        layer = Image.new("RGB", CANVAS)
        layer.paste(tile, (left, top))
        canvas.paste(layer, (0, 0), mask)
    return canvas


def largest_dark_component(gray: np.ndarray, threshold: int = 215) -> np.ndarray:
    dark = gray < threshold
    # The source screenshot has a thin dark capture edge along the top. Break
    # that edge before connected-component analysis so it cannot join the tree.
    dark[:3, :] = False
    height, width = dark.shape
    seen = np.zeros_like(dark, dtype=bool)
    best: list[int] = []
    from collections import deque

    for y, x in zip(*np.nonzero(dark)):
        if seen[y, x]:
            continue
        queue = deque([y * width + x])
        seen[y, x] = True
        component: list[int] = []
        while queue:
            position = queue.popleft()
            cy, cx = divmod(position, width)
            component.append(position)
            if cx > 0 and dark[cy, cx - 1] and not seen[cy, cx - 1]:
                seen[cy, cx - 1] = True
                queue.append(position - 1)
            if cx + 1 < width and dark[cy, cx + 1] and not seen[cy, cx + 1]:
                seen[cy, cx + 1] = True
                queue.append(position + 1)
            if cy > 0 and dark[cy - 1, cx] and not seen[cy - 1, cx]:
                seen[cy - 1, cx] = True
                queue.append(position - width)
            if cy + 1 < height and dark[cy + 1, cx] and not seen[cy + 1, cx]:
                seen[cy + 1, cx] = True
                queue.append(position + width)
        if len(component) > len(best):
            best = component
    result = np.zeros_like(dark, dtype=np.uint8)
    if best:
        result.ravel()[np.asarray(best, dtype=np.int64)] = 255
    return result


def tree_overlay(base_path: Path, strength: float) -> Image.Image:
    base = open_rgb(base_path).resize(CANVAS, Image.Resampling.LANCZOS)
    gray = np.asarray(base.convert("L"), dtype=np.uint8)
    component = largest_dark_component(gray)
    mask = Image.fromarray(component)
    closed = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    thick_zone = mask.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(17))
    silhouette = Image.fromarray(
        np.maximum(
            component,
            np.where(np.asarray(thick_zone) > 0, np.asarray(closed), 0),
        ).astype(np.uint8)
    )
    edge = mask.filter(ImageFilter.GaussianBlur(0.65))
    alpha = Image.fromarray(np.maximum(np.asarray(silhouette), np.asarray(edge)).astype(np.uint8))
    if strength < 1.0:
        alpha = alpha.point(lambda value: round(value * strength))
    # The JPEG was flattened on white. Darken the outside edge before adding
    # transparency so antialiased white matte pixels cannot create a halo.
    silhouette_array = np.asarray(silhouette)
    eroded = np.asarray(silhouette.filter(ImageFilter.MinFilter(5)))
    boundary = (silhouette_array > 0) & (eroded == 0)
    rgb = np.asarray(base).copy()
    rgb[boundary] = np.minimum(rgb[boundary], 28)
    rgb[(silhouette_array == 0) & (np.asarray(alpha) > 0)] = 0
    overlay = Image.fromarray(rgb).convert("RGBA")
    overlay.putalpha(alpha)
    return overlay


def branch_cell_labels(overlay: Image.Image) -> np.ndarray:
    """Derive eight photo cells from the actual trunk and branch geometry.

    The tree is treated as a barrier. Its eight largest naturally enclosed
    background components become the primary cells; small twig-enclosed
    pockets inherit the nearest primary cell. Labels then grow back through
    the widened barrier, so every meeting line stays inside a branch band and
    is covered by the final tree overlay.
    """
    width, height = MASK_SIZE
    alpha = overlay.getchannel("A").resize(MASK_SIZE, Image.Resampling.LANCZOS)
    base_barrier = np.asarray(alpha.filter(ImageFilter.MaxFilter(9))) >= 48
    right_barrier = np.asarray(alpha.filter(ImageFilter.MaxFilter(17))) >= 48
    right_region = np.zeros((height, width), dtype=bool)
    right_region[:, 280:] = True
    # Close only the branch tips on the visually dominant right side. This
    # splits the oversized upper-right opening without thickening every branch
    # or creating a free-floating geometric cut through the photographs.
    barrier = base_barrier | (right_barrier & right_region)
    background = ~barrier
    seen = np.zeros((height, width), dtype=bool)
    components: list[tuple[int, float, float, np.ndarray]] = []

    for y, x in zip(*np.nonzero(background)):
        if seen[y, x]:
            continue
        queue = deque([y * width + x])
        seen[y, x] = True
        pixels: list[int] = []
        sum_x = 0
        sum_y = 0
        while queue:
            position = queue.popleft()
            cy, cx = divmod(position, width)
            pixels.append(position)
            sum_x += cx
            sum_y += cy
            for neighbor in (position - 1, position + 1, position - width, position + width):
                if not 0 <= neighbor < width * height:
                    continue
                ny, nx = divmod(neighbor, width)
                if abs(nx - cx) + abs(ny - cy) != 1:
                    continue
                if background[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append(neighbor)
        count = len(pixels)
        components.append(
            (count, sum_x / count, sum_y / count, np.asarray(pixels, dtype=np.int64))
        )

    components.sort(key=lambda component: component[0], reverse=True)
    if len(components) < 8:
        raise RuntimeError("The fixed tree no longer produces eight branch-defined cells")
    primary = components[:8]
    labels = np.zeros(width * height, dtype=np.uint8)

    for _, center_x, center_y, pixels in components:
        slot = min(
            range(8),
            key=lambda index: (
                (center_x - primary[index][1]) ** 2
                + (center_y - primary[index][2]) ** 2
            ),
        )
        labels[pixels] = slot + 1

    # Multi-source growth puts the remaining label meetings in the middle of
    # the widened tree barrier instead of drawing straight cuts through photos.
    queue = deque(np.nonzero(labels)[0].tolist())
    while queue:
        position = queue.popleft()
        cy, cx = divmod(position, width)
        label = labels[position]
        for neighbor in (position - 1, position + 1, position - width, position + width):
            if not 0 <= neighbor < width * height or labels[neighbor] != 0:
                continue
            ny, nx = divmod(neighbor, width)
            if abs(nx - cx) + abs(ny - cy) != 1:
                continue
            labels[neighbor] = label
            queue.append(neighbor)

    label_image = Image.fromarray(labels.reshape(height, width), mode="L")
    return np.asarray(label_image.resize(CANVAS, Image.Resampling.NEAREST), dtype=np.uint8)


def seam_coverage(cell_labels: np.ndarray, overlay: Image.Image) -> float:
    """Return the share of photo-change pixels that remain near a real branch."""
    seam = np.zeros(cell_labels.shape, dtype=bool)
    seam[:, 1:] |= cell_labels[:, 1:] != cell_labels[:, :-1]
    seam[1:, :] |= cell_labels[1:, :] != cell_labels[:-1, :]
    nearby_tree = np.asarray(overlay.getchannel("A").filter(ImageFilter.MaxFilter(9))) > 16
    return float(nearby_tree[seam].mean()) if np.any(seam) else 1.0


def main() -> int:
    args = parse_args()
    missing = [str(path) for path in [*args.inputs, args.base] if not path.is_file()]
    if missing:
        print("Missing files:\n" + "\n".join(missing), file=sys.stderr)
        return 2
    if not 6 <= len(args.inputs) <= 12:
        print("Provide 6–12 input photos.", file=sys.stderr)
        return 2
    if not 0.7 <= args.tree_strength <= 1.0:
        print("--tree-strength must be between 0.7 and 1.0", file=sys.stderr)
        return 2
    try:
        focuses = parse_focus(args.focus)
    except (ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    photos = [measure(path) for path in args.inputs]
    if args.keep_order:
        selected = photos[:8]
        while len(selected) < 8:
            selected.append(photos[(len(selected) - len(photos)) % len(photos)])
    else:
        selected = arrange(select_diverse(photos, 8))
    overlay = tree_overlay(args.base, args.tree_strength)
    cell_labels = branch_cell_labels(overlay)
    background = compose_background(selected, focuses, args.grade, cell_labels)
    result = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output, format="PNG", optimize=True)
    print("Created:", args.output.resolve())
    print("Slots:")
    for index, photo in enumerate(selected):
        print(f"  {index + 1} ({SLOT_NAMES[index]}): {photo.path}")
    print(f"Branch-aligned seam coverage: {seam_coverage(cell_labels, overlay):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
