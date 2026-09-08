"""JSON in, JSON with base64 PNG out. Runs only in browser memory."""
import base64
import importlib
import io
import json
import matplotlib.pyplot as plt
import model

CHARTS = {'overview', 'attributes', 'apartments', 'orientation', 'openings',
          'room_types', 'ceiling_heights', 'window_heights', 'wwr_distribution', 'wwr_by_type'}
ATTRIBUTES = {'wwr', 'room_area', 'window_area', 'ceiling_height', 'window_count'}

def handle(payload):
    data = json.loads(payload)
    if data['type'] == 'upload':
        return json.dumps(model.load_csv(data['csv']))
    if data['type'] != 'render' or data.get('chart') not in CHARTS:
        raise ValueError('Unknown visualization request.')
    plans = model.plans()
    plan = str(data.get('plan') or plans[0])
    if plan not in plans:
        raise ValueError('This plan is not in the uploaded floor.')
    attribute = data.get('attribute', 'wwr')
    if attribute not in ATTRIBUTES:
        raise ValueError('Unknown room attribute.')
    plt.close('all')
    try:
        fig = importlib.import_module(data['chart']).render(plan, attribute)
        output = io.BytesIO()
        fig.savefig(output, format='png', dpi=110, bbox_inches='tight')
        return json.dumps({'png': base64.b64encode(output.getvalue()).decode('ascii')})
    finally:
        plt.close('all')
