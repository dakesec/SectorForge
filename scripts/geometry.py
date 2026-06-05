"""
geometry.py — turn a map-spec into an occupancy grid, then auto-derive walls,
doors (portals), and line-of-sight from the floor boundary.

Rooms may be any shape (rect, ellipse/circle, diamond, octagon, polygon); each
is rasterized to a set of cells, so wall derivation — which works on the
floor/non-floor boundary — is shape-agnostic.

Every floor cell belongs to a *region* (a room id, or a corridor id). Where two
regions touch, the shared edges form an *entrance* (an opening in the bulkhead).
Connection-based doors `{from, to}` are placed exactly across the detected
entrance, so doors always line up with the passages between rooms.

Coordinates are in GRID UNITS (cells). Cell (cx, cy) occupies [cx, cx+1] x
[cy, cy+1]. A "unit edge" is one cell side:
    ('H', X, Y)  horizontal edge from (X, Y) to (X+1, Y)
    ('V', X, Y)  vertical   edge from (X, Y) to (X, Y+1)
"""

import math
import random
from collections import defaultdict, deque


# --- room shapes -------------------------------------------------------------

def _rect_cells(x, y, w, h):
    return {(cx, cy)
            for cy in range(int(y), int(y + h))
            for cx in range(int(x), int(x + w))}


def _ellipse_cells(x, y, w, h):
    cx0, cy0 = x + w / 2.0, y + h / 2.0
    rx, ry = w / 2.0, h / 2.0
    cells = set()
    for cy in range(int(math.floor(y)), int(math.ceil(y + h))):
        for cx in range(int(math.floor(x)), int(math.ceil(x + w))):
            nx, ny = (cx + 0.5 - cx0) / rx, (cy + 0.5 - cy0) / ry
            if nx * nx + ny * ny <= 1.0:
                cells.add((cx, cy))
    return cells


def _diamond_cells(x, y, w, h):
    cx0, cy0 = x + w / 2.0, y + h / 2.0
    rx, ry = w / 2.0, h / 2.0
    cells = set()
    for cy in range(int(math.floor(y)), int(math.ceil(y + h))):
        for cx in range(int(math.floor(x)), int(math.ceil(x + w))):
            nx, ny = abs(cx + 0.5 - cx0) / rx, abs(cy + 0.5 - cy0) / ry
            if nx + ny <= 1.0:
                cells.add((cx, cy))
    return cells


def _octagon_cells(x, y, w, h, cut=None):
    if cut is None:
        cut = max(1, int(round(min(w, h) * 0.3)))
    cells = set()
    for j in range(int(h)):
        for i in range(int(w)):
            if (i + j < cut or (w - 1 - i) + j < cut
                    or i + (h - 1 - j) < cut or (w - 1 - i) + (h - 1 - j) < cut):
                continue
            cells.add((int(x) + i, int(y) + j))
    return cells


