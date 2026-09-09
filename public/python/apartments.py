import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment, muted_room

def visualize_apartment_ids(plan_id, apartment_id=None):
    """
    Colour-codes rooms by apartment_id (derived from unit_id in the CSV).
    Public spaces (0) are grey; edges between different apartments are highlighted.
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

    # 2. Colours per apartment
    unique_apt_ids = sorted({rooms[n]['apartment_id'] for n in rooms})
    num_apts = len([i for i in unique_apt_ids if i != 0])
    cmap = plt.get_cmap('tab10', max(1, num_apts))

    def get_apt_color(apt_id):
        if apt_id == 0:
            return 'lightgray'  # public / corridor / stairs
        idx = unique_apt_ids.index(apt_id) - (1 if 0 in unique_apt_ids else 0)
        return cmap(idx)

    # 3. Rooms
    legend_elements = set()
    for n, data in rooms.items():
        if muted_room(ax, data, apartment_id):
            continue
        room_poly = data['geometry']
        apt_id = data['apartment_id']

        label = "Public Area (0)" if apt_id == 0 else f"Apartment {apt_id}"
        _label = label if label not in legend_elements else ""

        x, y = room_poly.exterior.xy
        ax.fill(x, y, alpha=0.7, color=get_apt_color(apt_id), edgecolor='dimgray',
                linewidth=1.5, label=_label)
        legend_elements.add(label)

        r_cx, r_cy = room_poly.centroid.x, room_poly.centroid.y
        ax.plot(r_cx, r_cy, 'ko', markersize=3)
        ax.text(r_cx, r_cy + 0.15, f"R{n}", fontsize=10, ha='center', va='bottom', fontweight='bold')
        ax.text(r_cx, r_cy - 0.15, f"Apt {apt_id}", fontsize=8, ha='center', va='top', fontweight='bold')

    # 4. Demising walls (edges crossing apartments)
    for (u, v) in edges:
        if apartment_id is not None and any(rooms[n]['unit_id'] != apartment_id for n in (u, v)):
            continue
        ux, uy = rooms[u]['geometry'].centroid.x, rooms[u]['geometry'].centroid.y
        vx, vy = rooms[v]['geometry'].centroid.x, rooms[v]['geometry'].centroid.y

        if rooms[u]['apartment_id'] != rooms[v]['apartment_id']:
            color, ls, width, label_edge = 'red', '--', 3.0, 'Demising Wall / Entry'
        else:
            color, ls, width, label_edge = 'dimgray', '-', 1.0, 'Internal Connection'

        _label_edge = label_edge if label_edge not in legend_elements else ""
        ax.plot([ux, vx], [uy, vy], color=color, linestyle=ls, linewidth=width,
                alpha=0.8, label=_label_edge)
        legend_elements.add(label_edge)

    title = f"Apartment Segmentation: Plan {plan_id}\n"
    title += f"Total Units: {num_apts} | Public Spaces: {'Yes' if 0 in unique_apt_ids else 'No'}"
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)

    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1))
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    return fig

def render(plan_id, attribute="wwr", apartment_id=None):
    return visualize_apartment_ids(plan_id, apartment_id=apartment_id)
