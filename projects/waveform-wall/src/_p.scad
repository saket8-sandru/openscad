include <waveform_wall.scad>
echo(str("P| tiles ", tile_cols, "x", tile_rows, " tile ", tile_w, "mm",
         " | fins/tile ", fins_per_tile, " pitch ", pitch, "mm",
         " | fin ", fin_thickness, "mm gap ", fin_gap, "mm",
         " | min_wavelength ", min_wavelength, " harmonics ", f_wave_count,
         " | back_t ", back_t));
