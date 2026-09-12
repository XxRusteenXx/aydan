"""Geometry calculations adapted from Data Visualisation Code_v1.ipynb.
The original WWR, connectivity, and largest-footprint heuristics are preserved.
"""
import io
import math
import pandas as pd
import shapely.wkt
from shapely.geometry import Polygon, MultiPolygon, JOIN_STYLE
from shapely.ops import unary_union

df = None
_cache = {}
def get_max_width_and_angle(poly):
    """Longest edge of a polygon: returns (angle_deg, length)."""
    coords = list(poly.exterior.coords) if hasattr(poly, 'exterior') else list(poly.coords)
    max_length, angle = 0.0, 0.0
    for i in range(len(coords) - 1):
        (x1, y1), (x2, y2) = coords[i][:2], coords[i + 1][:2]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length > max_length:
            max_length = length
            angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360
    return angle, max_length

def closest_boundary_segment(poly, px, py):
    """Nearest polygon edge to a point: returns (a, b, projection) as (x, y) tuples."""
    coords = list(poly.exterior.coords)
    best_seg, best_dist = None, float('inf')

    for i in range(len(coords) - 1):
        ax_, ay_ = coords[i][:2]
        bx_, by_ = coords[i + 1][:2]
        abx, aby = bx_ - ax_, by_ - ay_
        ab_len2 = abx * abx + aby * aby
        if ab_len2 == 0:
            continue

        t = ((px - ax_) * abx + (py - ay_) * aby) / ab_len2
        t = max(0.0, min(1.0, t))
        projx, projy = ax_ + t * abx, ay_ + t * aby
        d = math.hypot(px - projx, py - projy)

        if d < best_dist:
            best_dist = d
            best_seg = ((ax_, ay_), (bx_, by_), (projx, projy))

    return best_seg

def outward_normal_from_segment(room_poly, wx, wy):
    """Unit normal of the room wall nearest to (wx, wy), pointing away from the room."""
    seg = closest_boundary_segment(room_poly, wx, wy)
    if seg is None:
        return None

    (ax_, ay_), (bx_, by_), (projx, projy) = seg
    tx, ty = bx_ - ax_, by_ - ay_
    norm = math.hypot(tx, ty)
    if norm == 0:
        return None
    tx, ty = tx / norm, ty / norm

    # Two perpendicular candidates
    n1 = (-ty, tx)
    cx, cy = room_poly.centroid.x, room_poly.centroid.y

    # Pick the one pointing away from the room centroid
    if n1[0] * (projx - cx) + n1[1] * (projy - cy) > 0:
        return n1
    return (-n1[0], -n1[1])

def contact_width(poly_a, poly_b, tol=0.08):
    """Approximate length of the wall shared by two rooms (0 if they do not touch)."""
    inter = poly_a.buffer(tol, join_style=JOIN_STYLE.mitre).intersection(
        poly_b.buffer(tol, join_style=JOIN_STYLE.mitre))
    if inter.is_empty:
        return 0.0
    return inter.area / (2 * tol)

def extract_master_footprint(room_polys, gap_distance=0.5):
    """
    Merges room polygons into a single continuous building footprint.

    Parameters:
    - room_polys: list of shapely Polygons (the rooms of one plan)
    - gap_distance: distance to buffer out; should be slightly larger
                    than half of the maximum gap between rooms.
    """
    valid = [p for p in room_polys if p is not None and p.is_valid]
    if not valid:
        return None

    # 1. Union all shapes together
    unioned_shape = unary_union(valid)

    # 2. Buffer outward (expand) - mitre keeps sharp architectural corners
    merged_poly = unioned_shape.buffer(gap_distance, join_style=JOIN_STYLE.mitre)

    # 3. Buffer inward (shrink) by slightly less, so floating point noise
    #    cannot tear the geometry apart
    final_footprint = merged_poly.buffer(-(gap_distance - 0.01), join_style=JOIN_STYLE.mitre)

    # 4. Fallback: if it still splits, keep the largest continuous area
    if isinstance(final_footprint, MultiPolygon):
        final_footprint = max(final_footprint.geoms, key=lambda geom: geom.area)

    return final_footprint

