"""
geometry.py — turn a map-spec into an occupancy grid, then auto-derive
walls, doors (portals), and line-of-sight polylines from the floor boundary.

All coordinates here are in GRID UNITS (cells). A cell (cx, cy) occupies the
square [cx, cx+1] x [cy, cy+1]. The renderer and exporters convert to pixels by
multiplying by cell_px.

A "unit edge" is one cell-side:
    ('H', X, Y)  horizontal edge from (X, Y) to (X+1, Y)
    ('V', X, Y)  vertical   edge from (X, Y) to (X, Y+1)

Walls are the set of unit edges where a floor cell touches a non-floor cell.
Doors remove a unit edge from the wall set and become portals instead.
"""

from collections import defaultdict


def _rect_cells(x, y, w, h):
    for cy in range(int(y), int(y + h)):
        for cx in range(int(x), int(x + w)):
            yield (cx, cy)


def _room_center(room):
    return (room["x"] + room["w"] / 2.0, room["y"] + room["h"] / 2.0)


def _l_corridor_cells(c0, c1, width):
    """L-shaped corridor between two cell-center points, given a width in cells."""
    half = max(1, int(width)) // 2
    x0, y0 = int(c0[0]), int(c0[1])
    x1, y1 = int(c1[0]), int(c1[1])
    cells = set()
    # horizontal leg at y0
    for cx in range(min(x0, x1), max(x0, x1) + 1):
        for d in range(-half, max(1, int(width)) - half):
            cells.add((cx, y0 + d))
    # vertical leg at x1
    for cy in range(min(y0, y1), max(y0, y1) + 1):
        for d in range(-half, max(1, int(width)) - half):
            cells.add((x1 + d, cy))
    return cells


def build_occupancy(spec):
    """Return (floor_set, room_lookup). floor_set is a set of (cx, cy) cells."""
    rooms = spec.get("rooms", [])
    room_by_id = {}
    floor = set()

    for i, room in enumerate(rooms):
        room.setdefault("id", f"room{i}")
        room_by_id[room["id"]] = room
        floor.update(_rect_cells(room["x"], room["y"], room["w"], room["h"]))

    for cor in spec.get("corridors", []):
        if "from" in cor and "to" in cor:
            a = room_by_id.get(cor["from"])
            b = room_by_id.get(cor["to"])
            if not a or not b:
                raise ValueError(
                    f"corridor references unknown room id(s): {cor.get('from')}, {cor.get('to')}"
                )
            floor.update(_l_corridor_cells(_room_center(a), _room_center(b), cor.get("width", 2)))
        else:
            rx = cor.get("x", cor.get("rect", [0, 0, 0, 0])[0])
            if "rect" in cor:
                rx, ry, rw, rh = cor["rect"]
            else:
                rx, ry, rw, rh = cor["x"], cor["y"], cor["w"], cor["h"]
            floor.update(_rect_cells(rx, ry, rw, rh))

    return floor, room_by_id


# --- wall derivation ---------------------------------------------------------

_SIDE_EDGE = {
    # side of cell (cx, cy) -> unit edge key
    "n": lambda cx, cy: ("H", cx, cy),
    "s": lambda cx, cy: ("H", cx, cy + 1),
    "w": lambda cx, cy: ("V", cx, cy),
    "e": lambda cx, cy: ("V", cx + 1, cy),
}
_SIDE_NEIGHBOR = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}


def derive_wall_edges(floor):
    """Set of unit edges on the floor/non-floor boundary."""
    walls = set()
    for (cx, cy) in floor:
        for side, (dx, dy) in _SIDE_NEIGHBOR.items():
            if (cx + dx, cy + dy) not in floor:
                walls.add(_SIDE_EDGE[side](cx, cy))
    return walls


def door_edge(door):
    """Map a door spec {x, y, side} to its unit edge key."""
    side = door.get("side")
    if side in _SIDE_EDGE:
        return _SIDE_EDGE[side](door["x"], door["y"])
    # fallback: orient h = north edge, v = west edge
    orient = door.get("orient", "h")
    return ("H", door["x"], door["y"]) if orient == "h" else ("V", door["x"], door["y"])


def edge_endpoints(edge):
    kind, a, b = edge
    if kind == "H":
        return (a, b), (a + 1, b)
    return (a, b), (a, b + 1)


def merge_edges(walls):
    """Merge colinear contiguous unit edges into maximal straight segments.

    Returns a list of ((x1, y1), (x2, y2)) segments in grid units.
    """
    segments = []

    # horizontal: group by Y, merge runs of X
    by_y = defaultdict(list)
    for kind, a, b in walls:
        if kind == "H":
            by_y[b].append(a)
    for y, xs in by_y.items():
        xs.sort()
        run_start = prev = xs[0]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
            else:
                segments.append(((run_start, y), (prev + 1, y)))
                run_start = prev = x
        segments.append(((run_start, y), (prev + 1, y)))

    # vertical: group by X, merge runs of Y
    by_x = defaultdict(list)
    for kind, a, b in walls:
        if kind == "V":
            by_x[a].append(b)
    for x, ys in by_x.items():
        ys.sort()
        run_start = prev = ys[0]
        for yv in ys[1:]:
            if yv == prev + 1:
                prev = yv
            else:
                segments.append(((x, run_start), (x, prev + 1)))
                run_start = prev = yv
        segments.append(((x, run_start), (x, prev + 1)))

    return segments


def derive(spec):
    """Full pipeline: returns a dict with floor, wall segments, door portals."""
    floor, room_by_id = build_occupancy(spec)
    if not floor:
        raise ValueError("map has no floor cells — define at least one room")

    wall_edges = derive_wall_edges(floor)

    portals = []
    for door in spec.get("doors", []):
        e = door_edge(door)
        wall_edges.discard(e)  # carve the doorway out of the wall
        p0, p1 = edge_endpoints(e)
        portals.append(
            {
                "p0": p0,
                "p1": p1,
                "type": door.get("type", "door"),     # door | blast | secret | airlock
                "state": door.get("state", "closed"),  # closed | open | locked
            }
        )

    segments = merge_edges(wall_edges)
    return {
        "floor": floor,
        "rooms": room_by_id,
        "segments": segments,   # merged straight wall runs in grid units
        "portals": portals,
    }
