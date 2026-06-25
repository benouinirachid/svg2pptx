"""Path segment types for SVG path commands."""

import math
from dataclasses import dataclass
from typing import Union


@dataclass
class MoveToSeg:
    x: float
    y: float


@dataclass
class LineToSeg:
    x: float
    y: float


@dataclass
class CubicBezierToSeg:
    cp1: tuple[float, float]
    cp2: tuple[float, float]
    end: tuple[float, float]


@dataclass
class QuadBezierToSeg:
    cp: tuple[float, float]
    end: tuple[float, float]


@dataclass
class ArcSeg:
    rx: float
    ry: float
    x_rotation: float  # degrees
    large_arc: bool
    sweep: bool
    x: float
    y: float


@dataclass
class CloseSeg:
    pass


PathSegment = Union[
    MoveToSeg, LineToSeg, CubicBezierToSeg, QuadBezierToSeg, ArcSeg, CloseSeg
]


def apply_transform(transform, segments: list[PathSegment]) -> list[PathSegment]:
    """Apply an affine transform to all coordinates in a list of path segments.

    For ArcSeg, radii are scaled by the linear part of the transform and
    x_rotation is adjusted by the transform's rotation angle.  This is exact
    for rotate/scale/translate transforms and approximate for skews.
    """
    scale_x = math.sqrt(transform.a ** 2 + transform.b ** 2)
    scale_y = math.sqrt(transform.c ** 2 + transform.d ** 2)
    rotation_deg = math.degrees(math.atan2(transform.b, transform.a))

    result = []
    for seg in segments:
        if isinstance(seg, MoveToSeg):
            x, y = transform.apply(seg.x, seg.y)
            result.append(MoveToSeg(x, y))
        elif isinstance(seg, LineToSeg):
            x, y = transform.apply(seg.x, seg.y)
            result.append(LineToSeg(x, y))
        elif isinstance(seg, CubicBezierToSeg):
            cp1 = transform.apply(*seg.cp1)
            cp2 = transform.apply(*seg.cp2)
            end = transform.apply(*seg.end)
            result.append(CubicBezierToSeg(cp1, cp2, end))
        elif isinstance(seg, QuadBezierToSeg):
            cp = transform.apply(*seg.cp)
            end = transform.apply(*seg.end)
            result.append(QuadBezierToSeg(cp, end))
        elif isinstance(seg, ArcSeg):
            end_x, end_y = transform.apply(seg.x, seg.y)
            result.append(ArcSeg(
                rx=seg.rx * scale_x,
                ry=seg.ry * scale_y,
                x_rotation=seg.x_rotation + rotation_deg,
                large_arc=seg.large_arc,
                sweep=seg.sweep,
                x=end_x,
                y=end_y,
            ))
        elif isinstance(seg, CloseSeg):
            result.append(CloseSeg())
    return result
