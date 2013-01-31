from jasmin_cis.plot import Plotter
from jasmin_cis.data_io.read import read_variable_from_files
from jasmin_cis.test.test_util.mock import gen_random_data, gen_random_lon, gen_random_lat, ScatterData

x1 = [gen_random_lon(), gen_random_lon(), gen_random_lon(), gen_random_lon(), gen_random_lon()]
x2 = [gen_random_lon(), gen_random_lon(), gen_random_lon(), gen_random_lon(), gen_random_lon()]
y1 = [gen_random_lat(), gen_random_lat(), gen_random_lat(), gen_random_lat(), gen_random_lat()]
y2 = [gen_random_lat(), gen_random_lat(), gen_random_lat(), gen_random_lat(), gen_random_lat()]
data = [gen_random_data(), gen_random_data(), gen_random_data(), gen_random_data(), gen_random_data()]
scatter_data1 = ScatterData(x1, y1, data, (len(x1), len(y1)), "Scatter 1")
scatter_data2 = ScatterData(x2, y2, None, (len(x2), len(y2)), "Scatter 2")
heatmap_cube =  read_variable_from_files("/home/shared/NetCDF Files/xglnwa.pm.k8dec-k9nov.col.tm.nc", "rain")

Plotter([heatmap_cube, scatter_data1, scatter_data2], datafiles = [{"itemstyle" : None, "color" : None, "label": None}, 
                                                                   {"itemstyle" : "*", "color" : None, "label": "Scatter 1"}, 
                                                                   {"itemstyle" : "p", "color" : "black", "label": "Scatter 2"}],
                                                                     itemwidth = 30, cbarorient = "vertical")