def _point_in_poly(px, py, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _poly_cells(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    cells = set()
    for cy in range(int(math.floor(min(ys))), int(math.ceil(max(ys)))):
        for cx in range(int(math.floor(min(xs))), int(math.ceil(max(xs)))):
            if _point_in_poly(cx + 0.5, cy + 0.5, points):
                cells.add((cx, cy))
    return cells


def room_cells(room):
    shape = room.get("shape", "rect").lower()
    if shape in ("circle", "ellipse", "round", "oval", "dome"):
        return _ellipse_cells(room["x"], room["y"], room["w"], room["h"])
    if shape in ("diamond", "rhombus"):
        return _diamond_cells(room["x"], room["y"], room["w"], room["h"])
    if shape in ("octagon", "octagonal"):
        return _octagon_cells(room["x"], room["y"], room["w"], room["h"], room.get("corner"))
    if shape in ("poly", "polygon"):
        return _poly_cells(room["points"])
    return _rect_cells(room["x"], room["y"], room["w"], room["h"])


def _room_center(room):
    return (room["x"] + room["w"] / 2.0, room["y"] + room["h"] / 2.0)


# --- corridors ---------------------------------------------------------------

def _l_corridor_cells(c0, c1, width):
    width = max(1, int(width))
    half = width // 2
    x0, y0 = int(c0[0]), int(c0[1])
    x1, y1 = int(c1[0]), int(c1[1])
    cells = set()
    for cx in range(min(x0, x1), max(x0, x1) + 1):       # horizontal leg at y0
        for d in range(-half, width - half):
            cells.add((cx, y0 + d))
    for cy in range(min(y0, y1), max(y0, y1) + 1):       # vertical leg at x1
        for d in range(-half, width - half):
            cells.add((x1 + d, cy))
    return cells


def _corridor_cells(cor, room_by_id):
    if "from" in cor and "to" in cor:
        a = room_by_id.get(cor["from"])
        b = room_by_id.get(cor["to"])
        if not a or not b:
            raise ValueError(
                f"corridor references unknown room id(s): {cor.get('from')}, {cor.get('to')}")
        return _l_corridor_cells(_room_center(a), _room_center(b), cor.get("width", 2))
    if "rect" in cor:
        rx, ry, rw, rh = cor["rect"]
    else:
        rx, ry, rw, rh = cor["x"], cor["y"], cor["w"], cor["h"]
    return _rect_cells(rx, ry, rw, rh)


# --- occupancy + regions -----------------------------------------------------

def build_occupancy(spec):
    """Return (floor_set, room_by_id, region_of). region_of maps cell -> region id
    (a room id, or a corridor id). Room cells win over corridor cells on overlap."""
    rooms = spec.get("rooms", [])
    room_by_id = {}
    floor = set()
    region_of = {}

    for i, room in enumerate(rooms):
        room.setdefault("id", f"room{i}")
        room["_cells"] = room_cells(room)
        room_by_id[room["id"]] = room

    # Square off each room's wall where a corridor docks, so the corridor meets a
    # flat face exactly its own width (clean, aligned doorways on any shape).
    corridors = spec.get("corridors", [])
    for cor in corridors:
        if "from" in cor and "to" in cor:
            _flatten_corridor_docks(cor, room_by_id)

    for room in room_by_id.values():
        for c in room["_cells"]:
            floor.add(c)
            region_of[c] = room["id"]

    for i, cor in enumerate(corridors):
        cid = cor.get("id", f"corr{i}")
        for c in _corridor_cells(cor, room_by_id):
            floor.add(c)
            region_of.setdefault(c, cid)  # don't override a room's cell

    # Optional maze: winding corridors with branches and dead ends, carved into
    # the region around rooms/corridors (deterministic from `seed`).
    mz = spec.get("maze")
    if mz:
        seed = int(mz.get("seed", spec.get("seed", 1)))
        for c in _carve_maze(mz, spec, set(floor), seed):
            if c not in region_of:
                floor.add(c)
                region_of[c] = "maze"

    # Guarantee every area is reachable (tunnel between disconnected components).
    if mz or spec.get("ensureConnected"):
        _ensure_connected(floor, region_of)

    return floor, room_by_id, region_of


# --- maze generation ---------------------------------------------------------

def _carve_maze(mz, spec, blocked, seed):
    """Recursive-backtracker maze of `cell`-wide passages, routed around blocked
    (room/corridor) cells. Returns the set of carved floor cells."""
    rng = random.Random(seed)
    rx, ry = int(mz.get("x", 0)), int(mz.get("y", 0))
    rw = int(mz.get("w", spec.get("size", {}).get("w", 20)))
    rh = int(mz.get("h", spec.get("size", {}).get("h", 20)))
    pw = max(1, int(mz.get("cell", 2)))     # passage width (cells)
    wt = max(1, int(mz.get("wall", 1)))     # wall thickness between passages
    pitch = pw + wt
    nx = max(1, (rw + wt) // pitch)
    ny = max(1, (rh + wt) // pitch)

    def node_cells(i, j):
        X, Y = rx + i * pitch, ry + j * pitch
        return [(X + a, Y + b) for a in range(pw) for b in range(pw)]

    def blocked_node(i, j):
        return any(c in blocked for c in node_cells(i, j))

    def gap_cells(i, j, ni, nj):
        X, Y = rx + i * pitch, ry + j * pitch
        if ni > i:
            return [(X + pw + k, Y + b) for k in range(wt) for b in range(pw)]
        if ni < i:
            return [(X - wt + k, Y + b) for k in range(wt) for b in range(pw)]
        if nj > j:
            return [(X + a, Y + pw + k) for k in range(wt) for a in range(pw)]
        return [(X + a, Y - wt + k) for k in range(wt) for a in range(pw)]

    start = None
    for j in range(ny):
        for i in range(nx):
            if not blocked_node(i, j):
                start = (i, j)
                break
        if start:
            break
    if not start:
        return set()

    visited = {start}
    stack = [start]
    cells = set(node_cells(*start))
    while stack:
        i, j = stack[-1]
        nbrs = []
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and (ni, nj) not in visited and not blocked_node(ni, nj):
                nbrs.append((ni, nj))
        if nbrs:
            ni, nj = rng.choice(nbrs)
            cells.update(node_cells(ni, nj))
            cells.update(gap_cells(i, j, ni, nj))
            visited.add((ni, nj))
            stack.append((ni, nj))
        else:
            stack.pop()

    loops = float(mz.get("loops", 0.0))   # 0 = perfect maze (max dead ends)
    if loops > 0:
        for i in range(nx):
            for j in range(ny):
                if (i, j) not in visited:
                    continue
                for di, dj in ((1, 0), (0, 1)):
                    ni, nj = i + di, j + dj
                    if (ni, nj) in visited and rng.random() < loops:
                        cells.update(gap_cells(i, j, ni, nj))

    return {c for c in cells if rx <= c[0] < rx + rw and ry <= c[1] < ry + rh and c not in blocked}


def _components(floor):
    remaining = set(floor)
    comps = []
    while remaining:
        seedc = next(iter(remaining))
        remaining.discard(seedc)
        comp = {seedc}
        stack = [seedc]
        while stack:
            cx, cy = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cx + dx, cy + dy)
                if n in remaining:
                    remaining.discard(n)
                    comp.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def _l_path(a, b):
    (x0, y0), (x1, y1) = a, b
    cells = set()
    for x in range(min(x0, x1), max(x0, x1) + 1):
        cells.add((x, y0))
    for y in range(min(y0, y1), max(y0, y1) + 1):
        cells.add((x1, y))
    return cells


def _ensure_connected(floor, region_of):
    """Tunnel thin passages between disconnected floor components so the whole
    map is reachable (no-op if already connected)."""
    comps = _components(floor)
    if len(comps) <= 1:
        return
    comps.sort(key=len, reverse=True)
    main = comps[0]
    for comp in comps[1:]:
        best, bd = None, None
        for a in comp:
            for b in main:
                d = abs(a[0] - b[0]) + abs(a[1] - b[1])
                if bd is None or d < bd:
                    bd, best = d, (a, b)
        for c in _l_path(*best):
            floor.add(c)
            region_of.setdefault(c, "tunnel")
        main |= comp


def _flatten_dock(cells, cross, side):
    """Extend `cells` so the room presents a flat `side` face across the lines in
    `cross` (row indices for e/w docks, column indices for n/s docks)."""
    if side in ("e", "w"):
        xs = [cx for (cx, cy) in cells if cy in cross]
        if not xs:
            return
        face = max(xs) if side == "e" else min(xs)
        for cy in cross:
            row = [cx for (cx, c2) in cells if c2 == cy]
            if side == "e":
                start = (max(row) + 1) if row else face
                for cx in range(start, face + 1):
                    cells.add((cx, cy))
            else:
                end = (min(row) - 1) if row else face
                for cx in range(face, end + 1):
                    cells.add((cx, cy))
    else:
        ys = [cy for (cx, cy) in cells if cx in cross]
        if not ys:
            return
        face = max(ys) if side == "s" else min(ys)
        for cx in cross:
            col = [cy for (c2, cy) in cells if c2 == cx]
            if side == "s":
                start = (max(col) + 1) if col else face
                for cy in range(start, face + 1):
                    cells.add((cx, cy))
            else:
                end = (min(col) - 1) if col else face
                for cy in range(face, end + 1):
                    cells.add((cx, cy))


def _flatten_corridor_docks(cor, room_by_id):
    a = room_by_id.get(cor["from"])
    b = room_by_id.get(cor["to"])
    if not a or not b:
        return  # _corridor_cells will raise the clear error
    x0, y0 = int(a["x"] + a["w"] / 2.0), int(a["y"] + a["h"] / 2.0)
    x1, y1 = int(b["x"] + b["w"] / 2.0), int(b["y"] + b["h"] / 2.0)
    w = max(1, int(cor.get("width", 2)))
    half = w // 2
    span = range(-half, w - half)
    rows = {y0 + d for d in span}        # horizontal leg occupies these rows (at y0)
    cols = {x1 + d for d in span}        # vertical leg occupies these cols (at x1)

    # `a` is reached by the horizontal leg (unless the route is purely vertical).
    if x1 != x0:
        _flatten_dock(a["_cells"], rows, "e" if x1 > x0 else "w")
    else:
        _flatten_dock(a["_cells"], {x0 + d for d in span}, "s" if y1 > y0 else "n")

    # `b` is reached by the vertical leg (unless the route is purely horizontal).
    if y1 != y0:
        _flatten_dock(b["_cells"], cols, "n" if y0 < y1 else "s")
    else:
        _flatten_dock(b["_cells"], rows, "w" if x0 < x1 else "e")


# --- wall edges --------------------------------------------------------------

_SIDE_EDGE = {
    "n": lambda cx, cy: ("H", cx, cy),
    "s": lambda cx, cy: ("H", cx, cy + 1),
    "w": lambda cx, cy: ("V", cx, cy),
    "e": lambda cx, cy: ("V", cx + 1, cy),
}
_SIDE_NEIGHBOR = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}


def derive_wall_edges(floor):
    walls = set()
    for (cx, cy) in floor:
        for side, (dx, dy) in _SIDE_NEIGHBOR.items():
            if (cx + dx, cy + dy) not in floor:
                walls.add(_SIDE_EDGE[side](cx, cy))
    return walls


def door_edge(door):
    side = door.get("side")
    if side in _SIDE_EDGE:
        return _SIDE_EDGE[side](door["x"], door["y"])
    orient = door.get("orient", "h")
    return ("H", door["x"], door["y"]) if orient == "h" else ("V", door["x"], door["y"])


def edge_endpoints(edge):
    kind, a, b = edge
    if kind == "H":
        return (a, b), (a + 1, b)
    return (a, b), (a, b + 1)


def _edge_mid(edge):
    (x1, y1), (x2, y2) = edge_endpoints(edge)
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _seg_len(seg):
    (x1, y1), (x2, y2) = seg
    return math.hypot(x2 - x1, y2 - y1)


def _merge_unit_edges(edges):
    """Merge colinear contiguous unit edges into maximal straight runs.
    Returns a list of (segment, [unit_edges_in_run])."""
    runs = []
    by_y, by_x = defaultdict(list), defaultdict(list)
    for kind, a, b in edges:
        if kind == "H":
            by_y[b].append(a)
        else:
            by_x[a].append(b)

    for y, xs in sorted(by_y.items()):
        xs.sort()
        start = prev = xs[0]
        group = [("H", xs[0], y)]
        for x in xs[1:]:
            if x == prev + 1:
                prev = x
                group.append(("H", x, y))
            else:
                runs.append((((start, y), (prev + 1, y)), group))
                start = prev = x
                group = [("H", x, y)]
        runs.append((((start, y), (prev + 1, y)), group))

    for x, ys in sorted(by_x.items()):
        ys.sort()
        start = prev = ys[0]
        group = [("V", x, ys[0])]
        for yv in ys[1:]:
            if yv == prev + 1:
                prev = yv
                group.append(("V", x, yv))
            else:
                runs.append((((x, start), (x, prev + 1)), group))
                start = prev = yv
                group = [("V", x, yv)]
        runs.append((((x, start), (x, prev + 1)), group))

    return runs


def merge_edges(walls):
    # sorted for deterministic output order (edge tuples contain strings, whose
    # set-iteration order varies per process under hash randomization)
    return sorted(seg for seg, _ in _merge_unit_edges(walls))


# --- entrances (region interfaces) -------------------------------------------

def detect_entrances(floor, region_of):
    """Find openings between regions. Returns a list of entrances:
    {regions: frozenset(r1, r2), segment: ((x1,y1),(x2,y2)), edges: [unit_edges]}."""
    pair_edges = defaultdict(set)
    for (cx, cy) in floor:
        r1 = region_of[(cx, cy)]
        if (cx + 1, cy) in floor:
            r2 = region_of[(cx + 1, cy)]
            if r2 != r1:
                pair_edges[frozenset((r1, r2))].add(("V", cx + 1, cy))
        if (cx, cy + 1) in floor:
            r2 = region_of[(cx, cy + 1)]
            if r2 != r1:
                pair_edges[frozenset((r1, r2))].add(("H", cx, cy + 1))

    entrances = []
    for pair, edges in pair_edges.items():
        for seg, group in _merge_unit_edges(edges):
            entrances.append({"regions": pair, "segment": seg, "edges": group})
    # deterministic order (region ids are strings -> hash-randomized set order)
    entrances.sort(key=lambda e: (tuple(sorted(e["regions"])), e["segment"]))
    return entrances


def _region_graph(entrances):
    g = defaultdict(set)
    for e in entrances:
        r = list(e["regions"])
        if len(r) == 2:
            g[r[0]].add(r[1])
            g[r[1]].add(r[0])
    return g


def _first_hop(graph, a, b):
    """Neighbor of `a` on a shortest region-path to `b` (or None)."""
    if a == b or a not in graph:
        return None
    prev = {a: None}
    q = deque([a])
    while q:
        u = q.popleft()
        for v in graph[u]:
            if v not in prev:
                prev[v] = u
                if v == b:
                    cur = v
                    while prev[cur] != a:
                        cur = prev[cur]
                    return cur
                q.append(v)
    return None


def _nearest_edge(edge, pool, max_dist):
    m = _edge_mid(edge)
    best, bd = None, max_dist + 1e-6
    for e in pool:
        em = _edge_mid(e)
        d = math.hypot(em[0] - m[0], em[1] - m[1])
        if d < bd:
            bd, best = d, e
    return best


# --- door placement ----------------------------------------------------------

def _place_door(portals, wall_edges, seg, edges, door):
    for e in edges:
        wall_edges.discard(e)  # carve any coincident bulkhead (breach doors)
    (p0, p1) = seg
    portals.append({
        "p0": p0, "p1": p1,
        "type": door.get("type", "door"),
        "state": door.get("state", "closed"),
    })


def _resolve_connection(door, entrances, graph, warnings):
    """Return the list of entrances a {from,to} door should span."""
    a, b = door["from"], door["to"]
    pair_ab = frozenset((a, b))
    if any(e["regions"] == pair_ab for e in entrances):
        neighbor = b
    else:
        neighbor = _first_hop(graph, a, b)
    if neighbor is None:
        warnings.append(f"door from '{a}' to '{b}': no connecting opening found.")
        return []
    pair = frozenset((a, neighbor))
    cands = [e for e in entrances if e["regions"] == pair]
    if not cands:
        warnings.append(f"door from '{a}' to '{b}': no entrance on '{a}'.")
        return []
    if door.get("all"):
        return cands
    return [max(cands, key=lambda e: _seg_len(e["segment"]))]


def derive(spec):
    floor, room_by_id, region_of = build_occupancy(spec)
    if not floor:
        raise ValueError("map has no floor cells — define at least one room")

    wall_edges = derive_wall_edges(floor)
    entrances = detect_entrances(floor, region_of)
    interface_edges = set()
    for e in entrances:
        interface_edges.update(e["edges"])
    graph = _region_graph(entrances)
    warnings = []
    portals = []

    doors = list(spec.get("doors", []))

    # autoDoors: place a door across every room<->corridor opening.
    auto = spec.get("autoDoors")
    if auto:
        atype = auto if isinstance(auto, str) else "door"
        for e in entrances:
            room_sides = [r for r in e["regions"] if r in room_by_id]
            if len(room_sides) == 1:  # exactly one room + one corridor => a doorway
                doors.append({"_entrance": e, "type": atype, "state": "closed"})

    for door in doors:
        if "_entrance" in door:
            e = door["_entrance"]
            _place_door(portals, wall_edges, e["segment"], e["edges"], door)
            continue

        if "from" in door and "to" in door:
            for e in _resolve_connection(door, entrances, graph, warnings):
                if door.get("perCell"):
                    for ue in e["edges"]:
                        _place_door(portals, wall_edges, edge_endpoints(ue), [ue], door)
                else:
                    _place_door(portals, wall_edges, e["segment"], e["edges"], door)
            continue

        # explicit {x, y, side}: validate against real walls/entrances, snap if close
        edge = door_edge(door)
        loc = f"({door.get('x')},{door.get('y')}) side {door.get('side', door.get('orient'))}"
        if edge in wall_edges or edge in interface_edges:
            chosen = edge
        else:
            snap = _nearest_edge(edge, interface_edges, 1.5) or _nearest_edge(edge, wall_edges, 1.5)
            if snap:
                chosen = snap
                warnings.append(f"door at {loc} snapped to nearest opening/wall.")
            else:
                chosen = edge
                warnings.append(
                    f"door at {loc} does not align to any wall or entrance - placed as-is.")
        _place_door(portals, wall_edges, edge_endpoints(chosen), [chosen], door)

    segments = merge_edges(wall_edges)
    return {
        "floor": floor,
        "rooms": room_by_id,
        "region_of": region_of,
        "entrances": entrances,
        "segments": segments,
        "portals": portals,
        "warnings": warnings,
    }
