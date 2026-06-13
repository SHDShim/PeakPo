from lmfit.models import PseudoVoigtModel, LinearModel
from lmfit import Parameters

def make_model(peak_positions, fwhm=0.05, max_fwhm=0.5, pos_range=0.5, amplitude=1000.):
    n_peaks = len(peak_positions)
    pars = Parameters()

    bg = LinearModel(prefix='bg_')
    pars.update(bg.make_params(slope=0, intercept=0))
    
    mod = bg
    #pars['bg_intercept'].set(vary=True)
    #pars['bg_slope'].set(vary=True)

    for i in range(n_peaks):
        prefix = 'pk{}_'.format(i)
        peak = PseudoVoigtModel(prefix= prefix)
        # Set this zero
        pars.update( peak.make_params())
        pars[prefix+'center'].set(peak_positions[i], min=peak_positions[i]-pos_range, 
                                  max=peak_positions[i]+pos_range, vary=True)
        pars[prefix+'sigma'].set(fwhm, min=0., max=max_fwhm, vary=True)
        pars[prefix+'amplitude'].set(amplitude, min=0., vary=True)
        pars[prefix+'fraction'].set(0.0, min=0., max=1., vary=True)
        mod += peak
    return mod, pars
    
def plot_fitresult(ax, x, y, out, n_peaks):
    #plt.title(data_filename)
    comps = out.eval_components(x=x)
    ax.plot(x, y, 'k.', label='data')
    #plt.plot(spr_x, init, 'k--')
    ax.plot(x, out.best_fit, 'b-', label='total fit')
    #plt.plot(x, comps['pk_water_'], 'b-', label='indiv. peak')
    #plt.plot(x, comps['pk1_']+comps['pk2_']+comps['pk3_']+comps['pk4_'], 'g-', label='No H2O')
    #plt.plot(spr_x_fit, comps['bg_'], 'b-', label='background')
    ax.plot(x, y - out.best_fit - y.max()*0.2, 'g-', label='fit residue')

    for i in range(n_peaks):
        prefix = 'pk{}_'.format(i)
        ax.axvline(out.params[prefix+'center']) 
        ax.plot(x, comps[prefix] - y.max()*0.1, 'r-', label='indiv. peak')

    ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))