import matplotlib.pyplot as plt
import model

def render(plan_id=None, attribute=None):
    values = model.df.loc[model.df.entity_type_n == 'area', 'height'].dropna()
    values = values[(values > 0) & (values < 6)]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(values, bins=40, color='#27AE60', edgecolor='white')
    ax.set(title='Room ceiling heights on this floor (0–6 m)', xlabel='Height (m)', ylabel='Rooms')
    if values.empty: ax.text(.5, .5, 'No heights in this range', transform=ax.transAxes, ha='center')
    fig.tight_layout()
    return fig
