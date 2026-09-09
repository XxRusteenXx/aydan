import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment, muted_room

import model

def render(plan_id=None, attribute="wwr", apartment_id=None):
    selected_plans = model.plans()[:4]
    count = len(selected_plans)
    cols = min(2, count)
    rows = (count + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 7 * rows), squeeze=False)
    axes = axes.flatten()
    for ax in axes[count:]:
        ax.set_visible(False)
    
    for idx, plan_id in enumerate(selected_plans):
        ax = axes[idx]
        plan = build_plan(plan_id)
        rooms, edges, meta = plan['rooms'], plan['edges'], plan['meta']
    
        # Master footprint (thick green outline + light fill)
        footprint = meta['master_footprint']
        if footprint is not None and footprint.geom_type == 'Polygon':
            m_x, m_y = footprint.exterior.xy
            ax.plot(m_x, m_y, color='#27AE60', linewidth=3, zorder=1,
                    label='Master Footprint' if idx == 0 else "")
            ax.fill(m_x, m_y, alpha=0.1, color='#27AE60', zorder=0)
    
        # --- A. Rooms ---
        pos = {}
        first_node = next(iter(rooms))
        for n, data in rooms.items():
            if muted_room(ax, data, apartment_id):
                continue
            poly = data['geometry']
            x, y = poly.exterior.xy
            ax.fill(x, y, alpha=0.3, color='#4A90E2', edgecolor='#333333', linewidth=1.5, zorder=2)
    
            cx, cy = poly.centroid.x, poly.centroid.y
            pos[n] = (cx, cy)
    
            if data['window_area'] > 0:
                ax.plot(cx, cy, 'o', color='orange', markersize=8, zorder=5,
                        label='Has Window' if n == first_node else "")
            else:
                ax.plot(cx, cy, 'o', color='#333333', markersize=4, zorder=5)
    
        # --- B. Connections ---
        first_edge = next(iter(edges), None)
        for (u, v), attr in edges.items():
            if apartment_id is not None and any(rooms[n]['unit_id'] != apartment_id for n in (u, v)):
                continue
            x_values = [pos[u][0], pos[v][0]]
            y_values = [pos[u][1], pos[v][1]]
            if attr['door_type'] == 0:
                ax.plot(x_values, y_values, color='black', linestyle='-', linewidth=1, zorder=3)
            else:
                ax.plot(x_values, y_values, color='red', linestyle='--', linewidth=2, zorder=4,
                        label='Door' if (u, v) == first_edge else "")
    
        ax.set_title(f"Plan: {plan_id}\nRooms: {len(rooms)} | Edges: {len(edges)}", fontsize=12)
        ax.axis('equal')
        ax.axis('off')
    
        if idx == 0:
            handles, labels = ax.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            if by_label:
                ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=10)
    
    plt.tight_layout()
    return fig
