from generic_plot import Generic_Plot

class Histogram_3D(Generic_Plot):
    valid_histogram_styles = ["bar", "step", "stepfilled"]
    def plot(self):
        vmin = self.mplkwargs.pop("vmin")
        vmax = self.mplkwargs.pop("vmax")

        self.matplotlib.hist2d(self.unpacked_data_items[0]["x"], self.unpacked_data_items[1]["x"], *self.mplargs, **self.mplkwargs)

        self.mplkwargs["vmin"] = vmin
        self.mplkwargs["vmax"] = vmax

    def format_plot(self):
        self.format_3d_plot()

    def set_default_axis_label(self, axis):
        self.set_default_axis_label_for_comparative_plot(axis)

    def calculate_axis_limits(self, axis):
        valrange = {}
        if axis == "x":
            coord_axis = "x"
        elif axis == "y":
            coord_axis = "data"
        valrange[axis + "min"], valrange[axis + "max"] = self.calculate_min_and_max_values_of_array_including_case_of_log(axis, self.unpacked_data_items[0][coord_axis])
        return valrange

    def apply_axis_limits(self, valrange, axis):
        if valrange is not None:
            if axis == "x":
                step = valrange.pop("xstep", None)
                self.matplotlib.xlim(**valrange)
                if step is not None: valrange["xstep"] = step
            elif axis == "y":
                step = valrange.pop("ystep", None)
                self.matplotlib.ylim(**valrange)
                if step is not None: valrange["ystep"] = step

    def create_legend(self):
        pass

    def add_color_bar(self, logv, vmin, vmax, v_range, orientation, units):
        # nformat = "%e"
        # nformat = "%.3f"
        # nformat = "%.3e"
        nformat = "%.3g"

        cbar = self.matplotlib.colorbar(orientation = orientation, format = nformat)

        cbar.set_label("Frequency")

