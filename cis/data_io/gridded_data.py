from time import gmtime, strftime
import logging

import iris
import numpy as np

from cis.data_io.common_data import CommonData, CommonDataList
from cis.data_io.hyperpoint import HyperPoint
from cis.data_io.hyperpoint_view import GriddedHyperPointView


def load_cube(*args, **kwargs):
    """
    Load a single GriddedData object through the iris load interface, but also attempt concatenation if merging fails

    :return GriddedData: A single GriddedData object
    :raises ValueError: If 0 or more than one cube is found
    """
    from iris.exceptions import MergeError, ConcatenateError
    # Removes warnings and prepares for future Iris change
    iris.FUTURE.netcdf_promote = True

    cubes = iris.load(*args, **kwargs)

    try:
        iris_cube = cubes.merge_cube()
    except MergeError as e:
        logging.info("Unable to merge cubes on load: \n {}\nAttempting to concatenate instead.".format(e))
        try:
            iris_cube = cubes.concatenate_cube()
        except ConcatenateError as e:
            logging.error("Unable to concatenate cubes on load: \n {}".format(e))
            raise ValueError("Unable to create a single cube from arguments given: {}".format(args))
    except ValueError as e:
        raise ValueError("No cubes found")
    return make_from_cube(iris_cube)


def make_from_cube(cube):
    gd = None
    if isinstance(cube, iris.cube.Cube):
        return GriddedData.make_from_cube(cube)
    elif isinstance(cube, iris.cube.CubeList):
        return GriddedDataList(cube)
    return gd


