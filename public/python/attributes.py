import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment, muted_room

def visualize_plan(plan_id, color_by='wwr', apartment_id=None):
    """
    Plots one plan straight from the CSV, colouring rooms by a derived attribute.

    Parameters:
    - plan_id: int, the plan to draw
    - color_by: str, room attribute used for the colourmap ('wwr', 'ceiling_height',
                'window_area', 'room_area', 'apartment_id', ...)
    """
    plan = build_plan(plan_id)
    rooms, edges, meta = plan['rooms'], plan['edges'], plan['meta']

    fig, ax = plt.subplots(figsize=(12, 12))

    # 1. Master footprint
    footprint = meta['master_footprint']
    if isinstance(footprint, Polygon):
        x, y = footprint.exterior.xy
        ax.plot(x, y, color='black', linewidth=4, zorder=10, label='Master Footprint')
    elif isinstance(footprint, MultiPolygon):
        for i, geom in enumerate(footprint.geoms):
            x, y = geom.exterior.xy
            ax.plot(x, y, color='black', linewidth=4, zorder=10,
                    label='Master Footprint' if i == 0 else "")

    # 2. Colourmap bounds - negative values (e.g. balcony WWR = -1) render white
    node_values = [rooms[n].get(color_by, 0) for n in rooms]
    positive_values = [v for v in node_values if v >= 0]
    vmin = 0.0
    vmax = max(positive_values) if positive_values else 1.0
    if vmax == vmin:
        vmax = vmin + 1.0

    cmap = plt.get_cmap('YlOrRd' if color_by == 'wwr' else 'viridis').copy()
    cmap.set_under('white')
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    # 3. Rooms + reconstructed window vectors
    first_node = next(iter(rooms))
    for n, data in rooms.items():
        if muted_room(ax, data, apartment_id):
            continue
        room_poly = data['geometry']
        val = data.get(color_by, 0)

        x, y = room_poly.exterior.xy
        ax.fill(x, y, alpha=0.5, color=cmap(norm(val)), edgecolor='dimgray', linewidth=1)

        r_cx, r_cy = room_poly.centroid.x, room_poly.centroid.y
        ax.plot(r_cx, r_cy, 'ko', markersize=3)
        ax.text(r_cx, r_cy + 0.15, f"R{n}", fontsize=10, ha='center', va='bottom', fontweight='bold')
        ax.text(r_cx, r_cy - 0.15,
                f"{color_by}: {val:.2f}" if isinstance(val, float) else f"{color_by}: {val}",
                fontsize=8, ha='center', va='top')

        if data['window_area'] > 0:
            minx, miny, maxx, maxy = room_poly.bounds
            r_width = max((maxx - minx), 0.01)
            r_height = max((maxy - miny), 0.01)

            # Reverse the relative encoding used when the vector was built
            w_cx = r_cx + (data['window_vec_dist'] * data['window_vec_cos'] * r_width)
            w_cy = r_cy + (data['window_vec_dist'] * data['window_vec_sin'] * r_height)

            ax.plot([r_cx, w_cx], [r_cy, w_cy], color='dodgerblue', linestyle='--', linewidth=1.5)
            ax.plot(w_cx, w_cy, 's', color='dodgerblue', markersize=6,
                    label='Window Vector' if n == first_node else "")

    # 4. Doors / passages
    legend_elements = set()
    for (u, v), edata in edges.items():
        if apartment_id is not None and any(rooms[n]['unit_id'] != apartment_id for n in (u, v)):
            continue
        ux, uy = rooms[u]['geometry'].centroid.x, rooms[u]['geometry'].centroid.y
        vx, vy = rooms[v]['geometry'].centroid.x, rooms[v]['geometry'].centroid.y

        door_type = edata['door_type']
        if door_type == 0:
            color, ls, label = 'forestgreen', ':', 'Passage'
        elif door_type == 3:
            color, ls, label = 'crimson', '-', 'Entrance'
        else:
            color, ls, label = 'purple', '-', 'Internal Door'

        _label = label if label not in legend_elements else ""
        ax.plot([ux, vx], [uy, vy], color=color, linestyle=ls,
                linewidth=edata['door_width'] * 2.5, alpha=0.8, label=_label)
        legend_elements.add(label)

    # 5. Metadata in the title
    title = f"Plan: {plan_id}\n"
    title += f"Area: {meta['building_area']:.1f}m2 | "
    title += f"Perimeter: {meta['building_perimeter']:.1f}m | "
    title += f"Compactness: {meta['building_compactness']:.3f}"
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)

    ax.legend(loc='upper right', bbox_to_anchor=(1.25, 1))
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.035, pad=0.03, shrink=0.7)
    cbar.set_label(f"Room Attribute: {color_by}", rotation=270, labelpad=15)

    ax.set_aspect('equal')
    ax.axis('off')
    return fig

def render(plan_id, attribute="wwr", apartment_id=None):
    return visualize_plan(plan_id, color_by=attribute, apartment_id=apartment_id)
