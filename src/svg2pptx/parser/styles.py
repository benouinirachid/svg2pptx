"""SVG style attribute parsing."""

import re
from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class GradientStop:
    """A single stop in a gradient."""

    offset: float
    color: str
    opacity: float = 1.0


@dataclass
class LinearGradient:
    """Parsed SVG linearGradient definition."""

    stops: list  # list[GradientStop]
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 1.0
    y2: float = 0.0
    gradient_units: str = "objectBoundingBox"


@dataclass
class RadialGradient:
    """Parsed SVG radialGradient definition.

    OOXML radial gradients are far less expressive than SVG: they fill inward
    from the shape's bounding rectangle toward a focus point, with no true
    radius or elliptical control. Only the stop list, center/focus, and units
    are preserved; the writer renders a centered (optionally focus-shifted)
    circular approximation.
    """

    stops: list  # list[GradientStop]
    cx: float = 0.5
    cy: float = 0.5
    r: float = 0.5
    fx: Optional[float] = None
    fy: Optional[float] = None
    gradient_units: str = "objectBoundingBox"


# A paint that is a gradient (either kind).
Gradient = Union[LinearGradient, RadialGradient]


# Named CSS colors to RGB hex
CSS_COLORS = {
    "black": "#000000",
    "white": "#ffffff",
    "red": "#ff0000",
    "green": "#008000",
    "blue": "#0000ff",
    "yellow": "#ffff00",
    "cyan": "#00ffff",
    "magenta": "#ff00ff",
    "gray": "#808080",
    "grey": "#808080",
    "silver": "#c0c0c0",
    "maroon": "#800000",
    "olive": "#808000",
    "lime": "#00ff00",
    "aqua": "#00ffff",
    "teal": "#008080",
    "navy": "#000080",
    "fuchsia": "#ff00ff",
    "purple": "#800080",
    "orange": "#ffa500",
    "pink": "#ffc0cb",
    "brown": "#a52a2a",
    "coral": "#ff7f50",
    "crimson": "#dc143c",
    "darkblue": "#00008b",
    "darkgray": "#a9a9a9",
    "darkgreen": "#006400",
    "darkred": "#8b0000",
    "gold": "#ffd700",
    "indigo": "#4b0082",
    "ivory": "#fffff0",
    "khaki": "#f0e68c",
    "lavender": "#e6e6fa",
    "lightblue": "#add8e6",
    "lightgray": "#d3d3d3",
    "lightgreen": "#90ee90",
    "lightyellow": "#ffffe0",
    "skyblue": "#87ceeb",
    "steelblue": "#4682b4",
    "tomato": "#ff6347",
    "turquoise": "#40e0d0",
    "violet": "#ee82ee",
    "wheat": "#f5deb3",
    "transparent": "none",
}

# Pattern for rgb() and rgba() colors
RGB_PATTERN = re.compile(
    r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE
)
RGBA_PATTERN = re.compile(
    r"rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)",
    re.IGNORECASE,
)

# Pattern for gradient references like url(#gradientId)
URL_REF_PATTERN = re.compile(r"url\s*\(\s*#([^)]+)\s*\)", re.IGNORECASE)

# Gradient definitions registry, keyed by gradient ID (without #)
_gradients: dict[str, "Gradient"] = {}