class GriddedData(iris.cube.Cube, CommonData):

    def __init__(self, *args, **kwargs):

        try:
            standard_name = kwargs['standard_name']
            try:
                iris.std_names.STD_NAMES[standard_name]
            except KeyError:
                rejected_name = kwargs.pop('standard_name')
                logging.warning("Standard name '{}' not CF-compliant, this standard name will not be "
                                "used in the output file.".format(rejected_name))
        except KeyError:
            pass

        self._local_attributes = []

        try:
            super(GriddedData, self).__init__(*args, **kwargs)
        except ValueError:
            rejected_unit = kwargs.pop('units')
            logging.warning("Attempted to set invalid unit '{}'.".format(rejected_unit))
            super(GriddedData, self).__init__(*args, **kwargs)

    @classmethod
    def make_from_cube(cls, cube):
        """
        Create a GriddedData object from a cube
        :param cube:
        :return:
        """
        if not isinstance(cube, GriddedData):
            cube.__class__ = GriddedData
            cube._local_attributes = []
        return cube

    def make_new_with_same_coordinates(self, data=None, var_name=None, standard_name=None,
                                       long_name=None, history=None, units=None, flatten=False):
        """
        Create a new, empty GriddedData object with the same coordinates as this one
        :param data: Data to use (if None then defaults to all zeros)
        :param var_name: Variable name
        :param standard_name: Variable CF standard name
        :param long_name: Variable long name
        :param history: Data history string
        :param units: Variable units
        :param flatten: Whether to flatten the data shape (for ungridded data only)
        :return: GriddedData instance
        """
        if data is None:
            data = np.zeros(self.shape)
        data = GriddedData(data=data, standard_name=standard_name, long_name=long_name, var_name=var_name,
                           units=units, dim_coords_and_dims=self._dim_coords_and_dims,
                           aux_coords_and_dims=self._aux_coords_and_dims, aux_factories=self._aux_factories)
        # Add history separately as it is not a constructor argument
        data.add_history(history)
        return data

    @staticmethod
    def _wrap_cube_iterator(itr):
        """Makes a generator that returns a GriddedData object from each Cube returned by an iterator.
        :param itr: iterator over Cubes
        :return: yields GriddedData objects created from Cubes
        """
        for c in itr:
            yield make_from_cube(c)

    def slices(self, *args, **kwargs):
        return self._wrap_cube_iterator(super(GriddedData, self).slices(*args, **kwargs))

    def get_coordinates_points(self):
        """Returns a HyperPointView of the points.
        :return: HyperPointView of all the data points
        """
        all_coords = [((c[0].points, c[1]) if c is not None else None) for c in self.find_standard_coords()]
        return GriddedHyperPointView(all_coords, self.data)

    def get_all_points(self):
        """Returns a HyperPointView of the points.
        :return: HyperPointView of all the data points
        """
        all_coords = [((c[0].points, c[1]) if c is not None else None) for c in self.find_standard_coords()]
        return GriddedHyperPointView(all_coords, self.data)

    def get_non_masked_points(self):
        """Returns a HyperPointView of the points.
        :return: HyperPointView of all the data points
        """
        all_coords = [((c[0].points, c[1]) if c is not None else None) for c in self.find_standard_coords()]
        return GriddedHyperPointView(all_coords, self.data, non_masked_iteration=True)

    def find_standard_coords(self):
        """Constructs a list of the standard coordinates.
        The standard coordinates are latitude, longitude, altitude, air_pressure and time; they occur in the return
        list in this order.
        :return: list of coordinates or None if coordinate not present
        """
        ret_list = []

        coords = self.coords(dim_coords=True)
        for name in HyperPoint.standard_names:
            coord_and_dim = None
            for idx, coord in enumerate(coords):
                if coord.standard_name == name:
                    coord_and_dim = (coord, idx)
                    break
            ret_list.append(coord_and_dim)

        return ret_list

    @property
    def history(self):
        """
        Return the history attribute
        :return:
        """
        return self.attributes['history']

    def add_history(self, new_history):
        """Appends to, or creates, the history attribute using the supplied history string.

        The new entry is prefixed with a timestamp.
        :param new_history: history string
        """
        timestamp = strftime("%Y-%m-%dT%H:%M:%SZ ", gmtime())
        if 'history' not in self.attributes:
            self.attributes['history'] = timestamp + new_history
        else:
            self.attributes['history'] += '\n' + timestamp + new_history

    def name(self):
        return self.var_name

    @property
    def is_gridded(self):
        """Returns value indicating whether the data/coordinates are gridded.
        """
        return True

    def set_longitude_range(self, range_start):
        """Rotates the longitude coordinate array and changes its values by
        360 as necessary to force the values to be within a 360 range starting
        at the specified value, i.e.,
        range_start <= longitude < range_start + 360

        The data array is rotated correspondingly around the dimension
        corresponding to the longitude coordinate.

        :param range_start: starting value of required longitude range
        """
        lon_coord = self.coords(standard_name="longitude")
        if len(lon_coord) == 0:
            return
        lon_coord = lon_coord[0]
        lon_idx = self.dim_coords.index(lon_coord)
        # Check if there are bounds which we will need to wrap as well
        roll_bounds = (lon_coord.bounds is not None) and (lon_coord.bounds.size != 0)
        idx1 = np.searchsorted(lon_coord.points, range_start)
        idx2 = np.searchsorted(lon_coord.points, range_start + 360.)
        shift = 0
        new_lon_points = None
        new_lon_bounds = None
        if 0 < idx1 < len(lon_coord.points):
            shift = -idx1
            lon_min = lon_coord.points[idx1]
            new_lon_points = np.roll(lon_coord.points, shift, 0)
            # Calculate which indices need 360 adding to them...
            indices_to_shift_value_of = new_lon_points < lon_min
            # ... then, add 360 to all those longitude values
            new_lon_points[indices_to_shift_value_of] += 360.0
            if roll_bounds:
                # If the coordinate has bounds then roll those as well
                new_lon_bounds = np.roll(lon_coord.bounds, shift, 0)
                # And shift all of the bounds (upper and lower) for those points which we had to shift. We can't do the
                # check independently because there may be cases where an upper or lower bound falls outside of the
                # 360 range, we leave those as they are to preserve monotonicity. See e.g.
                # test_set_longitude_bounds_wrap_at_360
                new_lon_bounds[indices_to_shift_value_of] += 360.0
        elif 0 < idx2 < len(lon_coord.points):
            shift = len(lon_coord.points) - idx2
            lon_max = lon_coord.points[idx2]
            new_lon_points = np.roll(lon_coord.points, shift, 0)
            indices_to_shift_value_of = new_lon_points >= lon_max
            new_lon_points[indices_to_shift_value_of] -= 360.0
            if roll_bounds:
                new_lon_bounds = np.roll(lon_coord.bounds, shift, 0)
                # See comment above re preserving monotinicity.
                new_lon_bounds[indices_to_shift_value_of] -= 360.0
        if shift != 0:
            # Ensure we also roll any auxilliary coordinates
            for aux_coord in self.aux_coords:
                # Find all of the data dimensions which the auxiliary coordinate spans...
                dims = self.coord_dims(aux_coord)
                # .. and check if longitude is one of those dimensions
                if lon_idx in dims:
                    # Now roll the axis of the auxiliary coordinate which is associated with the longitude data
                    # dimension: dims.index(lon_idx)
                    new_points = np.roll(aux_coord.points, shift, dims.index(lon_idx))
                    aux_coord.points = new_points
            # Now roll the data itself
            new_data = np.roll(self.data, shift, lon_idx)
            self.data = new_data
            # Put the new coordinates back in their relevant places
            self.dim_coords[lon_idx].points = new_lon_points
            if roll_bounds:
                self.dim_coords[lon_idx].bounds = new_lon_bounds

    def add_attributes(self, attributes):
        """
        Add a variable attribute to this data
        :param attributes: Dictionary of attribute names (keys) and values.
        :return:
        """
        for key, value in list(attributes.items()):
            try:
                self.attributes[key] = value
            except ValueError:
                try:
                    setattr(self, key, value)
                except ValueError as e:
                    logging.warning("Could not set NetCDF attribute '%s' because %s" % (key, e.args[0]))
        # Record that this is a local (variable) attribute, not a global attribute
        self._local_attributes.extend(list(attributes.keys()))

    def remove_attribute(self, key):
        """
        Remove a variable attribute to this data
        :param key: Attribute key to remove
        :return:
        """
        self.attributes.pop(key, None)
        try:
            self._local_attributes.remove(key)
        except ValueError:
            pass

    def save_data(self, output_file):
        """
        Save this data object to a given output file
        :param output_file: Output file to save to.
        """
        logging.info('Saving data to %s' % output_file)
        save_args = {'local_keys': self._local_attributes}
        # If we have a time coordinate then use that as the unlimited dimension, otherwise don't have any
        if self.coords('time'):
            save_args['unlimited_dimensions'] = ['time']
        else:
            iris.FUTURE.netcdf_no_unlimited = True
        iris.save(self, output_file, **save_args)

    def as_data_frame(self, copy=True):
        """
        Convert a GriddedData object to a Pandas DataFrame.

        :param copy: Create a copy of the data for the new DataFrame? Default is True.
        :return: A Pandas DataFrame representing the data and coordinates. Note that this won't include any metadata.
        """
        from iris.pandas import as_data_frame
        return as_data_frame(self, copy=copy)

    def collapsed(self, coords, kernel=None, **kwargs):
        """
        Collapse the dataset over one or more coordinates using CIS aggregation (NOT Iris). This allows multidimensional
         coordinates to be aggregated over as well.
        :param list of iris.coords.Coord or str coords: The coords to collapse
        :param iris.analysis.Aggregator kernel: The kernel to use in the aggregation
        :param kwargs: NOT USED - this is only to match the iris interface.
        :return:
        """
        return _collapse_gridded(self, coords, kernel)

    def subset(self, **kwargs):
        """
        Subset the CommonData object based on the specified constraints
        :param kwargs:
        :return:
        """
        from cis.subsetting.subset import subset, GriddedSubsetConstraint
        return subset(self, GriddedSubsetConstraint, **kwargs)

    def aggregate(self, kernel=None, **kwargs):
        """
        Aggregate based on the specified grids
        :param kernel: The kernel to use in the aggregation
        :param kwargs: The grid specifications for each coordinate dimension
        :return:
        """
        raise NotImplementedError("Aggregating gridded data to a different grid is currently unsupported")

    def sampled_from(self, data, how='', kernel=None, missing_data_for_missing_sample=True, fill_value=None,
                     var_name='', var_long_name='', var_units='', **kwargs):
        """
        Collocate the CommonData object with another CommonData object using the specified collocator and kernel

        :param CommonData or CommonDataList data: The data to resample
        :param str how: Collocation method (e.g. lin, nn, bin or box)
        :param str or cis.collocation.col_framework.Kernel kernel:
        :param bool missing_data_for_missing_sample: Should missing values in sample data be ignored for collocation?
        :param float fill_value: Value to use for missing data
        :param str var_name: The output variable name
        :param str var_long_name: The output variable's long name
        :param str var_units: The output variable's units
        :return CommonData: The collocated dataset
        """
        from cis.collocation import col_implementations as ci
        from cis.data_io.ungridded_data import UngriddedData, UngriddedDataList
        from cis.collocation.col import collocate, get_kernel

        if isinstance(data, UngriddedData) or isinstance(data, UngriddedDataList):
            col_cls = ci.GeneralGriddedCollocator()
            # Bin is the default for ungridded -> gridded collocation
            if how == '' or how == 'bin':
                con = ci.BinnedCubeCellOnlyConstraint()
            elif how == 'box':
                con = ci.SepConstraintKdtree(**kwargs)
            else:
                raise ValueError("Invalid method specified for ungridded -> gridded collocation: " + how)

            # We can have any kernel, default to moments
            kernel = get_kernel(kernel)
        elif isinstance(data, GriddedData) or isinstance(data, GriddedDataList):
            col_cls = ci.GriddedCollocator
            con = None
            if kernel is not None:
                raise ValueError("Cannot specify kernel when method is 'lin' or 'nn'")

            # Lin is the default for gridded -> gridded
            if how == '' or how == 'lin':
                kernel = ci.gridded_gridded_li()
            elif how == 'nn':
                kernel = ci.gridded_gridded_nn()
            else:
                raise ValueError("Invalid method specified for gridded -> gridded collocation: " + how)
        else:
            raise ValueError("Invalid argument, data must be either GriddedData or UngriddedData")

        col = col_cls(missing_data_for_missing_sample=missing_data_for_missing_sample, fill_value=fill_value,
                      var_name=var_name, var_long_name=var_long_name, var_units=var_units)

        return collocate(data, self, col, con, kernel)


    def _get_default_plot_type(self, lat_lon=False):
        if self.ndim == 1:
            return 'line'
        elif self.ndim ==2:
            return 'heatmap'
        else:
            raise ValueError("Unable to determine plot type for data with {} dimensions".format(self.ndim))


