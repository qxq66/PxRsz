"""ComfyUI Pixel Budget Resize V2: bounded pixels, explicit aspect tolerance.

No third-party dependencies beyond an existing ComfyUI installation.
Pure dimension calculation is importable without torch or ComfyUI.
"""
from fractions import Fraction
from math import isfinite, isqrt

__version__ = "2.0.0"


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
    overrun = _percent(limit_overrun_percent, "limit_overrun_percent", 100)
    return (base * (1 + overrun)).numerator // (base * (1 + overrun)).denominator


def calculate_dimensions(width, height, max_pixels=1048576, dimension_multiple=16,
                         limit_overrun_percent=0.0, max_aspect_error_percent=1.5,
                         optimization="closest_to_limit"):
    """Return globally optimal integer dimensions within the explicit constraints.

    smaller images <= the BASE budget are never modified, including off-grid images.
    Downscaling candidates must obey grid, aspect tolerance, allowed cap and
    width<=source_width AND height<=source_height. Aspect error is measured as
    abs((output_width/output_height)/(source_width/source_height)-1)*100.
    Fractions/integer arithmetic make all constraint checks exact.
    """
    w, h, base, multiple = map(int, (width, height, max_pixels, dimension_multiple))
    if (w, h, base, multiple) != (width, height, max_pixels, dimension_multiple):
        raise ValueError("Breite, Hoehe, Pixelbudget und Raster muessen ganzzahlig sein.")
    if min(w, h, base, multiple) < 1:
        raise ValueError("Breite, Hoehe, Pixelbudget und Raster muessen positiv sein.")
    tolerance = _percent(max_aspect_error_percent, "max_aspect_error_percent", 50)
    cap = allowed_pixel_limit(base, limit_overrun_percent)
    if optimization not in ("closest_to_limit", "maximize_allowed_pixels"):
        raise ValueError("Unbekannte optimization.")
    if w * h <= base:
        return w, h

    ratio = Fraction(w, h)
    lower = ratio * (1 - tolerance)
    upper = ratio * (1 + tolerance)

    max_w = min(w, cap // multiple,
                isqrt((cap * upper.numerator) // upper.denominator))
    max_h = min(h, cap // multiple,
                isqrt((cap * lower.denominator) // lower.numerator))
    transpose = max_h < max_w
    if transpose:
        x_limit, y_limit = max_h, w
        r_min, r_max = 1 / upper, 1 / lower
    else:
        x_limit, y_limit = max_w, h
        r_min, r_max = lower, upper

    best = None
    best_score = None
    for x in range(multiple, x_limit + 1, multiple):
        # r_min <= x/y <= r_max; every operation remains integer-exact.
        y_min = _ceil_div(x * r_max.denominator, r_max.numerator)
        y_min = _ceil_div(max(1, y_min), multiple) * multiple
        y_max = min(y_limit, cap // x,
                    (x * r_min.denominator) // r_min.numerator)
        y_max = (y_max // multiple) * multiple
        if y_min > y_max:
            continue
        if optimization == "maximize_allowed_pixels":
            candidates = (y_max,)
        else:
            y_floor = (base // (x * multiple)) * multiple
            candidates = {max(y_min, min(y_max, y_floor)),
                          max(y_min, min(y_max, y_floor + multiple))}
        for y in candidates:
            nw, nh = (y, x) if transpose else (x, y)
            area = nw * nh
            error = abs(Fraction(nw * h, nh * w) - 1)
            if optimization == "closest_to_limit":
                score = (abs(area - base), area > base, error, nw, nh)
            else:
                score = (-area, error, nw, nh)
            if best_score is None or score < best_score:
                best_score = score
                best = nw, nh
    if best is None:
        raise ValueError(
            f"Keine zulaessige Groesse fuer {w} x {h}: Basislimit {base:,}, "
            f"erlaubtes Limit {cap:,}, Raster {multiple}, "
            f"maximale Verhaeltnisabweichung {max_aspect_error_percent} %. "
            "max_aspect_error_percent oder limit_overrun_percent erhoehen, "
            "oder dimension_multiple verkleinern. 0 % Verhaeltnistoleranz "
            "erzwingt wieder mathematisch exakte Proportionen und kann sehr "
            "kleine Ergebnisse oder einen unloesbaren Konflikt verursachen. "
            "Es wird nicht beschnitten, aufgefuellt oder hochskaliert."
        )
    return best


class PixelBudgetResizeV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "max_pixels": ("INT", {"default": 1048576, "min": 1,
                    "max": 1099511627776, "step": 1,
                    "tooltip": "Basislimit: Breite mal Hoehe pro Bild."}),
                "dimension_multiple": ("INT", {"default": 16, "min": 1,
                    "max": 512, "step": 1,
                    "tooltip": "1 fuer freie Bildmasse, 16 fuer SD3. Gilt nur bei Verkleinerung."}),
                "upscale_method": (["lanczos", "area", "bicubic", "bilinear", "nearest-exact"],),
            },
            "optional": {
                "limit_overrun_percent": ("FLOAT", {"default": 0.0, "min": 0.0,
                    "max": 100.0, "step": 0.01,
                    "tooltip": "Erlaubte Ueberschreitung des Basis-Pixelbudgets in Prozent. 0 = harte Grenze."}),
                "max_aspect_error_percent": ("FLOAT", {"default": 1.5, "min": 0.0,
                    "max": 50.0, "step": 0.01,
                    "tooltip": "Maximale relative Abweichung von Breite/Hoehe in Prozent. 0 = mathematisch exakt."}),
                "optimization": (["closest_to_limit", "maximize_allowed_pixels"],
                    {"tooltip": "closest_to_limit: moeglichst nahe am BASISlimit. maximize_allowed_pixels: erhoehtes Limit voll ausnutzen."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "INT", "STRING", "FLOAT", "FLOAT", "INT", "FLOAT")
    RETURN_NAMES = ("image", "width", "height", "pixels", "info",
                    "aspect_error_percent", "limit_usage_percent", "allowed_max_pixels",
                    "actual_overrun_percent")
    FUNCTION = "resize"
    CATEGORY = "image/resize/pixel budget"
    DESCRIPTION = (
        "V2: Findet die naechste erlaubte Pixelzahl zum Budget mit expliziter "
        "Seitenverhaeltnis-Toleranz und optionaler Pixelbudget-Ueberschreitung. "
        "Kleinere Bilder bleiben identisch; keine Ausschnitte, Raender oder Vergroesserung."
    )

    def resize(self, image, max_pixels, dimension_multiple, upscale_method,
               limit_overrun_percent=0.0, max_aspect_error_percent=1.5,
               optimization="closest_to_limit"):
        old_h, old_w = int(image.shape[1]), int(image.shape[2])
        new_w, new_h = calculate_dimensions(
            old_w, old_h, max_pixels, dimension_multiple,
            limit_overrun_percent, max_aspect_error_percent, optimization)
        if (new_w, new_h) == (old_w, old_h):
            result = image
            action = "Unveraendert: keine Groessenaenderung."
        else:
            from comfy.utils import common_upscale
            result = common_upscale(
                image.movedim(-1, 1), new_w, new_h, upscale_method, "disabled"
            ).movedim(1, -1)
            action = "Verkleinert; kein Beschnitt, kein Rand, kein Upscaling."
        area = new_w * new_h
        cap = allowed_pixel_limit(max_pixels, limit_overrun_percent)
        signed_aspect = float((Fraction(new_w * old_h, new_h * old_w) - 1) * 100)
        aspect_error = abs(signed_aspect)
        usage = area / int(max_pixels) * 100
        overrun = max(0.0, (area - int(max_pixels)) / int(max_pixels) * 100)
        grid_ok = new_w % int(dimension_multiple) == 0 and new_h % int(dimension_multiple) == 0
        info = (
            "Pixel Budget Resize V2.0.0\n"
            f"{action}\n"
            f"Quelle: {old_w} x {old_h} = {old_w * old_h:,} Pixel\n"
            f"Ausgabe: {new_w} x {new_h} = {area:,} Pixel\n"
            f"Basislimit: {int(max_pixels):,} Pixel\n"
            f"Erlaubte Ueberschreitung: {limit_overrun_percent:.4f} %\n"
            f"Erlaubte Obergrenze: {cap:,} Pixel\n"
            f"Nutzung des Basislimits: {usage:.6f} %\n"
            f"Tatsaechliche Ueberschreitung: {overrun:.6f} %\n"
            f"Abstand zum Basislimit: {area - int(max_pixels):+,} Pixel\n"
            f"Seitenverhaeltnis Quelle/Ausgabe: {old_w / old_h:.9f} / {new_w / new_h:.9f}\n"
            f"Verhaeltnisabweichung: {aspect_error:.6f} % (erlaubt: {max_aspect_error_percent:.4f} %)\n"
            f"Raster: {int(dimension_multiple)}; Ausgabe rasterkonform: {'ja' if grid_ok else 'nein'}\n"
            f"Optimierung: {optimization}"
        )
        if old_w * old_h <= int(max_pixels) and not grid_ok:
            info += ("\nHINWEIS: Kleineres Bild absichtlich unveraendert. "
                     "Das gewuenschte Raster gilt dann nicht; Latent-Node ggf. ungeeignet.")
        return result, new_w, new_h, area, info, aspect_error, usage, cap, overrun


class ExactSD3SizeCheck:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "width": ("INT", {"forceInput": True}),
            "height": ("INT", {"forceInput": True}),
        }}

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "info")
    FUNCTION = "check"
    CATEGORY = "image/resize/pixel budget"

    def check(self, width, height):
        from nodes import MAX_RESOLUTION
        if not (16 <= width <= MAX_RESOLUTION and 16 <= height <= MAX_RESOLUTION):
            raise ValueError(f"SD3-Groesse ausserhalb des Bereichs 16..{MAX_RESOLUTION}: {width} x {height}.")
        if width % 16 or height % 16:
            raise ValueError(
                f"{width} x {height} passt nicht in das SD3-16er-Raster. "
                "Kleinere Bilder bleiben unveraendert. Fuer notwendige "
                "Verkleinerungen dimension_multiple=16 verwenden. "
                "Diese Pruefung veraendert das Bild nicht."
            )
        return int(width), int(height), f"SD3-Groesse OK: {width} x {height}; {width * height:,} Pixel."


NODE_CLASS_MAPPINGS = {
    "PixelBudgetResizeV2": PixelBudgetResizeV2,
    # Same original node ID, original first four widgets and first five outputs:
    "ExactPixelBudgetResize": PixelBudgetResizeV2,
    "ExactSD3SizeCheck": ExactSD3SizeCheck,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "PixelBudgetResizeV2": "Pixel Budget Resize V2 (Flexible)",
    "ExactPixelBudgetResize": "Pixel Budget Resize V2 (Updated Legacy ID)",
    "ExactSD3SizeCheck": "SD3 Size Check (Strict)",
}
