import logging
from abc import abstractmethod, ABCMeta

from matplotlib.ticker import MaxNLocator, AutoMinorLocator


def format_units(units):
    """
    :param units: The units of a variable, as a string
    :return: The units surrounding brackets, or the empty string if no units given
    """
    if "since" in str(units):
        # Assume we are on a time if the units contain since.
        return ""
    elif units:
        return "(" + str(units) + ")"
    else:
        return ""


def get_label(common_data):
    # in general, display both name and units in brackets
    name = common_data.name()
    name = "" if name is None else name + " "
    return name + format_units(common_data.units)


def calc_min_and_max_vals_of_array_incl_log(array, log=False):
    """
    Calculates the min and max values of a given array.
    If a log scale is being used only positive values are taken into account
    :param array: The array to calculate the min and max values of
    :param log: Is a log scale being used?
    :return: The min and max values of the array
    """

    if log:
        import numpy.ma as ma
        positive_array = ma.array(array, mask=array <= 0)
        min_val = positive_array.min()
        max_val = positive_array.max()
    else:
        min_val = array.min()
        max_val = array.max()
    return min_val, max_val


class APlot(object):

    __metaclass__ = ABCMeta

    # TODO: Reorder these into roughly the order they are most commonly used
    # @initializer
    def __init__(self, packed_data_items, ax, xaxis, yaxis, color=None,
                 edgecolor=None, itemstyle=None, itemwidth=None, label=None, *mplargs, **mplkwargs):
        """
        Constructor for Generic_Plot.
        Note: This also calls the plot method

        :param ax: The matplotlib axis on which to plot
        :param datagroup: The data group number in an overlay plot, 0 is the 'base' plot
        :param packed_data_items: A list of packed (i.e. Iris cubes or Ungridded data objects) data items
        :param plot_args: A dictionary of plot args that was created by plot.py
        :param mplargs: Any arguments to be passed directly into matplotlib
        :param mplkwargs: Any keyword arguments to be passed directly into matplotlib
        """
        # Raw data attributes (for unpacking the packed data into)
        self.data = None
        self.x = None
        self.y = None

        self.ax = ax

        self.xaxis = xaxis
        self.yaxis = yaxis
        self.color = color
        self.label = label
        self.edgecolor = edgecolor
        self.itemstyle = itemstyle
        self.itemwidth = itemwidth

        self.mplargs = mplargs
        self.mplkwargs = mplkwargs

        self.color_axis = []

    @abstractmethod
    def __call__(self):
        """
        The method that will do the plotting. To be implemented by each subclass of Generic_Plot.
        """
        pass

    @staticmethod
    def guess_axis_label(data, axisvar=None, axis=None):
        """
        :param data: The data to inspect for names and units
        :param axisvar: An axis name to look in coords for
        :param axis: An axis label (x or y)
        """
        import cis.exceptions as cisex
        import iris.exceptions as irisex
        try:
            if axisvar is None:
                # If axisvar is None data.coord will happily return a Coord if only one Coord is there
                raise cisex.CoordinateNotFoundError
            coord = data.coord(axisvar)
        except (cisex.CoordinateNotFoundError, irisex.CoordinateNotFoundError):
            name = data.name()
            units = data.units
        else:
            name = coord.name()
            units = coord.units

        # in general, display both name and units in brackets
        name = "" if name is None else name + " "
        return name + format_units(units)

    @staticmethod
    def valid_number_of_datagroups(number_of_datagroups):
        return number_of_datagroups == 1
