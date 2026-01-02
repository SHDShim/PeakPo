import numpy as np
from xrd_unitconv import *

def plot_diffcake(ax_cake, model, xrange=[5,20], yrange=None, 
                  no_yticks=True, dsp_ticks=False, mid_angle = 0, 
                  no_xlabel=False, no_ylabel=False, dsp_step = 0.2, 
                  clim=(1.e2, 7.e3), 
                  tick_decimals=2):
    """
    ax_pattern = axis of diffraction pattern
    model = PeakPo model
    
    """
    wavelength = model.base_ptn.wavelength
    if not no_ylabel:
        ax_cake.set_ylabel('Azimuthal angle (degrees)')

    if no_yticks:
        ax_cake.set_yticks([])
        
    int_cake = model.__dict__['diff_img'].__dict__['intensity_cake']
    intensity_c = np.array(int_cake)
    intensity_cake = np.ones_like(intensity_c)
    intensity_cake[0:mid_angle] = intensity_c[360 - mid_angle:361]
    intensity_cake[mid_angle:361] = intensity_c[0:360 - mid_angle]

    tth_cake = model.__dict__['diff_img'].__dict__['tth_cake']
    chi_cake = model.__dict__['diff_img'].__dict__['chi_cake']
    
    """
    if dsp_ticks and (xrange is not None):
        xrange[0] = dsp2tth(xrange[0], wavelength)
        xrange[1] = dsp2tth(xrange[1], wavelength)        
    """
    
    if xrange is None:
        xrange = [tth_cake.min(), tth_cake.max()]
    if yrange is None:
        yrange = [chi_cake.min(), chi_cake.max()]
    #x = np.ma.masked_where( (tth_cake <= xrange[0]) | (tth_cake >= xrange[1]), tth_cake )
    #y = np.ma.masked_where( (tth_cake <= xrange[0]) | (tth_cake >= xrange[1]), intensity_cake )
    x = tth_cake
    y = intensity_cake
    ax_cake.set_xlim(xrange)    
    ax_cake.set_ylim(yrange)        
    ax_cake.imshow(intensity_cake, origin="lower", 
                   extent=[tth_cake.min(), tth_cake.max(), chi_cake.min(), chi_cake.max()], 
           aspect="auto", cmap="gray_r", clim=clim)

    #if xrange is not None:
    #    ax_pattern.set_xlim(x.min(),x.max())
    x_roi = np.ma.masked_outside(x, xrange[0], xrange[1]).compressed()

    if dsp_ticks:
        dsp_roi = tth2dsp(x_roi, wavelength)
        ticks_min = np.floor( 
            (dsp_roi.max()*np.power(10.,tick_decimals))) / np.power(10.,tick_decimals)
        ticks_max = np.ceil( 
            (dsp_roi.min()*np.power(10.,tick_decimals))) / np.power(10.,tick_decimals)
        ticks = np.arange( ticks_min, ticks_max, -1.*dsp_step)
        if ticks.size <= 20.:
            ticks_in_tth = dsp2tth(ticks, wavelength)
            ax_cake.set_xticks(ticks_in_tth)
            ax_cake.set_xticklabels(np.around(ticks, decimals=tick_decimals))
        if not no_xlabel:
            ax_cake.set_xlabel('d-spacing ($\mathdefault{\AA}$)')
    else:
        if not no_xlabel:
            ax_cake.set_xlabel('Two Theta (degrees)')

