import pytest
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def test_plot_radar():
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    stats = [0.8, 0.9, 0.85, 0.86, 0.7, 0.8]
    
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='blue', alpha=0.25)
    ax.plot(angles, stats, color='blue', linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    
    # Save to temp buffer
    import io
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    assert len(buf.getvalue()) > 0
