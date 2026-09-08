import matplotlib.pyplot as plt
import model

def render(plan_id=None, attribute=None):
    table = model.wwr_table()
    means = table.groupby('room_type').wwr.mean().sort_values()
    fig, ax = plt.subplots(figsize=(9, max(5, len(means) * .3)))
    ax.barh(means.index, means.values, color='#8E44AD')
    ax.set(title='Mean WWR by room type on this floor', xlabel='Mean estimated WWR')
    if table.empty: ax.text(.5, .5, 'No non-balcony rooms', transform=ax.transAxes, ha='center')
    fig.tight_layout()
    return fig
