import matplotlib.pyplot as plt
import model

def render(plan_id=None, attribute=None):
    windows = model.df[model.df.entity_subtype_n.str.contains('WINDOW')]
    values = (windows.elevation + windows.height).dropna()
    values = values[(values > 0) & (values < 6)]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values, bins=40, color='#E67E22', edgecolor='white')
    ax.set(title='Window head heights on this floor (0–6 m)', xlabel='Sill + height (m)', ylabel='Window records')
    if values.empty: ax.text(.5, .5, 'No window head heights in this range', transform=ax.transAxes, ha='center')
    fig.tight_layout()
    return fig
