"""Shared data model for the report generator."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class BomComponent:
    id: str
    designators: list[str]
    value: Optional[str] = None
    footprint: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    mpn: Optional[str] = None
    quantity: Optional[int] = None
    delivered: bool = False
    mounted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Placement:
    designator: str
    x: float
    y: float
    rotation: float = 0.0
    side: str = "top"
    manual: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ViewBox:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GerberRenderResult:
    top_svg: Optional[str] = None
    bottom_svg: Optional[str] = None
    view_box: Optional[ViewBox] = None
    warnings: list[str] = field(default_factory=list)
