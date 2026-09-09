import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment, muted_room

def visualize_window_orientation_outward(plan_id, apartment_id=None):
    """
    Draws the reconstructed window centre of every room and forces the orientation
    arrow to point outward, using the nearest room-boundary segment instead of the
    ambiguous sign of window_angle.
    """
    plan = build_plan(plan_id)
    rooms, meta = plan['rooms'], plan['meta']

    fig, ax = plt.subplots(figsize=(12, 12))

    # 1. Master footprint
    footprint = meta['master_footprint']
    if isinstance(footprint, Polygon):
        x, y = footprint.exterior.xy
        ax.plot(x, y, color='black', linewidth=4, zorder=1)
    elif isinstance(footprint, MultiPolygon):
        for geom in footprint.geoms:
            x, y = geom.exterior.xy
            ax.plot(x, y, color='black', linewidth=4, zorder=1)

    # 2. Rooms and outward arrows
    for n, data in rooms.items():
        if muted_room(ax, data, apartment_id):
            continue
        room_poly = data['geometry']

        x, y = room_poly.exterior.xy
        ax.fill(x, y, alpha=0.25, color='lightsteelblue', edgecolor='gray', linewidth=1)

        r_cx, r_cy = room_poly.centroid.x, room_poly.centroid.y
        ax.plot(r_cx, r_cy, 'ko', markersize=3, zorder=3)
        ax.text(r_cx, r_cy + 0.15, f"R{n}", fontsize=9, ha='center', va='bottom', fontweight='bold')

        if data['wwr'] == -1.0:
            ax.text(r_cx, r_cy - 0.15, "Balcony", fontsize=8, ha='center', va='top',
                    color='red', fontweight='bold')
            continue

        if data['window_area'] > 0.0:
            minx, miny, maxx, maxy = room_poly.bounds
            r_width = max((maxx - minx), 0.01)
            r_height = max((maxy - miny), 0.01)

            # Reconstruct the window centre from the encoded relative vector
            w_cx = r_cx + (data['window_vec_dist'] * data['window_vec_cos'] * r_width)
            w_cy = r_cy + (data['window_vec_dist'] * data['window_vec_sin'] * r_height)

            ax.plot(w_cx, w_cy, 's', color='crimson', markersize=7,
                    markeredgecolor='black', zorder=5)

            normal = outward_normal_from_segment(room_poly, w_cx, w_cy)
            if normal is not None:
                arrow_len = max(r_width, r_height, 0.01) * 0.6
                end_x = w_cx + arrow_len * normal[0]
                end_y = w_cy + arrow_len * normal[1]

                ax.plot([w_cx, end_x], [w_cy, end_y], color='darkgreen', linewidth=2.5, zorder=4)
                ax.plot(end_x, end_y, '^', color='limegreen', markersize=8,
                        markeredgecolor='black', zorder=6)

    ax.set_title(f"Window Centres & Outward Orientation: Plan {plan_id}",
                 fontsize=14, fontweight='bold', pad=15)

    custom_lines = [
        Line2D([0], [0], color='lightsteelblue', lw=6, alpha=0.5, label='Room Geometry'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='k', markersize=6, label='Room Centroid'),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='crimson',
               markeredgecolor='k', markersize=7, label='Window Centre'),
        Line2D([0], [0], color='darkgreen', lw=2.5, label='Outward Window Direction'),
        Line2D([0], [0], marker='^', color='w', markerfacecolor='limegreen',
               markeredgecolor='k', markersize=8, label='Arrow Tip'),
    ]
    ax.legend(handles=custom_lines, loc='upper right', bbox_to_anchor=(1.35, 1))

    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

def render(plan_id, attribute="wwr", apartment_id=None):
    return visualize_window_orientation_outward(plan_id, apartment_id=apartment_id)
