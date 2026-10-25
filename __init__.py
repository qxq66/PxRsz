"""Pixel Budget Resize V3. One node, separate target dimensions and image scaling."""
from fractions import Fraction
from math import isfinite, isqrt

__version__ = "3.0.0"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]


def _percent(value, name, maximum):
    try:
        f = float(value)
        result = Fraction(str(value))
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        raise ValueError(f"{name} muss eine endliche Zahl sein.") from None
    if not isfinite(f) or result < 0 or result > maximum:
        raise ValueError(f"{name} muss zwischen 0 und {maximum} liegen.")
    return result / 100


def _ceil_div(a, b):
    return -(-a // b)


def allowed_pixel_limit(max_pixels, limit_overrun_percent=0.0):
    base = int(max_pixels)
    if base < 1 or base != max_pixels:
        raise ValueError("max_pixels muss eine positive ganze Zahl sein.")
    allowed = base * (1 + _percent(limit_overrun_percent, "limit_overrun_percent", 100))
    return allowed.numerator // allowed.denominator


def calculate_dimensions(width, height, max_pixels=1048576, dimension_multiple=16,
                         limit_overrun_percent=0.0, max_aspect_error_percent=1.5,
                         optimization="closest_to_limit", scale_small_dimensions=True,
                         upscale_small_images=False, max_dimension=None):
    """Return target width/height, independently of whether image pixels are enlarged.

    Small = source area <= BASE max_pixels, including exactly equal area.
    If either small-image option is on, search targets near the budget.
    For small images each output side is >= its input side (no mixed scaling).
    For large images each side is <= its input side. No padding or cropping.
    'pixels' in the node means TARGET width*height, not necessarily IMAGE area.
    """
    w, h, base, grid = map(int, (width, height, max_pixels, dimension_multiple))
    if (w, h, base, grid) != (width, height, max_pixels, dimension_multiple):
        raise ValueError("Abmessungen, Budget und Raster muessen ganzzahlig sein.")
    if min(w, h, base, grid) < 1:
        raise ValueError("Abmessungen, Budget und Raster muessen positiv sein.")
    tolerance = _percent(max_aspect_error_percent, "max_aspect_error_percent", 50)
    cap = allowed_pixel_limit(base, limit_overrun_percent)
    if optimization not in ("closest_to_limit", "maximize_allowed_pixels"):
        raise ValueError("Unbekannte optimization.")
    if max_dimension is not None and (int(max_dimension) != max_dimension or max_dimension < 1):
        raise ValueError("max_dimension muss positiv und ganzzahlig sein.")
    small = w * h <= base
    if small and not (scale_small_dimensions or upscale_small_images):
        return w, h

    ratio = Fraction(w, h)
    lower, upper = ratio * (1 - tolerance), ratio * (1 + tolerance)
    min_w, min_h = (w, h) if small else (1, 1)
    max_w = min(cap // grid, isqrt((cap * upper.numerator) // upper.denominator))
    max_h = min(cap // grid, isqrt((cap * lower.denominator) // lower.numerator))
    if not small:
        max_w, max_h = min(max_w, w), min(max_h, h)
    if max_dimension is not None:
        max_w, max_h = min(max_w, int(max_dimension)), min(max_h, int(max_dimension))

    transpose = max_h // grid - _ceil_div(min_h, grid) < max_w // grid - _ceil_div(min_w, grid)
    if transpose:
        x_min, x_max, y_minimum, y_maximum = min_h, max_h, min_w, max_w
        r_min, r_max = 1 / upper, 1 / lower
    else:
        x_min, x_max, y_minimum, y_maximum = min_w, max_w, min_h, max_h
        r_min, r_max = lower, upper

    best = best_score = None
    for x in range(_ceil_div(x_min, grid) * grid, x_max + 1, grid):
        y_min = max(y_minimum, _ceil_div(x * r_max.denominator, r_max.numerator))
        y_min = _ceil_div(y_min, grid) * grid
        y_max = min(y_maximum, cap // x, x * r_min.denominator // r_min.numerator)
        y_max = y_max // grid * grid
        if y_min > y_max:
            continue
        if optimization == "maximize_allowed_pixels":
            candidates = (y_max,)
        else:
            y_floor = (base // (x * grid)) * grid
            candidates = {max(y_min, min(y_max, y_floor)),
                          max(y_min, min(y_max, y_floor + grid))}
        for y in candidates:
            nw, nh = (y, x) if transpose else (x, y)
            area = nw * nh
            error = abs(Fraction(nw * h, nh * w) - 1)
            if optimization == "closest_to_limit":
                score = (abs(area - base), area > base, error, nw, nh)
            else:
                score = (-area, error, nw, nh)
            if best_score is None or score < best_score:
                best, best_score = (nw, nh), score
    if best is None:
        raise ValueError(
            f"Keine passende Zielgroesse fuer {w} x {h}: Basis {base:,}, "
            f"Obergrenze {cap:,}, Raster {grid}, Verhaeltnistoleranz "
            f"{max_aspect_error_percent} %. "
            "Verhaeltnistoleranz oder erlaubte Pixelueberschreitung erhoehen, "
            "oder Raster verkleinern. Bei 0 % Verhaeltnistoleranz sind nur "
            "mathematisch exakte Proportionen erlaubt. "
            "Wenn beide Optionen fuer kleine Bilder aus sind, bleiben deren "
            "Masse unangetastet, auch ausserhalb des Rasters."
        )
    return best


class PixelBudgetResize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_pixels": ("INT", {"default": 1048576, "min": 1, "max": 1099511627776, "step": 1,
                    "tooltip": "Basislimit der ZIELMASSE: Breite mal Hoehe pro Bild."}),
                "dimension_multiple": ("INT", {"default": 16, "min": 1, "max": 512, "step": 1,
                    "tooltip": "Raster der Zielmasse: 1 fuer freie Masse, 16 fuer SD3."}),
                "upscale_method": (["lanczos", "area", "bicubic", "bilinear", "nearest-exact"],),
            },
            "optional": {
                "limit_overrun_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 100.0, "step": 0.01,
                    "tooltip": "Erlaubte Ueberschreitung des Basis-Pixelbudgets in Prozent. 0 = harte Grenze."}),
                "max_aspect_error_percent": ("FLOAT", {"default": 1.5, "min": 0.0, "max": 50.0, "step": 0.01,
                    "tooltip": "Maximale relative Abweichung von Breite/Hoehe. 0 = mathematisch exakt."}),
                "optimization": (["closest_to_limit", "maximize_allowed_pixels"],
                    {"tooltip": "Basislimit moeglichst genau treffen ODER erhoehtes Limit ausnutzen."}),
                "scale_small_dimensions": ("BOOLEAN", {"default": True,
                    "tooltip": "Kleine Bilder: width/height zum Budget hochrechnen, IMAGE allein dadurch NICHT vergroessern."}),
                "upscale_small_images": ("BOOLEAN", {"default": False,
                    "tooltip": "Kleine Bilder auch tatsaechlich auf die Zielmasse hochskalieren. Aktiviert Zielberechnung auch wenn scale_small_dimensions AUS ist."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("image", "width", "height", "pixels", "info")
    FUNCTION = "resize"
    CATEGORY = "image/resize/pixel budget"
    DESCRIPTION = (
        "V3: Bildskalierung und Zielmasse fuer EmptySD3LatentImage getrennt steuerbar. "
        "width/height/pixels sind ZIELMASSE und koennen bei kleinen Bildern vom IMAGE abweichen. "
        "Mit upscale_small_images wird IMAGE ebenfalls auf die Zielmasse vergroessert. "
        "Pixelbudget, Ueberschreitung, Raster und Verhaeltnistoleranz bleiben einstellbar."
    )

    def resize(self, image, max_pixels, dimension_multiple, upscale_method,
               limit_overrun_percent=0.0, max_aspect_error_percent=1.5,
               optimization="closest_to_limit", scale_small_dimensions=True,
               upscale_small_images=False):
        old_h, old_w = int(image.shape[1]), int(image.shape[2])
        if min(old_h, old_w) < 1:
            raise ValueError("Leeres Bild.")
        try:
            from nodes import MAX_RESOLUTION
        except ImportError:
            MAX_RESOLUTION = None
        tw, th = calculate_dimensions(
            old_w, old_h, max_pixels, dimension_multiple,
            limit_overrun_percent, max_aspect_error_percent, optimization,
            scale_small_dimensions, upscale_small_images, MAX_RESOLUTION)
        small = old_w * old_h <= int(max_pixels)
        change_image = (tw, th) != (old_w, old_h) and (not small or upscale_small_images)
        if change_image:
            from comfy.utils import common_upscale
            result = common_upscale(
                image.movedim(-1, 1), tw, th, upscale_method, "disabled"
            ).movedim(1, -1)
            action = "Bild hochskaliert." if small else "Bild verkleinert."
        else:
            result = image
            action = "Bild unveraendert; nur Zielmasse berechnet." if (tw, th) != (old_w, old_h) else "Bild und Zielmasse unveraendert."
        actual_h, actual_w = int(result.shape[1]), int(result.shape[2])
        area, actual_area = tw * th, actual_w * actual_h
        cap = allowed_pixel_limit(max_pixels, limit_overrun_percent)
        error = float(abs(Fraction(tw * old_h, th * old_w) - 1) * 100)
        overrun = max(0.0, 100 * (area - int(max_pixels)) / int(max_pixels))
        info = (
            "Pixel Budget Resize V3.0.0\n"
            f"{action}\n"
            f"QUELLE: {old_w} x {old_h} = {old_w * old_h:,} Pixel\n"
            f"IMAGE-PORT: {actual_w} x {actual_h} = {actual_area:,} Pixel\n"
            f"ZIELMASSE width/height: {tw} x {th} = {area:,} Pixel\n"
            f"pixels-PORT = Zielbreite * Zielhoehe: {area:,}\n"
            f"Basislimit: {int(max_pixels):,}; erlaubte Obergrenze: {cap:,}\n"
            f"Ziel-Nutzung des Basislimits: {100 * area / int(max_pixels):.6f} %\n"
            f"Tatsaechliche Ziel-Ueberschreitung: {overrun:.6f} % "
            f"(erlaubt: {limit_overrun_percent:.4f} %)\n"
            f"Ziel-Verhaeltnisabweichung: {error:.6f} % "
            f"(erlaubt: {max_aspect_error_percent:.4f} %)\n"
            f"Raster: {int(dimension_multiple)}; Ziel rasterkonform: "
            f"{'ja' if tw % int(dimension_multiple) == 0 and th % int(dimension_multiple) == 0 else 'nein'}\n"
            f"scale_small_dimensions: {'AN' if scale_small_dimensions else 'AUS'}; "
            f"upscale_small_images: {'AN' if upscale_small_images else 'AUS'}\n"
            f"Optimierung: {optimization}"
        )
        if (actual_w, actual_h) != (tw, th):
            info += "\nHINWEIS: IMAGE und Zielmasse absichtlich verschieden. Fuer gleich grosses ControlNet-Bild upscale_small_images aktivieren."
        if small and upscale_small_images and not scale_small_dimensions:
            info += "\nHINWEIS: Bild-Hochskalierung aktiviert automatisch auch die Zielberechnung."
        return result, tw, th, area, info


# Retain the current V2 workflow ID, but register ONE implementation only.
# No legacy alias and no separate size-check node: add-node menu has one entry.
NODE_CLASS_MAPPINGS = {"PixelBudgetResizeV2": PixelBudgetResize}
NODE_DISPLAY_NAME_MAPPINGS = {"PixelBudgetResizeV2": "Pixel Budget Resize V3 (Flexible)"}