class GriddedDataList(iris.cube.CubeList, CommonDataList):
    """
    This class extends iris.cube.CubeList to add functionality needed for CIS to process multiple gridded data.

    It is expected that it will contain cis.data_io.gridded_data.GriddedData instances (which extend
    iris.cube.Cube) rather than IRIS cubes themselves, as there is additional functionality required which is
    present in the GriddedData wrapper.
    """

    def __str__(self):
        "<GriddedDataList: %s>" % super(GriddedDataList, self).__str__()

    @property
    def is_gridded(self):
        """Returns value indicating whether the data/coordinates are gridded.
        """
        return True

    def append(self, p_object):
        if isinstance(p_object, iris.cube.Cube):
            p_object = make_from_cube(p_object)
        super(GriddedDataList, self).append(p_object)

    def save_data(self, output_file):
        """
        Save data to a given output file
        :param output_file: File to save to
        """
        logging.info('Saving data to %s' % output_file)
        save_args = {}

        # If we have a time coordinate then use that as the unlimited dimension, otherwise don't have any
        if self.coords('time'):
            save_args['unlimited_dimensions'] = ['time']
        else:
            iris.FUTURE.netcdf_no_unlimited = True

        iris.save(self, output_file, **save_args)

    def coord(self, *args, **kwargs):
        """
        Call iris.cube.Cube.coord(*args, **kwargs) for the first item of data (assumes all data in list has
        same coordinates)
        :param args:
        :param kwargs:
        :return:
        """
        return self[0].coord(*args, **kwargs)

    def add_aux_coord(self, *args, **kwargs):
        """
        Call iris.cube.Cube.add_aux_coord(*args, **kwargs) for the all items in the data list
        :param args:
        :param kwargs:
        :return:
        """
        for var in self:
            var.add_aux_coord(*args, **kwargs)

    def coord_dims(self, *args, **kwargs):
        """
        Call iris.cube.Cube.coord_dims(*args, **kwargs) for the first item of data (assumes all data in list has
        same coordinates)
        :param args:
        :param kwargs:
        :return:
        """
        return self[0].coord_dims(*args, **kwargs)

    def remove_coord(self, *args, **kwargs):
        """
        Call iris.cube.Cube.remove_coord(*args, **kwargs) for the all items in the data list
        :param args:
        :param kwargs:
        :return:
        """
        for var in self:
            var.remove_coord(*args, **kwargs)

    def add_dim_coord(self, *args, **kwargs):
        """
        Call iris.cube.Cube.add_dim_coord(*args, **kwargs) for the all items in the data list
        :param args:
        :param kwargs:
        :return:
        """
        for var in self:
            var.add_dim_coord(*args, **kwargs)

    def aggregated_by(self, *args, **kwargs):
        """
        Build an aggregated GriddedDataList by calling iris.cube.Cube.aggregated_by(*args, **kwargs)
        for the all items in the data list
        :param args:
        :param kwargs:
        :return: GriddedDataList
        """
        data_list = GriddedDataList()
        for data in self:
            data_list.append(data.aggregated_by(*args, **kwargs))
        return data_list

    def collapsed(self, coords, kernel=None, **kwargs):
        """
        Collapse the dataset over one or more coordinates using CIS aggregation (NOT Iris). This allows multidimensional
         coordinates to be aggregated over as well.
        :param list of iris.coords.Coord or str coords: The coords to collapse
        :param iris.analysis.Aggregator kernel: The kernel to use in the aggregation
        :param kwargs: NOT USED - this is only to match the iris interface.
        :return:
        """
        return _collapse_gridded(self, coords, kernel)

    def interpolate(self, *args, **kwargs):
        """
        Perform an interpolation over the GriddedDataList using the iris.cube.Cube.interpolate() method
        :param args: Arguments for the Iris interpolate method
        :param kwargs: Keyword arguments for the Iris interpolate method
        :return: Interpolated GriddedDataList
        """
        output = GriddedDataList()
        for data in self:
            output.append(data.interpolate(*args, **kwargs))
        return output

    def regrid(self, *args, **kwargs):
        """
        Perform a regrid over the GriddedDataList using the iris.cube.Cube.regrid() method
        :param args: Arguments for the Iris regrid method
        :param kwargs: Keyword arguments for the Iris regrid method
        :return: Regridded GriddedDataList
        """
        output = GriddedDataList()
        for data in self:
            output.append(data.regrid(*args, **kwargs))
        return output

    def intersection(self, *args, **kwargs):
        """
        Call the iris.cube.Cube.intersection() method over all the cubes in a GriddedDataList
        :param args: Arguments for the Iris intersection method
        :param kwargs: Keyword arguments for the Iris intersection method
        :return: Intersected GriddedDataList or None if no data in intersection
        """
        output = GriddedDataList()
        for data in self:
            new_data = data.intersection(*args, **kwargs)
            if new_data is None:
                return None
            output.append(data.intersection(*args, **kwargs))
        return output

    def extract(self, *args, **kwargs):
        """
        Call the iris.cube.Cube.extract() method over all the cubes in a GriddedDataList
        :param args: Arguments for the Iris extract method
        :param kwargs: Keyword arguments for the Iris extract method
        :return: Extracted GriddedDataList oR None if all data excluded
        """
        output = GriddedDataList()
        for data in self:
            new_data = data.extract(*args, **kwargs)
            if new_data is None:
                return None
            output.append(data.extract(*args, **kwargs))
        return output

    def transpose(self, *args, **kwargs):
        """
        Call the iris.cube.Cube.transpose() method over all the cubes in a GriddedDataList
        :param args: Arguments for the Iris transpose method
        :param kwargs: Keyword arguments for the Iris transpose method
        """
        for data in self:
            data.transpose(*args, **kwargs)

    @property
    def dim_coords(self):
        """
        The dimension coordinates of this data
        """
        # Use the dimensions of the first item since all items should have the same dimensions
        return self[0].dim_coords

    @property
    def aux_coords(self):
        """
        The auxiliary coordinates of this data
        """
        # Use the dimensions of the first item since all items should have the same dimensions
        return self[0].aux_coords

    @property
    def ndim(self):
        """
        The number of dimensions in the data of this list.
        """
        # Use the dimensions of the first item since all items should be the same shape
        return self[0].ndim

    def subset(self, **kwargs):
        from cis.subsetting.subset import subset, GriddedSubsetConstraint
        return subset(self, GriddedSubsetConstraint, **kwargs)

    def aggregate(self, kernel=None, **kwargs):
        """
        Aggregate based on the specified grids
        :param kernel: The kernel to use in the aggregation
        :param kwargs: The grid specifications for each coordinate dimension
        :return:
        """
        raise NotImplementedError("Aggregating gridded data to a different grid is currently unsupported")


