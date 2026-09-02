include <waveform_wall.scad>
PTS = [[0,0],[37,91],[123.5,45.25],[200,200],[311,88],[399,399],[75,320],[250,17]];
for (p = PTS) echo(str("PROBE ", p[0], " ", p[1], " ",
                        field_raw(p[0],p[1]), " ", field01(p[0],p[1])));
echo(str("NORM ", FIELD_LO, " ", FIELD_HI));
echo(str("VORTICES ", VORTICES));
echo(str("PEAKS ", PEAKS));
echo(str("DERIVED pitch=", pitch, " fins=", fin_count, " thick=", fin_thickness,
         " gap=", fin_gap, " tiles=", tile_cols, "x", tile_rows, " zs=", z_samples));
echo(str("GUARD amp=", WARP_AMP, " min_wl=", min_wavelength, " waves=", f_wave_count,
         " of ", sp(I_WAVE_COUNT), " lam_short=", f_wave_len/pow(f_harm_ratio, f_wave_count-1)));
