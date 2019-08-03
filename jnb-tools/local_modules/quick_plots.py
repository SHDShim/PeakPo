import matplotlib.pyplot as plt
import numpy as np

def plot_diffpattern(ax_pattern, model):
    """
    ax_pattern = axis of diffraction pattern
    model = PeakPo model
    """
    wavelength = model.base_ptn.wavelength
    ax_pattern.set_ylabel('Intensity (arbitrary unit)')

    ax_pattern.set_yticks([])
    x_data, y_data = model.base_ptn.get_bgsub()
    xrange = [x_data.min(), x_data.max()]
    yrange = [y_data.min(), y_data.max()]
    ax_pattern.set_xlim(xrange)    
    ax_pattern.set_ylim(yrange)        
    ax_pattern.plot(x_data, y_data, c='k', lw=1.0)
    ax_pattern.set_xlabel('Two Theta (degrees)')
    
def plot_jcpds(ax_pattern, model):
    selected_phases = []
    for phase in model.jcpds_lst:
        if phase.display:
            selected_phases.append(phase)
    n_displayed_jcpds = len(selected_phases)
    axisrange = ax_pattern.axis()
    pressure = model.get_saved_pressure()
    temperature = model.get_saved_temperature()
    wavelength =  model.base_ptn.wavelength
    bar_min = 0.
    bar_scale = 1. / 100. * axisrange[3] 
    for i, phase in enumerate(selected_phases):
        phase.cal_dsp(pressure, temperature)
        tth, inten = phase.get_tthVSint(wavelength)
        intensity = inten * phase.twk_int
        if pressure == 0.:
            volume = phase.v
        else:
            volume = phase.v.item()
        ax_pattern.vlines(
            tth, bar_min, intensity*bar_scale, colors=phase.color,
            label=phase.name, lw=1.0, alpha=1.0)
    ax_pattern.legend()