@dataclass
class Style:
    """
    Parsed SVG style attributes.

    Attributes:
        fill: Fill color as hex string or "none".
        fill_opacity: Fill opacity (0.0 to 1.0).
        stroke: Stroke color as hex string or "none".
        stroke_width: Stroke width in pixels.
        stroke_opacity: Stroke opacity (0.0 to 1.0).
        opacity: Overall opacity (0.0 to 1.0).
        font_family: Font family name.
        font_size: Font size in pixels.
        font_weight: Font weight (normal, bold, or numeric).
        text_anchor: Text anchor (start, middle, end).
    """

    fill: str = "none"
    fill_opacity: float = 1.0
    stroke: str = "none"
    stroke_width: float = 1.0
    stroke_opacity: float = 1.0
    opacity: float = 1.0
    font_family: str = "Arial"
    font_size: float = 12.0
    font_weight: str = "normal"
    text_anchor: str = "start"
    gradient_fill: Optional["Gradient"] = None
    gradient_stroke: Optional["Gradient"] = None

    def with_parent(self, parent: "Style") -> "Style":
        """
        Create a new style inheriting from a parent style.

        Child values override parent values if explicitly set.
        """
        return Style(
            fill=self.fill if self.fill != "inherit" else parent.fill,
            fill_opacity=self.fill_opacity,
            stroke=self.stroke if self.stroke != "inherit" else parent.stroke,
            stroke_width=self.stroke_width,
            stroke_opacity=self.stroke_opacity,
            opacity=self.opacity * parent.opacity,
            font_family=(
                self.font_family
                if self.font_family != "inherit"
                else parent.font_family
            ),
            font_size=(
                self.font_size
                if self.font_size > 0
                else parent.font_size
            ),
            font_weight=(
                self.font_weight
                if self.font_weight != "inherit"
                else parent.font_weight
            ),
            text_anchor=(
                self.text_anchor
                if self.text_anchor != "inherit"
                else parent.text_anchor
            ),
            gradient_fill=self.gradient_fill if self.gradient_fill is not None else parent.gradient_fill,
            gradient_stroke=self.gradient_stroke if self.gradient_stroke is not None else parent.gradient_stroke,
        )

    @property
    def effective_fill_opacity(self) -> float:
        """Combined fill and overall opacity."""
        return self.fill_opacity * self.opacity

    @property
    def effective_stroke_opacity(self) -> float:
        """Combined stroke and overall opacity."""
        return self.stroke_opacity * self.opacity


def clear_gradient_registry() -> None:
    """Clear the gradient registry. Call before parsing a new SVG."""
    _gradients.clear()


def get_gradient(gradient_id: str) -> Optional["Gradient"]:
    """Return the full gradient (linear or radial) for the id, or None."""
    return _gradients.get(gradient_id)


def _resolve_gradient_ref(paint_value: str) -> Optional["Gradient"]:
    """Resolve a paint value to a gradient if it is a url(#id) to a known one."""
    if not paint_value:
        return None
    url_match = URL_REF_PATTERN.match(paint_value.strip())
    if not url_match:
        return None
    return get_gradient(url_match.group(1))


def _parse_gradient_coord(value: str, default: float) -> float:
    """Parse a gradient coordinate, handling percentage or plain number."""
    if not value:
        return default
    value = value.strip()
    if value.endswith("%"):
        return float(value[:-1]) / 100.0
    return float(value)


def _parse_stop_element(stop_element) -> Optional["GradientStop"]:
    """Parse a <stop> element into a GradientStop."""
    # Merge style attribute and direct attributes (style takes precedence)
    style_str = stop_element.get("style", "")
    style_dict: dict[str, str] = {}
    for decl in style_str.split(";"):
        decl = decl.strip()
        if ":" in decl:
            prop, val = decl.split(":", 1)
            style_dict[prop.strip().lower()] = val.strip()

    stop_color = style_dict.get("stop-color") or stop_element.get("stop-color")
    if not stop_color:
        return None
    color = _parse_color_value(stop_color)
    if not color or color == "none":
        return None

    stop_opacity_str = style_dict.get("stop-opacity") or stop_element.get("stop-opacity", "1")
    try:
        opacity = float(stop_opacity_str)
    except (ValueError, TypeError):
        opacity = 1.0

    offset_str = stop_element.get("offset", "0").strip()
    if offset_str.endswith("%"):
        offset = float(offset_str[:-1]) / 100.0
    else:
        try:
            offset = float(offset_str)
        except ValueError:
            offset = 0.0

    return GradientStop(offset=offset, color=color, opacity=opacity)


def _apply_matrix_to_direction(dx: float, dy: float, transform_str: str) -> tuple[float, float]:
    """Apply a matrix(...) gradientTransform to a direction vector, ignoring translation."""
    if not transform_str:
        return dx, dy
    transform_str = transform_str.strip()
    if not transform_str.lower().startswith("matrix"):
        return dx, dy
    nums = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", transform_str[6:])
    if len(nums) < 6:
        return dx, dy
    a, b, c, d = float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])
    return a * dx + c * dy, b * dx + d * dy


