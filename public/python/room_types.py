import matplotlib.pyplot as plt
import model

def render(plan_id=None, attribute=None):
    counts = model.df.loc[model.df.entity_type_n == 'area', 'entity_subtype_n'].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(9, max(5, len(counts) * .3)))
    ax.barh(counts.index, counts.values, color='#4A90E2')
    ax.set(title='Room types on this floor', xlabel='Count')
    fig.tight_layout()
    return fig