def _build_plan(plan_id, gap_distance=0.5):
    plan_data = df[df['plan_id'] == plan_id]
    if plan_data.empty:
        raise ValueError(f"plan_id {plan_id} not found in the CSV.")

    # --- A. ROOMS (entity_type == 'area') ---
    rooms = {}
    room_polys = []
    raw_uids, unique_uids = {}, []

    area_rows = plan_data[plan_data['entity_type_n'] == 'area'].dropna(subset=['geom'])

    for n, (_, row) in enumerate(area_rows.iterrows()):
        poly = shapely.wkt.loads(row['geom'])
        if poly.geom_type != 'Polygon' or not poly.is_valid:
            continue

        c_height = float(row['height']) if pd.notnull(row['height']) else 3.0
        if c_height <= 0 or math.isnan(c_height):
            c_height = 3.0

        subtype = str(row['entity_subtype']).strip().upper()
        room_type = str(row['roomtype']).strip() if pd.notnull(row['roomtype']) else subtype.title()
        is_balcony = (subtype == 'BALCONY') or (room_type.lower() == 'balcony')

        uid = str(row['unit_id']).strip() if pd.notnull(row['unit_id']) else ''
        raw_uids[n] = uid
        if uid and uid.lower() not in ['nan', 'none', 'null', '0', '0.0'] and uid not in unique_uids:
            unique_uids.append(uid)

        rooms[n] = {
            'geometry': poly,
            'room_type': room_type,
            'entity_subtype': subtype,
            'is_balcony': is_balcony,
            'ceiling_height': c_height,
            'unit_usage': 1 if str(row['unit_usage']).strip().upper() == 'RESIDENTIAL' else 0,
            'unit_id': uid,
        }
        room_polys.append(poly)

    if not rooms:
        raise ValueError(f"plan_id {plan_id} has no valid room polygons.")

    # Public / corridor / stairs = 0, first apartment = 1, second = 2, ...
    uid_to_int = {uid: i + 1 for i, uid in enumerate(unique_uids)}
    for n in rooms:
        rooms[n]['apartment_id'] = uid_to_int.get(raw_uids[n], 0)

    # --- B. WINDOWS & DOORS (entity_type == 'opening') ---
    unique_windows, seen_windows = [], set()
    win_df = plan_data[plan_data['entity_subtype_n'].str.contains('WINDOW', na=False)]
    for _, w_row in win_df.iterrows():
        if pd.isnull(w_row['geom']):
            continue
        win_poly = shapely.wkt.loads(w_row['geom'])
        w_sig = (round(win_poly.area, 2), round(win_poly.centroid.x, 2), round(win_poly.centroid.y, 2))
        if w_sig in seen_windows:
            continue
        seen_windows.add(w_sig)
        h = float(w_row['height']) if pd.notnull(w_row['height']) else 1.5
        sill = float(w_row['elevation']) if pd.notnull(w_row['elevation']) else 0.9
        unique_windows.append({'poly': win_poly, 'height': h, 'sill': sill})

    doors = []
    door_df = plan_data[plan_data['entity_subtype_n'].str.contains('DOOR', na=False)]
    for _, d_row in door_df.iterrows():
        if pd.isnull(d_row['geom']):
            continue
        doors.append({
            'poly': shapely.wkt.loads(d_row['geom']),
            'is_entrance': 'ENTRANCE' in str(d_row['entity_subtype']).upper(),
        })

    # --- C. WINDOW FEATURES PER ROOM (area, angle, relative vector, WWR) ---
    for n, data in rooms.items():
        room_poly = data['geometry']
        r_cx, r_cy = room_poly.centroid.x, room_poly.centroid.y
        minx, miny, maxx, maxy = room_poly.bounds
        r_width = max((maxx - minx), 0.01)
        r_height = max((maxy - miny), 0.01)

        connected = []
        for w in unique_windows:
            if room_poly.distance(w['poly']) >= 0.1:
                continue
            angle, width = get_max_width_and_angle(w['poly'])
            w_cx, w_cy = w['poly'].centroid.x, w['poly'].centroid.y
            rel_x = (w_cx - r_cx) / r_width
            rel_y = (w_cy - r_cy) / r_height
            vec_angle = math.atan2(rel_y, rel_x)
            connected.append({
                'area': width * w['height'],
                'angle': angle,
                'height': w['height'],
                'sill': w['sill'],
                'vec_dist': math.hypot(rel_x, rel_y),
                'vec_sin': math.sin(vec_angle),
                'vec_cos': math.cos(vec_angle),
            })

        if connected:
            total_win_area = sum(w['area'] for w in connected)
            largest = max(connected, key=lambda x: x['area'])
            data['window_area'] = total_win_area
            data['window_count'] = len(connected)
            data['window_angle'] = largest['angle']
            data['window_height'] = largest['height']
            data['window_sill'] = largest['sill']
            data['window_vec_dist'] = largest['vec_dist']
            data['window_vec_sin'] = largest['vec_sin']
            data['window_vec_cos'] = largest['vec_cos']

            exterior_wall_area = max(r_width, r_height) * data['ceiling_height']
            wwr = total_win_area / exterior_wall_area if exterior_wall_area > 0 else 0.0
            data['wwr'] = min(wwr, 1.0)
        else:
            data['window_area'] = 0.0
            data['window_count'] = 0
            data['window_angle'] = 0.0
            data['window_height'] = 0.0
            data['window_sill'] = 0.0
            data['window_vec_dist'] = 0.0
            data['window_vec_sin'] = 0.0
            data['window_vec_cos'] = 0.0
            data['wwr'] = 0.0

        # Balconies are open air: flagged with -1 instead of a ratio
        if data['is_balcony']:
            data['wwr'] = -1.0

        data['room_area'] = room_poly.area

    # --- D. EDGES: rooms joined by a door, or by a wide shared wall (passage) ---
    edges = {}
    node_ids = list(rooms.keys())

    for d in doors:
        touching = [n for n in node_ids if rooms[n]['geometry'].distance(d['poly']) < 0.1]
        if len(touching) < 2:
            continue
        _, d_width = get_max_width_and_angle(d['poly'])
        for i in range(len(touching)):
            for j in range(i + 1, len(touching)):
                u, v = touching[i], touching[j]
                if d['is_entrance']:
                    dtype = 3
                elif rooms[u]['is_balcony'] or rooms[v]['is_balcony']:
                    dtype = 2
                else:
                    dtype = 1
                key = (min(u, v), max(u, v))
                prev = edges.get(key)
                if prev is None or d_width > prev['door_width']:
                    edges[key] = {'door_width': float(max(d_width, 0.6)), 'door_type': int(dtype)}

    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            u, v = node_ids[i], node_ids[j]
            if (u, v) in edges:
                continue
            poly_u, poly_v = rooms[u]['geometry'], rooms[v]['geometry']
            if poly_u.distance(poly_v) > 0.15:
                continue
            width = contact_width(poly_u, poly_v)
            if width >= 0.9:  # wide opening with no door leaf = passage
                edges[(u, v)] = {'door_width': float(max(1.2, width)), 'door_type': 0}

    # --- E. GRAPH-LEVEL BUILDING FEATURES ---
    footprint = extract_master_footprint(room_polys, gap_distance=gap_distance)
    compactness = 0.0
    if footprint is not None and footprint.length > 0:
        compactness = (4 * math.pi * footprint.area) / (footprint.length ** 2)

    meta = {
        'plan_id': plan_id,
        'master_footprint': footprint,
        'building_area': round(footprint.area, 3) if footprint is not None else 0.0,
        'building_perimeter': round(footprint.length, 3) if footprint is not None else 0.0,
        'building_compactness': round(compactness, 3),
        'n_apartments': len(unique_uids),
        'n_windows': len(unique_windows),
        'n_doors': len(doors),
    }

    return {'rooms': rooms, 'edges': edges, 'windows': unique_windows, 'doors': doors, 'meta': meta}