def _collect_stops(element) -> list:
    """Collect GradientStop objects from direct <stop> children."""
    stops: list[GradientStop] = []
    for stop_elem in element:
        stop_tag = stop_elem.tag
        if "}" in stop_tag:
            stop_tag = stop_tag.split("}")[-1]
        if stop_tag.lower() != "stop":
            continue
        parsed = _parse_stop_element(stop_elem)
        if parsed is not None:
            stops.append(parsed)
    return stops


def _href_from_element(element) -> Optional[str]:
    """Return the bare id (without #) from xlink:href or href, or None."""
    xlink_ns = "http://www.w3.org/1999/xlink"
    href = (
        element.get(f"{{{xlink_ns}}}href")
        or element.get("href")
        or element.get("xlink:href")
    )
    if href and href.startswith("#"):
        return href[1:]
    return None


def parse_gradients_from_defs(defs_element) -> None:
    """
    Parse gradient definitions from a <defs> element and register them.

    Handles xlink:href stop-inheritance and gradientTransform.

    Args:
        defs_element: ElementTree element representing the <defs> section.
    """
    # First pass: collect raw data for every gradient element
    raw: dict[str, dict] = {}
    for child in defs_element:
        tag = child.tag
        if "}" in tag:
            tag = tag.split("}")[-1]
        tag = tag.lower()

        if tag not in ("lineargradient", "radialgradient"):
            continue

        grad_id = child.get("id")
        if not grad_id:
            continue

        raw[grad_id] = {
            "tag": tag,
            "stops": _collect_stops(child),
            "href": _href_from_element(child),
            "x1": child.get("x1"),
            "y1": child.get("y1"),
            "x2": child.get("x2"),
            "y2": child.get("y2"),
            "cx": child.get("cx"),
            "cy": child.get("cy"),
            "r": child.get("r"),
            "fx": child.get("fx"),
            "fy": child.get("fy"),
            "gradient_units": child.get("gradientUnits", "objectBoundingBox"),
            "gradient_transform": child.get("gradientTransform", ""),
        }

    # Second pass: resolve href references and register gradients
    for grad_id, info in raw.items():
        stops = info["stops"]
        # Inherit stops from href if this gradient has none
        if not stops and info["href"]:
            ref = raw.get(info["href"])
            if ref:
                stops = ref["stops"]

        if not stops:
            continue

        if info["tag"] == "lineargradient":
            try:
                x1 = _parse_gradient_coord(info["x1"] or "0", 0.0)
                y1 = _parse_gradient_coord(info["y1"] or "0", 0.0)
                x2 = _parse_gradient_coord(info["x2"] or "1", 1.0)
                y2 = _parse_gradient_coord(info["y2"] or "0", 0.0)
            except ValueError:
                x1, y1, x2, y2 = 0.0, 0.0, 1.0, 0.0

            # Apply gradientTransform to the direction vector so the angle
            # stored in LinearGradient is already in screen space.
            dx, dy = x2 - x1, y2 - y1
            if info["gradient_transform"]:
                dx, dy = _apply_matrix_to_direction(dx, dy, info["gradient_transform"])

            gradient = LinearGradient(
                stops=stops,
                x1=0.0,
                y1=0.0,
                x2=dx,
                y2=dy,
                gradient_units=info["gradient_units"],
            )
            _gradients[grad_id] = gradient

        elif info["tag"] == "radialgradient":
            ref = raw.get(info["href"]) if info["href"] else None

            def inherited(key: str):
                """Attribute from this element, falling back to the href'd one."""
                val = info.get(key)
                if val is None and ref is not None:
                    val = ref.get(key)
                return val

            try:
                cx = _parse_gradient_coord(inherited("cx") or "0.5", 0.5)
                cy = _parse_gradient_coord(inherited("cy") or "0.5", 0.5)
                r = _parse_gradient_coord(inherited("r") or "0.5", 0.5)
            except ValueError:
                cx, cy, r = 0.5, 0.5, 0.5

            fx_raw = inherited("fx")
            fy_raw = inherited("fy")
            try:
                fx = _parse_gradient_coord(fx_raw, cx) if fx_raw is not None else None
                fy = _parse_gradient_coord(fy_raw, cy) if fy_raw is not None else None
            except ValueError:
                fx, fy = None, None

            gradient = RadialGradient(
                stops=stops,
                cx=cx,
                cy=cy,
                r=r,
                fx=fx,
                fy=fy,
                gradient_units=info["gradient_units"],
            )
            _gradients[grad_id] = gradient