def plot_diffpattern(ax_pattern, model, xrange=None, yrange=None, bgsub=True,
                    no_yticks=True, dsp_ticks=False, dsp_step = 0.2,
                    no_xlabel=False):
    """
    ax_pattern = axis of diffraction pattern
    model = PeakPo model
    xrange = always in two theta unit even for dsp_ticks=True
    """
    wavelength = model.base_ptn.wavelength
    ax_pattern.set_ylabel('Intensity (arbitrary unit)')

    if no_yticks:
        ax_pattern.set_yticks([])
    if bgsub:
        x_data, y_data = model.base_ptn.get_bgsub()
    else:
        x_data, y_data = model.base_ptn.get_raw()
    """    
    if dsp_ticks and (xrange is not None):
        xrange[0] = dsp2tth(xrange[0], wavelength)
        xrange[1] = dsp2tth(xrange[1], wavelength)        
    """
    if xrange is None:
        xrange = [x_data.min(), x_data.max()]
    if yrange is None:
        yrange = [y_data.min(), y_data.max()]
    x = np.ma.masked_where( (x_data <= xrange[0]) | (x_data >= xrange[1]), x_data )
    y = np.ma.masked_where( (x_data <= xrange[0]) | (x_data >= xrange[1]), y_data )
    ax_pattern.set_xlim(xrange)    
    ax_pattern.set_ylim(yrange)        
    ax_pattern.plot(x, y, c='k', lw=1.0)

    #if xrange is not None:
    #    ax_pattern.set_xlim(x.min(),x.max())

    if dsp_ticks:
        ticks = np.arange( np.floor( (tth2dsp(x, wavelength)*10.).max())/10.,
                          np.ceil( (tth2dsp(x, wavelength)*10.).min())/10.,-dsp_step)
        ticks_in_tth = dsp2tth(ticks, wavelength)
        ax_pattern.set_xticks(ticks_in_tth)
        ax_pattern.set_xticklabels(np.around(ticks, decimals=2))
        if not no_xlabel:
            ax_pattern.set_xlabel('d-spacing ($\mathdefault{\AA}$)')
    else:
        if not no_xlabel:
            ax_pattern.set_xlabel('Two Theta (degrees)')
        
def plot_jcpds(ax_pattern, model, 
               in_cake=False,
               show_index=False, show_legend=False,
               bar_height=1., bar_position=0., bar_vsep=0.,
              phase_names=None, bar_alpha=1.0, bar_thick=1.):
    """
    bar position: position of the bar base in fraction.  negative number will shift 
        bars further down
    """
    selected_phases = []
    for phase in model.jcpds_lst:
        if phase.display:
            selected_phases.append(phase)
    if phase_names is not None:
        if len(phase_names) != len(selected_phases):
            return
    else:
        phase_names = []
        for phase in selected_phases:
            phase_names.append(phase.name) 
            
    n_displayed_jcpds = len(selected_phases)
    axisrange = ax_pattern.axis()
    #bar_scale = 1. / 100. * axisrange[3] * bar_factor / 100.
    pressure = model.get_saved_pressure()
    temperature = model.get_saved_temperature()
    wavelength =  model.base_ptn.wavelength
    for i, phase in enumerate(selected_phases):
        phase.cal_dsp(pressure, temperature)
        tth, inten = phase.get_tthVSint(wavelength)
        intensity = inten * phase.twk_int
        starting_intensity = np.ones_like(tth) * axisrange[2] - \
            bar_position * (axisrange[3] - axisrange[2])
        if in_cake:
            bar_max = axisrange[3] * np.ones_like(tth)
            bar_min = axisrange[2] * np.ones_like(tth)
        else:
            bar_max = starting_intensity - \
                (i*bar_vsep) * 100. * (bar_height) / n_displayed_jcpds
            bar_min = starting_intensity - \
                (i*bar_vsep+1) * 100. * (bar_height) / n_displayed_jcpds
        if pressure == 0.:
            volume = phase.v
        else:
            volume = phase.v.item()
        ax_pattern.vlines(
            tth, bar_min, bar_max, colors=phase.color,
            label=phase_names[i],
            lw=bar_thick,
            alpha=bar_alpha)
        # hkl
        if show_index:
            hkl_list = phase.get_hkl_in_text()
            for j, hkl in enumerate(hkl_list):
                if tth[j] >= axisrange[0] and tth[j] <= axisrange[1]:
                    ax_pattern.text(
                        tth[j], bar_max[j], hkl.replace(" ", ""), color=phase.color,
                        rotation=90, verticalalignment='bottom',
                        horizontalalignment='center',
                        fontsize=8.,
                        alpha=1.0)
        if in_cake:
            pass
        else:
            ax_pattern.text(
                axisrange[0] + (axisrange[1] - axisrange[0])*0.01, 
                (bar_max[0] + bar_min[0])/2., phase_names[i],
                color=phase.color,
                verticalalignment='center',
                horizontalalignment='left',
                fontsize=8.,
                alpha=1.0)
    ymin = axisrange[2] - bar_position * (axisrange[3] - axisrange[2]) - \
        ( (n_displayed_jcpds-1) * bar_vsep + 1) * 100. * bar_height / n_displayed_jcpds
    if not in_cake:
        ax_pattern.set_ylim((ymin, axisrange[3]))

    if show_legend:
        leg_jcpds = ax_pattern.legend(
            loc=0, prop={'size': 10}, framealpha=0., handlelength=1)
        for line, txt in zip(leg_jcpds.get_lines(), leg_jcpds.get_texts()):
            txt.set_color(line.get_color())