def build_plan(plan_id):
    plan_id = str(plan_id)
    if plan_id not in _cache:
        _cache[plan_id] = _build_plan(plan_id)
    return _cache[plan_id]

def load_csv(text):
    global df, _cache
    df, _cache = None, {}
    try:
        candidate = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=True)
    except Exception as exc:
        raise ValueError('Could not read CSV. Upload a comma-separated UTF-8 file.') from exc
    candidate.columns = candidate.columns.str.strip()
    required = {'building_id', 'floor_id', 'plan_id', 'unit_id', 'unit_usage',
                'entity_type', 'entity_subtype', 'geom', 'elevation', 'height', 'roomtype'}
    missing = required - set(candidate.columns)
    if missing:
        raise ValueError('Missing CSV columns: ' + ', '.join(sorted(missing)))
    if candidate.empty:
        raise ValueError('The CSV contains no rows.')
    if len(candidate) > 20000:
        raise ValueError('Please upload one floor with at most 20,000 rows.')
    for col in ['building_id', 'floor_id', 'plan_id', 'unit_id']:
        candidate[col] = candidate[col].str.strip().replace('', pd.NA)
    for col in ['building_id', 'floor_id']:
        if candidate[col].isna().any() or candidate[col].nunique() != 1:
            raise ValueError('Upload exactly one floor from one building, with complete ' + col + ' values.')
    if candidate['plan_id'].isna().any():
        raise ValueError('Every row must have a plan_id.')
    for col in ['height', 'elevation']:
        candidate[col] = pd.to_numeric(candidate[col], errors='coerce')
        if candidate[col].isin([float('inf'), float('-inf')]).any():
            raise ValueError(col + ' must contain finite numbers.')
    candidate['entity_type_n'] = candidate['entity_type'].fillna('').str.strip().str.lower()
    candidate['entity_subtype_n'] = candidate['entity_subtype'].fillna('').str.strip().str.upper()
    geometry_rows = candidate[(candidate['entity_type_n'] == 'area') |
        candidate['entity_subtype_n'].str.contains('WINDOW|DOOR', regex=True)]
    if len(geometry_rows) > 5000:
        raise ValueError('This floor is too large for the browser viewer (over 5,000 room/opening records).')
    for index, row in geometry_rows.iterrows():
        try:
            poly = shapely.wkt.loads(row['geom'])
            if poly.geom_type != 'Polygon' or poly.is_empty or not poly.is_valid:
                raise ValueError()
        except Exception as exc:
            raise ValueError(f'CSV row {index + 2}: expected a nonempty, valid Polygon in geom.') from exc
    rooms = candidate[candidate['entity_type_n'] == 'area']
    if rooms.empty:
        raise ValueError('No rooms found: entity_type must contain area rows.')
    units = rooms['unit_id'].dropna()
    units = units[~units.str.lower().isin(['nan', 'none', 'null', '0', '0.0'])]
    df = candidate
    return dict(building_id=str(df['building_id'].iloc[0]), floor_id=str(df['floor_id'].iloc[0]),
                plans=sorted(rooms['plan_id'].unique().tolist()), rooms=len(rooms), units=units.nunique(),
                apartments=apartment_options(), window_heights=window_height_options())