def _parse_color_value(color_str: str) -> str:
    """
    Internal helper to parse a color value without url() handling.

    This avoids infinite recursion when parsing gradient stop colors.
    """
    if not color_str:
        return "none"

    color_str = color_str.strip().lower()

    # Handle special values
    if color_str in ("none", "transparent", ""):
        return "none"
    if color_str == "currentcolor":
        return "#000000"  # Default to black

    # Named colors
    if color_str in CSS_COLORS:
        return CSS_COLORS[color_str]

    # Hex colors
    if color_str.startswith("#"):
        if len(color_str) == 4:
            # Short hex (#rgb -> #rrggbb)
            return "#" + "".join(c * 2 for c in color_str[1:])
        elif len(color_str) == 7:
            return color_str
        elif len(color_str) == 9:
            # #rrggbbaa - strip alpha
            return color_str[:7]

    # rgb() format
    rgb_match = RGB_PATTERN.match(color_str)
    if rgb_match:
        r, g, b = [int(x) for x in rgb_match.groups()]
        return f"#{r:02x}{g:02x}{b:02x}"

    # rgba() format
    rgba_match = RGBA_PATTERN.match(color_str)
    if rgba_match:
        r, g, b = [int(x) for x in rgba_match.groups()[:3]]
        return f"#{r:02x}{g:02x}{b:02x}"

    # Unknown format, return as-is
    return color_str


def parse_color(color_str: str) -> str:
    """
    Parse an SVG/CSS color value.

    Args:
        color_str: Color string (hex, rgb(), named color, url(#gradient), or "none").

    Returns:
        Normalized hex color string (e.g., "#ff0000") or "none".
    """
    if not color_str:
        return "none"

    color_str_stripped = color_str.strip()
    color_str_lower = color_str_stripped.lower()

    # Handle special values
    if color_str_lower in ("none", "transparent", ""):
        return "none"
    if color_str_lower == "currentcolor":
        return "#000000"  # Default to black

    # url() paint references (gradients are resolved before reaching here, so
    # any remaining reference — patterns, unknown ids — has no flat color).
    if URL_REF_PATTERN.match(color_str_stripped):
        return "none"

    # Named colors
    if color_str_lower in CSS_COLORS:
        return CSS_COLORS[color_str_lower]

    # Hex colors
    if color_str_lower.startswith("#"):
        if len(color_str_lower) == 4:
            # Short hex (#rgb -> #rrggbb)
            return "#" + "".join(c * 2 for c in color_str_lower[1:])
        elif len(color_str_lower) == 7:
            return color_str_lower
        elif len(color_str_lower) == 9:
            # #rrggbbaa - strip alpha
            return color_str_lower[:7]

    # rgb() format
    rgb_match = RGB_PATTERN.match(color_str_lower)
    if rgb_match:
        r, g, b = [int(x) for x in rgb_match.groups()]
        return f"#{r:02x}{g:02x}{b:02x}"

    # rgba() format
    rgba_match = RGBA_PATTERN.match(color_str_lower)
    if rgba_match:
        r, g, b = [int(x) for x in rgba_match.groups()[:3]]
        return f"#{r:02x}{g:02x}{b:02x}"

    # Unknown format, return as-is
    return color_str_lower


def parse_style_attribute(style_str: str) -> dict[str, str]:
    """
    Parse CSS-style attribute string.

    Args:
        style_str: Style attribute value (e.g., "fill: red; stroke-width: 2").

    Returns:
        Dictionary of property name to value.
    """
    if not style_str:
        return {}

    result = {}
    for declaration in style_str.split(";"):
        declaration = declaration.strip()
        if ":" in declaration:
            prop, value = declaration.split(":", 1)
            result[prop.strip().lower()] = value.strip()

    return result


