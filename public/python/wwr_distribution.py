import matplotlib.pyplot as plt
import model

def render(plan_id=None, attribute=None):
    table = model.wwr_table()
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(table.wwr, bins=40, color='#E74C3C', edgecolor='white')
    ax.set(title='WWR distribution on this floor (balconies excluded)', xlabel='Estimated window-to-wall ratio', ylabel='Rooms')
    if table.empty: ax.text(.5, .5, 'No non-balcony rooms', transform=ax.transAxes, ha='center')
    fig.tight_layout()
    return fig