def window_height_options():
    values = df.loc[df.entity_subtype_n.str.contains('WINDOW'), 'height']
    return [dict(value=None if pd.isna(value) else float(value), count=int(count))
            for value, count in values.value_counts(dropna=False).items()]

def change_window_height(original, height):
    plans()  # Require a loaded floor before making changes.
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or height <= 0:
        raise ValueError('Window height must be a finite number greater than zero.')
    windows = df.entity_subtype_n.str.contains('WINDOW')
    matching = df.height.isna() if original is None else df.height.eq(original)
    mask = windows & matching
    if not mask.any():
        raise ValueError('No windows have the selected height. Reload the height options.')
    df.loc[mask, 'height'] = float(height)
    _cache.clear()
    return dict(window_heights=window_height_options())

def apartment_options():
    areas = df[df['entity_type_n'] == 'area']
    return {pid: sorted({uid for uid in rows['unit_id'].dropna()
                        if uid.lower() not in ['nan', 'none', 'null', '0', '0.0']})
            for pid, rows in areas.groupby('plan_id')}

def muted_room(ax, room, apartment_id):
    """Draw unselected rooms as context; never change cached plan data."""
    if apartment_id is None or room['unit_id'] == apartment_id:
        return False
    x, y = room['geometry'].exterior.xy
    ax.fill(x, y, color='lightgray', edgecolor='gray', alpha=0.6, linewidth=1)
    return True

def plans():
    if df is None:
        raise ValueError('Load a floor CSV first.')
    return sorted(df.loc[df['entity_type_n'] == 'area', 'plan_id'].unique().tolist())

def wwr_table():
    return pd.DataFrame([
        {'wwr': room['wwr'], 'room_type': room['room_type']}
        for pid in plans() for room in build_plan(pid)['rooms'].values() if room['wwr'] >= 0
    ], columns=['wwr', 'room_type'])