def parse_style(
    element,
    parent_style: Optional[Style] = None,
    default_fill: str = "none",
    default_stroke: str = "none",
) -> Style:
    """
    Parse style from an SVG element.

    Combines inline style attribute and direct presentation attributes.

    Args:
        element: ElementTree element.
        parent_style: Parent element's style for inheritance.
        default_fill: Default fill color.
        default_stroke: Default stroke color.

    Returns:
        Parsed Style object.
    """
    # Start with defaults or inherit from parent
    if parent_style:
        style = Style(
            fill=parent_style.fill,
            fill_opacity=parent_style.fill_opacity,
            stroke=parent_style.stroke,
            stroke_width=parent_style.stroke_width,
            stroke_opacity=parent_style.stroke_opacity,
            opacity=parent_style.opacity,
            font_family=parent_style.font_family,
            font_size=parent_style.font_size,
            font_weight=parent_style.font_weight,
            text_anchor=parent_style.text_anchor,
            gradient_fill=parent_style.gradient_fill,
            gradient_stroke=parent_style.gradient_stroke,
        )
    else:
        style = Style(fill=default_fill, stroke=default_stroke)

    # Parse inline style attribute
    style_attr = element.get("style", "")
    style_dict = parse_style_attribute(style_attr)

    # Helper to get attribute from style or direct attribute
    def get_attr(name: str, default: Optional[str] = None) -> Optional[str]:
        # Style attribute takes precedence
        if name in style_dict:
            return style_dict[name]
        # Then direct attribute
        val = element.get(name)
        if val is not None:
            return val
        return default

    # Parse fill — detect gradient references before resolving to a flat color
    fill_val = get_attr("fill")
    if fill_val is not None:
        gradient = _resolve_gradient_ref(fill_val)
        if gradient is not None:
            style.gradient_fill = gradient
            style.fill = "none"
        else:
            style.gradient_fill = None
            style.fill = parse_color(fill_val)

    # Parse fill-opacity
    fill_opacity_val = get_attr("fill-opacity")
    if fill_opacity_val is not None:
        try:
            style.fill_opacity = float(fill_opacity_val)
        except ValueError:
            pass

    # Parse stroke — detect gradient references before resolving to a flat color
    stroke_val = get_attr("stroke")
    if stroke_val is not None:
        gradient = _resolve_gradient_ref(stroke_val)
        if gradient is not None:
            style.gradient_stroke = gradient
            style.stroke = "none"
        else:
            style.gradient_stroke = None
            style.stroke = parse_color(stroke_val)

    # Parse stroke-width
    stroke_width_val = get_attr("stroke-width")
    if stroke_width_val is not None:
        try:
            # Remove unit suffix if present
            width_str = re.sub(r"[a-z]+$", "", stroke_width_val.strip(), flags=re.I)
            style.stroke_width = float(width_str)
        except ValueError:
            pass

    # Parse stroke-opacity
    stroke_opacity_val = get_attr("stroke-opacity")
    if stroke_opacity_val is not None:
        try:
            style.stroke_opacity = float(stroke_opacity_val)
        except ValueError:
            pass

    # Parse opacity
    opacity_val = get_attr("opacity")
    if opacity_val is not None:
        try:
            style.opacity = float(opacity_val)
        except ValueError:
            pass

    # Parse font properties
    font_family_val = get_attr("font-family")
    if font_family_val is not None:
        # Remove quotes
        style.font_family = font_family_val.strip("'\"")

    font_size_val = get_attr("font-size")
    if font_size_val is not None:
        try:
            # Simple parsing, assumes px
            size_str = re.sub(r"[a-z]+$", "", font_size_val.strip(), flags=re.I)
            style.font_size = float(size_str)
        except ValueError:
            pass

    font_weight_val = get_attr("font-weight")
    if font_weight_val is not None:
        style.font_weight = font_weight_val

    text_anchor_val = get_attr("text-anchor")
    if text_anchor_val is not None:
        style.text_anchor = text_anchor_val

    return style
