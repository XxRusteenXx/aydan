"""One-time, reproducible extraction of the v1 geometry and plot functions."""
import ast
import json
from pathlib import Path

root = Path(__file__).resolve().parent
notebook = json.loads((root.parent / 'Data Visualisation Code_v1.ipynb').read_text(encoding='utf-8'))
cells = [''.join(cell['source']) for cell in notebook['cells']]
out = root / 'public' / 'python'
out.mkdir(parents=True, exist_ok=True)

def functions(index):
    return '\n\n'.join(ast.get_source_segment(cells[index], node) for node in ast.parse(cells[index]).body if isinstance(node, ast.FunctionDef))

model = '''"""Geometry calculations adapted from Data Visualisation Code_v1.ipynb.
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
'''
model += '\n\n'.join(functions(i) for i in [4, 5, 6])
model = model.replace('def build_plan(plan_id, gap_distance=0.5):', 'def _build_plan(plan_id, gap_distance=0.5):')
model += '''

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
                plans=sorted(rooms['plan_id'].unique().tolist()), rooms=len(rooms), units=units.nunique())

def plans():
    if df is None:
        raise ValueError('Load a floor CSV first.')
    return sorted(df.loc[df['entity_type_n'] == 'area', 'plan_id'].unique().tolist())

def wwr_table():
    return pd.DataFrame([
        {'wwr': room['wwr'], 'room_type': room['room_type']}
        for pid in plans() for room in build_plan(pid)['rooms'].values() if room['wwr'] >= 0
    ], columns=['wwr', 'room_type'])
'''
(out / 'model.py').write_text(model, encoding='utf-8')
header = '''import math
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from shapely.geometry import Polygon, MultiPolygon
from model import build_plan, outward_normal_from_segment
'''
for name, index, function in [
    ('attributes', 11, 'visualize_plan'), ('apartments', 14, 'visualize_apartment_ids'),
    ('orientation', 16, 'visualize_window_orientation_outward'), ('openings', 18, 'visualize_openings')]:
    source = functions(index).replace('    plt.show()', '    return fig')
    call = f'{function}(plan_id' + (", color_by=attribute" if name == 'attributes' else '') + ')'
    (out / f'{name}.py').write_text(header + '\n' + source + '\n\ndef render(plan_id, attribute="wwr"):\n    return ' + call + '\n', encoding='utf-8')

# Keep overview drawing logic, but adapt its grid to a one-floor input.
source = cells[9]
source = source[source.index('fig, axes ='):source.rindex('plt.show()')]
source = source.replace('fig, axes = plt.subplots(2, 2, figsize=(16, 14))\naxes = axes.flatten()',
    'count = len(selected_plans)\ncols = min(2, count)\nrows = (count + cols - 1) // cols\nfig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 7 * rows), squeeze=False)\naxes = axes.flatten()\nfor ax in axes[count:]:\n    ax.set_visible(False)')
(out / 'overview.py').write_text(header + '\nimport model\n\ndef render(plan_id=None, attribute="wwr"):\n    selected_plans = model.plans()[:4]\n' + '\n'.join('    ' + line for line in source.splitlines()) + '\n    return fig\n', encoding='utf-8')
print('Extracted shared model and five layout visualizations.')
