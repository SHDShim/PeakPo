from peakpo.ds_jcpds.jcpds import JCPDSplt


def test_plot_cache_key_changes_with_eos_tweaks():
    phase = JCPDSplt()

    key_before = phase._make_cal_dsp_key(
        pressure=10.0,
        temperature=300.0,
        b_a=1.0,
        c_a=1.0,
        use_table_for_0GPa=True,
    )
    phase.twk_k0 = 1.1
    key_after = phase._make_cal_dsp_key(
        pressure=10.0,
        temperature=300.0,
        b_a=1.0,
        c_a=1.0,
        use_table_for_0GPa=True,
    )

    assert key_after != key_before


def test_plot_cache_key_is_stable_when_inputs_are_unchanged():
    phase = JCPDSplt()

    first = phase._make_cal_dsp_key(5.0, 500.0, 1.0, 1.2, False)
    second = phase._make_cal_dsp_key(5.0, 500.0, 1.0, 1.2, False)

    assert second == first
