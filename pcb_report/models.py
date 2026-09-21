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
class BomVariant:
    """One assembly variant (e.g. Altium project variants like "Critical" /
    "NotCritical" / a plain, non-variant BOM) — its own component list and,
    when a matching pick-and-place source was found for it, its own
    placements. Several variants can be embedded in one report so the user
    picks which one they're currently assembling without re-running the
    tool."""

    name: str
    components: list[BomComponent] = field(default_factory=list)
    placements: dict[str, Placement] = field(default_factory=dict)
    source_bom: str = ""
    source_pnp: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "components": [c.to_dict() for c in self.components],
            "placements": {designator: p.to_dict() for designator, p in self.placements.items()},
        }


@dataclass
class GerberLayer:
    """One rendered Gerber/Excellon file, kept separate (rather than baked
    into one merged image) so the report can offer a per-layer visibility
    toggle — layer-type classification is a best-effort heuristic and real
    projects regularly have layers it gets wrong or that are only useful
    sometimes (fab verification), so letting the viewer show/hide any of
    them directly beats re-running the tool with different flags."""

    name: str
    layer_type: str
    side: str
    svg: str
    default_visible: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.layer_type,
            "side": self.side,
            "svg": self.svg,
            "defaultVisible": self.default_visible,
        }


@dataclass
class GerberRenderResult:
    layers: list[GerberLayer] = field(default_factory=list)
    view_box: Optional[ViewBox] = None
    warnings: list[str] = field(default_factory=list)
    # designator -> recolored SVG snippet of its real silkscreen/courtyard
    # outline (native board coordinates), for designators where one could be
    # confidently matched. Absent designators fall back to a generic marker.
    component_shapes: dict[str, str] = field(default_factory=dict)
