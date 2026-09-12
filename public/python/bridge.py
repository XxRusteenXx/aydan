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
LAYOUTS = {'overview', 'attributes', 'apartments', 'orientation', 'openings'}

def handle(payload):
    data = json.loads(payload)
    if data['type'] == 'upload':
        return json.dumps(model.load_csv(data['csv']))
    if data['type'] == 'window_height':
        return json.dumps(model.change_window_height(data.get('original'), data.get('height')))
    if data['type'] != 'render' or data.get('chart') not in CHARTS:
        raise ValueError('Unknown visualization request.')
    plans = model.plans()
    plan = str(data.get('plan') or plans[0])
    if plan not in plans:
        raise ValueError('This plan is not in the uploaded floor.')
    attribute = data.get('attribute', 'wwr')
    if attribute not in ATTRIBUTES:
        raise ValueError('Unknown room attribute.')
    apartment = data.get('apartment') or None
    if apartment is not None and data['chart'] in LAYOUTS:
        options = model.apartment_options()
        allowed = {uid for ids in options.values() for uid in ids} if data['chart'] == 'overview' else options[plan]
        if apartment not in allowed:
            raise ValueError('This apartment is not in the selected plan/floor.')
    plt.close('all')
    try:
        module = importlib.import_module(data['chart'])
        fig = module.render(plan, attribute, apartment) if data['chart'] in LAYOUTS else module.render(plan, attribute)
        if apartment is not None and data['chart'] in LAYOUTS:
            fig.suptitle(f'Apartment {apartment} highlighted — other rooms shown in gray')
            # The plot modules lay out their plan titles before this heading exists.
            # Reserve a separate top band for it before exporting the image.
            fig.tight_layout(rect=(0, 0, 1, 0.92))
        output = io.BytesIO()
        fig.savefig(output, format='png', dpi=110, bbox_inches='tight')
        return json.dumps({'png': base64.b64encode(output.getvalue()).decode('ascii')})
    finally:
        plt.close('all')
