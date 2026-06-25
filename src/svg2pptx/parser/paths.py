"""SVG path element parsing using svgpathtools."""

from dataclasses import dataclass, field
from typing import Optional

from svg2pptx.parser.styles import Style, parse_style
from svg2pptx.parser.transforms import Transform, parse_transform
from svg2pptx.parser.segments import (
    PathSegment,
    MoveToSeg,
    LineToSeg,
    CubicBezierToSeg,
    QuadBezierToSeg,
    ArcSeg,
    CloseSeg,
)


@dataclass
class PathShape:
    """
    Parsed SVG path data.

    A path is stored as a flat list of typed segments.  Subpath boundaries are
    indicated by MoveToSeg; closed subpaths end with CloseSeg.
    """

    shape_type: str = "path"
    style: Style = field(default_factory=Style)
    transform: Transform = field(default_factory=Transform.identity)
    element_id: Optional[str] = None
    segments: list[PathSegment] = field(default_factory=list)


def parse_path(
    element,
    parent_style: Optional[Style] = None,
    parent_transform: Optional[Transform] = None,
    curve_tolerance: float = 1.0,
) -> Optional[PathShape]:
    """
    Parse an SVG path element.

    Uses svgpathtools to parse the d attribute, preserving bezier curves and
    arcs as typed segments so the PPTX writer can emit native OOXML elements.

    Args:
        element: ElementTree element for a <path>.
        parent_style: Parent element's style for inheritance.
        parent_transform: Parent element's transform.
        curve_tolerance: Unused (kept for API compatibility; curves are now
            stored natively rather than approximated at parse time).

    Returns:
        PathShape object or None if parsing fails.
    """
    try:
        from svgpathtools import parse_path as svgpathtools_parse
        from svgpathtools import Line, CubicBezier, QuadraticBezier, Arc
    except ImportError:
        return _parse_path_basic(element, parent_style, parent_transform)

    style = parse_style(element, parent_style)
    local_transform = parse_transform(element.get("transform", ""))
    element_id = element.get("id")

    if parent_transform:
        transform = parent_transform.compose(local_transform)
    else:
        transform = local_transform

    d_attr = element.get("d", "")
    if not d_attr:
        return None

    try:
        path = svgpathtools_parse(d_attr)
    except Exception:
        return None

    segments: list[PathSegment] = []
    current_end: Optional[tuple[float, float]] = None

    for segment in path:
        start = (segment.start.real, segment.start.imag)
        end = (segment.end.real, segment.end.imag)

        # Emit MoveTo when a new subpath begins (gap between segments)
        if current_end is None or not _points_close(start, current_end):
            segments.append(MoveToSeg(start[0], start[1]))

        if isinstance(segment, Line):
            segments.append(LineToSeg(end[0], end[1]))

        elif isinstance(segment, CubicBezier):
            cp1 = (segment.control1.real, segment.control1.imag)
            cp2 = (segment.control2.real, segment.control2.imag)
            segments.append(CubicBezierToSeg(cp1, cp2, end))

        elif isinstance(segment, QuadraticBezier):
            cp = (segment.control.real, segment.control.imag)
            segments.append(QuadBezierToSeg(cp, end))

        elif isinstance(segment, Arc):
            segments.append(ArcSeg(
                rx=segment.radius.real,
                ry=segment.radius.imag,
                x_rotation=segment.rotation,
                large_arc=segment.large_arc,
                sweep=segment.sweep,
                x=end[0],
                y=end[1],
            ))

        current_end = end

    # svgpathtools converts Z to a Line back to the subpath start.
    # Replace those closing lines with CloseSeg.
    segments = _replace_close_lines(segments)

    if not segments:
        return None

    return PathShape(
        shape_type="path",
        style=style,
        transform=transform,
        element_id=element_id,
        segments=segments,
    )


def _replace_close_lines(segments: list[PathSegment]) -> list[PathSegment]:
    """Replace LineToSeg that returns to the subpath start with CloseSeg."""
    result: list[PathSegment] = []
    subpath_start: Optional[tuple[float, float]] = None

    for seg in segments:
        if isinstance(seg, MoveToSeg):
            subpath_start = (seg.x, seg.y)
            result.append(seg)
        elif isinstance(seg, LineToSeg) and subpath_start is not None:
            if _points_close((seg.x, seg.y), subpath_start):
                result.append(CloseSeg())
            else:
                result.append(seg)
        else:
            result.append(seg)

    return result


def _points_close(
    p1: tuple[float, float], p2: tuple[float, float], epsilon: float = 0.01
) -> bool:
    """Check if two points are close enough to be considered equal."""
    return abs(p1[0] - p2[0]) < epsilon and abs(p1[1] - p2[1]) < epsilon


def _parse_path_basic(
    element,
    parent_style: Optional[Style] = None,
    parent_transform: Optional[Transform] = None,
) -> Optional[PathShape]:
    """
    Basic path parsing fallback without svgpathtools.

    Supports M, L, H, V, Z.  Curve commands are skipped.
    """
    import re

    style = parse_style(element, parent_style)
    local_transform = parse_transform(element.get("transform", ""))
    element_id = element.get("id")

    if parent_transform:
        transform = parent_transform.compose(local_transform)
    else:
        transform = local_transform

    d_attr = element.get("d", "")
    if not d_attr:
        return None

    tokens = re.findall(r"([MmLlHhVvZzCcSsQqTtAa])|(-?[\d.]+(?:e[+-]?\d+)?)", d_attr)

    segments: list[PathSegment] = []
    current_x, current_y = 0.0, 0.0
    subpath_start = (0.0, 0.0)
    command = ""

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token[0]:
            command = token[0]
            i += 1
            if command.upper() == "Z":
                segments.append(CloseSeg())
                current_x, current_y = subpath_start
        elif token[1]:
            if command.upper() == "M":
                x = float(token[1])
                i += 1
                y = float(tokens[i][1]) if i < len(tokens) and tokens[i][1] else 0.0
                i += 1
                if command == "m":
                    x += current_x
                    y += current_y
                segments.append(MoveToSeg(x, y))
                current_x, current_y = x, y
                subpath_start = (x, y)
                command = "L" if command == "M" else "l"

            elif command.upper() == "L":
                x = float(token[1])
                i += 1
                y = float(tokens[i][1]) if i < len(tokens) and tokens[i][1] else 0.0
                i += 1
                if command == "l":
                    x += current_x
                    y += current_y
                segments.append(LineToSeg(x, y))
                current_x, current_y = x, y

            elif command.upper() == "H":
                x = float(token[1])
                i += 1
                if command == "h":
                    x += current_x
                segments.append(LineToSeg(x, current_y))
                current_x = x

            elif command.upper() == "V":
                y = float(token[1])
                i += 1
                if command == "v":
                    y += current_y
                segments.append(LineToSeg(current_x, y))
                current_y = y

            else:
                # Skip unsupported curve commands
                i += 1
        else:
            i += 1

    if not segments:
        return None

    return PathShape(
        shape_type="path",
        style=style,
        transform=transform,
        element_id=element_id,
        segments=segments,
    )
