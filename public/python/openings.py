import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment, muted_room

def visualize_openings(plan_id, apartment_id=None):
    plan = build_plan(plan_id)
    rooms, meta = plan['rooms'], plan['meta']

    fig, ax = plt.subplots(figsize=(12, 12))

    footprint = meta['master_footprint']
    if isinstance(footprint, Polygon):
        x, y = footprint.exterior.xy
        ax.plot(x, y, color='black', linewidth=3, zorder=1)

    for n, data in rooms.items():
        if muted_room(ax, data, apartment_id):
            continue
        room_poly = data['geometry']
        x, y = room_poly.exterior.xy
        color = 'wheat' if data['is_balcony'] else 'lightsteelblue'
        ax.fill(x, y, alpha=0.45, color=color, edgecolor='gray', linewidth=1, zorder=2)

        r_cx, r_cy = room_poly.centroid.x, room_poly.centroid.y
        ax.text(r_cx, r_cy, f"R{n}\n{data['room_type']}", fontsize=8, ha='center',
                va='center', fontweight='bold', zorder=6)

    for w in plan['windows']:
        if apartment_id is not None and not any(room['unit_id'] == apartment_id and room['geometry'].distance(w['poly']) < 0.1 for room in rooms.values()):
            x, y = w['poly'].exterior.xy
            ax.fill(x, y, color='lightgray', alpha=0.6, zorder=5)
            continue
        x, y = w['poly'].exterior.xy
        ax.fill(x, y, color='dodgerblue', alpha=0.9, zorder=5)

    for d in plan['doors']:
        if apartment_id is not None and not any(room['unit_id'] == apartment_id and room['geometry'].distance(d['poly']) < 0.1 for room in rooms.values()):
            x, y = d['poly'].exterior.xy
            ax.fill(x, y, color='lightgray', alpha=0.6, zorder=5)
            continue
        x, y = d['poly'].exterior.xy
        ax.fill(x, y, color='crimson' if d['is_entrance'] else 'purple', alpha=0.9, zorder=5)

    ax.set_title(f"Windows & Doors from CSV geometry: Plan {plan_id}\n"
                 f"{meta['n_windows']} windows | {meta['n_doors']} doors",
                 fontsize=14, fontweight='bold', pad=15)

    custom_lines = [
        Line2D([0], [0], color='lightsteelblue', lw=6, alpha=0.6, label='Room'),
        Line2D([0], [0], color='wheat', lw=6, alpha=0.9, label='Balcony'),
        Line2D([0], [0], color='dodgerblue', lw=6, label='Window'),
        Line2D([0], [0], color='purple', lw=6, label='Door'),
        Line2D([0], [0], color='crimson', lw=6, label='Entrance Door'),
    ]
    ax.legend(handles=custom_lines, loc='upper right', bbox_to_anchor=(1.3, 1))

    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

def render(plan_id, attribute="wwr", apartment_id=None):
    return visualize_openings(plan_id, apartment_id=apartment_id)