def _collapse_gridded(data, coords, kernel):
    """
    Collapse a GriddedData or GriddedDataList based on the specified grids (currently only collapsing is available)
    :param GriddedData or GriddedDataList data: The data object to aggregate
    :param list of iris.coords.Coord or str coords: The coords to collapse
    :param iris.analysis.Aggregator kernel: The kernel to use in the aggregation
    :return:
    """
    from cis.aggregation.aggregation_kernels import aggregation_kernels
    from iris.analysis import Aggregator as IrisAggregator, MEAN
    from cis.aggregation.gridded_aggregator import GriddedAggregator
    from cis.aggregation.aggregate import aggregate
    from cis.utils import listify
    from iris.coords import Coord

    # Make sure coords are a list
    coords = listify(coords)

    # This is a horrible hack to make the collapsed interface match the aggregation interface...
    kwargs = {}
    for c in coords:
        if isinstance(c, Coord):
            kwargs[c.name()] = []
        elif isinstance(c, str):
            kwargs[c] = []
        else:
            raise ValueError("Invalid coord specified: " + c)

    # Choose the right kernel - or fall back to default (MEAN)
    if isinstance(kernel, str):
        kernel_inst = aggregation_kernels[kernel]
    elif isinstance(kernel, IrisAggregator):
        kernel_inst = kernel
    elif kernel is None:
        kernel_inst = MEAN()
    else:
        raise ValueError("Invalid kernel specified: " + kernel)

    return aggregate(GriddedAggregator, data, kernel_inst, **kwargs)
