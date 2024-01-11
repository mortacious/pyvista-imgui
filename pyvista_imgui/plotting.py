from __future__ import annotations
import pyvista as pv
from .imgui_render_window import VTKImguiRenderWindowInteractor
from pyvista import global_theme
from pyvista.plotting.render_window_interactor import RenderWindowInteractor
import typing as typ
from functools import wraps
import contextlib
import numpy as np
from collections.abc import Sequence
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkRenderingCore import vtkGlyph3DMapper

__all__ = ['ImguiPlotter']

# monkey patch the pointgaussianmapper to disable the automatic rgba conversion of the colors
from pyvista.plotting.mapper import PointGaussianMapper

def _as_rgba_disabled(self):
    """Patched method to disable the rgba conversion for the PointGaussianMapper
    """
    if self.color_mode == 'direct':
        return

PointGaussianMapper.as_rgba = _as_rgba_disabled


@contextlib.contextmanager
def _no_base_plotter_init():
    init = pv.BasePlotter.__init__
    pv.BasePlotter.__init__ = lambda *args, **kwargs: None
    try:
        yield
    finally:
        pv.BasePlotter.__init__ = init

class ImguiPlotter(VTKImguiRenderWindowInteractor, pv.BasePlotter):
    """
    This class extends pyvista's BasePlotter making it available
    as a DearImGui widget. 

    To display this plotter withing an existing imgui application, just call
    the 'render'-method when building the ui. 

    Alternatively, the plotter also supports rendering as a standalone 
    imgui-application by calling the 'show'-method. It will display the plotter
    as a widget inside a minimal window-application.

    Parameters
    ----------
    multi_samples, optional
        The number of multi-samples used to mitigate aliasing. 4 is a
        good default but 8 will have better results with a potential
        impact on performance.. Defaults to None.
    line_smoothing, optional
        Enable line smoothing, by default False
    point_smoothing, optional
        Enable point smoothing, by default False
    polygon_smoothing, optional
        Enable polygon smoothing, by default False
    background, optional
        Spawn the viewer in a background thread to allow the main python interpreter to continue. 
        Only works when calling 'show'
    imgui_backend, optional
        The imgui backend to use for the ui. Use either 'pyimgui' or 'imgui_bundle'.
    """

    def __init__(self, 
                 title=None,
                 window_size=None,
                 line_smoothing: bool = False,
                 point_smoothing: bool = False,
                 polygon_smoothing: bool = False,
                 background: bool = False,
                 imgui_backend: typ.Optional[str] = None,
                 **kwargs):
        
        self._initialized = False
        
        # imgui has it's own border functionality so ignore the vtk one
        border = kwargs.pop("border", False)
        with _no_base_plotter_init():
            VTKImguiRenderWindowInteractor.__init__(self, border=border, imgui_backend=imgui_backend)
        pv.BasePlotter.__init__(self, **kwargs)
        self.title = title or "ImguiPlotter"
        self.suppress_rendering = True # disable rendering as the event loop is controlled by imgui

        self.render_window.SetMultiSamples(0)
        if line_smoothing:
            self.render_window.LineSmoothingOn()
        if point_smoothing:
            self.render_window.PointSmoothingOn()
        if polygon_smoothing:
            self.render_window.PolygonSmoothingOn()

        for renderer in self.renderers:
            self.render_window.AddRenderer(renderer)

        # Add the shadow renderer to allow us to capture interactions within
        # a given viewport
        # https://vtk.org/pipermail/vtkusers/2018-June/102030.html
        number_or_layers = self.render_window.GetNumberOfLayers()
        current_layer = self.renderer.GetLayer()
        self.render_window.SetNumberOfLayers(number_or_layers + 1)
        self.render_window.AddRenderer(self.renderers.shadow_renderer)
        self.renderers.shadow_renderer.SetLayer(current_layer + 1)
        self.renderers.shadow_renderer.SetInteractive(False)  # never needs to capture
        
        self.background_color = self.theme.background
        self._setup_interactor()

        # # Add the shadow renderer to allow us to capture interactions within
        # # a given viewport
        # # https://vtk.org/pipermail/vtkusers/2018-June/102030.html
        number_or_layers = self.render_window.GetNumberOfLayers()
        current_layer = self.renderer.GetLayer()
        self.render_window.SetNumberOfLayers(number_or_layers + 1)
        self.render_window.AddRenderer(self.renderers.shadow_renderer)
        self.renderers.shadow_renderer.SetLayer(current_layer + 1)
        self.renderers.shadow_renderer.SetInteractive(False)  # never needs to capture


        # Set window size
        self._window_size_unset = False
        if window_size is None:
            self.window_size = self._theme.window_size
            if self.window_size == pv.plotting.themes.Theme().window_size:
                self._window_size_unset = True
        else:
            self.window_size = window_size

        # # Set camera widget based on theme. This requires that an
        # # interactor be present.
        if self.theme._enable_camera_orientation_widget:
            self.add_camera_orientation_widget()

        # Set background
        self.set_background(self._theme.background)

        if self._theme.depth_peeling.enabled:
            if self.enable_depth_peeling():
                for renderer in self.renderers:
                    renderer.enable_depth_peeling()

        # set anti_aliasing based on theme
        if self.theme.anti_aliasing:
            self.enable_anti_aliasing(self.theme.anti_aliasing)

        self._run_background = background
        self._thread = None

        # self._app = None
        # Set some private attributes that let BasePlotter know
        # that this is safely rendering
        self._first_time = False  # Crucial!
        self._initialized = True

    def _setup_interactor(self) -> None:
        self.iren = RenderWindowInteractor(
            self, interactor=self.render_window.GetInteractor()
        )
        self.iren.interactor.RemoveObservers(
            "MouseMoveEvent"
        )  # slows window update?
        self.iren.initialize()
        self.enable_trackball_style()
        self.iren.add_observer("KeyPressEvent", self.key_press_event)


    def __del__(self):
        # We have to check here if the plotter was only partially initialized
        self.deep_clean()
        if self._initialized:
            del self.renderers

    @property
    def window_size(self) -> tuple[int, int]:  # numpydoc ignore=RT01
        """Return the render window size in ``(width, height)``.

        Examples
        --------
        Change the window size from ``200 x 200`` to ``400 x 400``.

        >>> import pyvista as pv
        >>> pl = pv.Plotter(window_size=[200, 200])
        >>> pl.window_size
        [200, 200]
        >>> pl.window_size = [400, 400]
        >>> pl.window_size
        [400, 400]

        """
        return tuple(self.render_window.GetSize())

    @window_size.setter
    def window_size(self, window_size):  # numpydoc ignore=GL08
        self.render_window.SetSize(window_size[0], window_size[1])
        self._window_size_unset = False
        #self.render() # rendering is controlled by imgui so do not do that here!

    def close(self, render=False):
        """Override the BasePlotter's close method to ensure correct behavior.

        Parameters
        ----------
        render : bool
            Unused argument.

        """
        from pyvista.plotting.widgets import WidgetHelper
        from pyvista.plotting.plotting import _ALL_PLOTTERS
        
        # optionally run just prior to exiting the plotter
        if self._before_close_callback is not None:
            self._before_close_callback(self)
            self._before_close_callback = None

        # must close out widgets first
        WidgetHelper.close(self)
        # Renderer has an axes widget, so close it
        self.renderers.close()
        self.renderers.remove_all_lights()

        # reset scalar bars
        self.scalar_bars.clear()
        self.mesh = None
        self.mapper = None

        if hasattr(self, 'textActor'):
            del self.textActor

        # end movie
        if hasattr(self, 'mwriter'):
            try:
                self.mwriter.close()
            except BaseException:
                pass

        # Remove the global reference to this plotter unless building the
        # gallery to allow it to collect.
        if not pv.BUILDING_GALLERY:
            if _ALL_PLOTTERS is not None:
                _ALL_PLOTTERS.pop(self._id_name, None)

        # this helps managing closed plotters
        self._closed = True 

    @wraps(pv.BasePlotter.add_actor)
    def add_actor(self, *args, **kwargs):
        """
        Override to ignore the 'render' argument
        """
        kwargs["render"] = False # never render as this is not controlled by vtk any more
        return pv.BasePlotter.add_actor(self, *args, **kwargs)
    
    @wraps(pv.BasePlotter.set_background)
    def set_background(self, color, top=None, right=None, side=None, corner=None, all_renderers=True):
        # the background color is not set unless the top color is set as well to enforce it 
        super().set_background(color, top=top or color, right=right, side=side, corner=corner, all_renderers=all_renderers)

    def show(self, 
             window_size: tuple[int, int] = None,
             before_close_callback: typ.Optional[typ.Callable] = None,
            **kwargs: typ.Any):
        """
        Show this plotter as a standalone imgui application. This call blocks until
        the resulting window is closed again.
        To integrate within an existing imgui context use render() within 
        the rendering loop.

        Parameters
        ----------
        window_size, optional
            The window size. Defaults to (1400, 1080).
        before_close_callback, optional
            An optional callback to execute before closing, by default None.
        kwargs: Exists to ensure compatiblity with the BasePlotter interface. 
                Any additional keywords are ignored for this plotter.
        """
        if before_close_callback is None:
            before_close_callback = global_theme._before_close_callback
        self._before_close_callback = before_close_callback

        if window_size is None:
            window_size = self.window_size
        else:
            self._window_size_unset = False
        self.render_window.SetSize(window_size[0], window_size[1])

        def _show():
            self.imgui_backend.show(title=self.title, window_size=window_size)

        if self._run_background:
            from threading import Thread
            self._thread = Thread(target=_show)
            self._thread.start()
        else:
            _show()
    
    def enable_pivot_style(self, pivot_sphere_radius: float = 0.25, pivot_sphere_resolution: int = 16) -> None:
        from .interactor_style_pivot import InteractorStylePivot
        pivot = InteractorStylePivot(self, pivot_sphere_radius=pivot_sphere_radius, pivot_sphere_resolution=pivot_sphere_resolution)
        return self._update_style('Pivot', pivot) 
    
    def _update_style(self, name, style_class):
        self.iren._style_class = style_class
        self.iren._style = name
        ret = self.iren.update_style()
        if getattr(self, '_fixed_clipping_range', False):
            self._style.SetAutoAdjustCameraClippingRange(True)
        return ret

    def add_glyph_mapper(self, 
                        dataset: pv.DataSet, 
                        orient: bool | str = True, 
                        scale: bool | str | typ.ArrayLike = True, 
                        factor: float = 1.0, 
                        geom: typ.Optional[pv.Dataset | tuple[pv.DataSet, ...]] = None,
                        indices: typ.Optional[tuple[float, ...]] = None, 
                        tolerance: typ.Optional[float] = None, 
                        absolute: bool = False, 
                        clamping: bool = False,
                        rng: typ.Optional[tuple[float, float]] = None, 
                        reset_camera: bool = False, 
                        name: typ.Optional[str] = None, 
                        pickable: bool = True) -> pv.Actor:
        """
        Add a Mapper copying a geometric representation (called a glyph) to the input dataset.
        This is similar to using the mesh.glyph filter in pyvista, except that all the glyph creation is 
        done at rendering time of the gpu resulting in saved memory and speedup.

        The glyphs may be oriented along the input vectors, and scaled according to scalar data or vector
        magnitude. Passing a table of glyphs to choose from based on
        scalars or vector magnitudes is also supported.  The arrays
        used for ``orient`` and ``scale`` must be either both point data
        or both cell data.

        Args:
            dataset: The dataset to build the glyphs from
            orient: If ``True``, use the active vectors array to orient the glyphs.
                    If string, the vector array to use to orient the glyphs. Defaults to True.
            scale: If ``True``, use the active scalars to scale the glyphs.
                   If string, the scalar array to use to scale the glyphs. Defaults to True.
            factor: Scale factor applied to scaling array. Defaults to 1.0.
            geom: The geometry to use for the glyph. If missing, an arrow glyph
                  is used. If a sequence is passed, the datasets inside define a table of
                  geometries to choose from based on scalars or vectors. In this
                  case a sequence of numbers of the same length must be passed as
                  ``indices``. The values of the range (see ``rng``) affect lookup
                  in the table. Defaults to None.
            indices: Specifies the index of each glyph in the table for lookup in case
                     ``geom`` is a sequence. If given, must be the same length as
                     ``geom``. If missing, a default value of ``range(len(geom))`` is
                     used. Indices are interpreted in terms of the scalar range
                     (see ``rng``). Ignored if ``geom`` has length 1.. Defaults to None.
            tolerance: Specify tolerance in terms of fraction of bounding box length.
                       Float value is between 0 and 1. Default is None. If ``absolute``
                       is ``True`` then the tolerance can be an absolute distance.
                       If ``None``, points merging as a preprocessing step is disabled. Defaults to None.
            absolute: Control if ``tolerance`` is an absolute distance or a fraction. Defaults to False.
            clamping: Turn on/off clamping of "scalar" values to range. Defaults to False.
            rng: Set the range of values to be considered by the filter when scalars values are provided. Defaults to None.
            reset_camera: Reset the camera on insertion of the actor. Defaults to False.
            name: Name of the actor. Defaults to None.
            pickable: Set whether the created actor is pickable. Defaults to True.

        Returns:
            Actor representing the glphed geometry
        """

        # Clean the points before glyphing
        if tolerance is not None:
            small = pv.PolyData(dataset.points)
            small.point_data.update(dataset.point_data)
            dataset = small.clean(point_merging=True, merge_tol=tolerance,
                                  lines_to_points=False, polys_to_lines=False,
                                  strips_to_polys=False, inplace=False,
                                  absolute=absolute)

        # Make glyphing geometry if necessary
        if geom is None:
            geom = pv.Arrow()

        # Check if a table of geometries was passed
        if isinstance(geom, (np.ndarray, Sequence)):
            if indices is None:
                # use default "categorical" indices
                indices = np.arange(len(geom))
            if not isinstance(indices, (np.ndarray, Sequence)):
                raise TypeError('If "geom" is a sequence then "indices" must '
                                'also be a sequence of the same length.')
            if len(indices) != len(geom) and len(geom) != 1:
                raise ValueError('The sequence "indices" must be the same length '
                                 'as "geom".')
        else:
            geom = [geom]
        if any(not isinstance(subgeom, vtkPolyData) for subgeom in geom):
            raise TypeError('Only PolyData objects can be used as glyphs.')

        # Prepare the mapper
        mapper = vtkGlyph3DMapper()
        if len(geom) == 1:
            # use a single glyph, ignore indices
            mapper.SetSourceData(geom[0])
        else:
            for index, subgeom in zip(indices, geom):
                mapper.SetSourceData(index, subgeom)
            mapper.SetSourceIndexing(dataset.active_scalars is not None)

        scale_array_name = None
        if isinstance(scale, str):
            mapper.SetScaleArray(scale)
            scale_array_name = scale
            #dataset.set_active_scalars(scale, 'cell')
            scale = True
        if scale:
            if scale_array_name is not None:
                scale_array = dataset.get_array(scale_array_name, preference='cell')

                if scale_array.ndim > 1:
                    mapper.SetScaleModeToScaleByVectorComponents()
                else:
                    mapper.SetScaleModeToScaleByMagnitude()
        else:
            mapper.SetScaleModeToNoDataScaling()

        if isinstance(orient, str):
            dataset.active_vectors_name = orient
            orient = True

        if scale and orient:
            if (dataset.active_vectors_info.association == pv.FieldAssociation.CELL
                    and dataset.active_scalars_info.association == pv.FieldAssociation.CELL
            ):
                source_data = dataset.cell_centers()
            elif (dataset.active_vectors_info.association == pv.FieldAssociation.POINT
                  and dataset.active_scalars_info.association == pv.FieldAssociation.POINT
            ):
                source_data = dataset
            else:
                raise ValueError("Both ``scale`` and ``orient`` must use "
                                 "point data or cell data.")
        else:
            source_data = dataset

        if rng is not None:
            mapper.SetRange(rng)
        mapper.SetOrient(orient)
        mapper.SetInputData(source_data)
        mapper.ScalingOn()
        #alg.SetVectorModeToUseVector()
        mapper.SetScaleFactor(factor)
        mapper.SetClamping(clamping)

        if name is None:
            name = '{}({})'.format(type(dataset).__name__, dataset.memory_address)

        actor, _ = self.add_actor(mapper,
                                  reset_camera=reset_camera,
                                  name=name,
                                  pickable=pickable, render=False)
        return actor
    
    def add_pointcloud(self,
                       point_cloud: pv.PointSet | pv.PolyData,
                       scalars: typ.Optional[str | typ.ArrayLike] = None,
                       **kwargs: typ.Any) -> pv.Actor:
        """
        Add a dataset (PointSet, PolyData) of any array-like object representing a point cloud  to the
        viewer. This is a specialized version of the add_points function used specifically for point clouds.
        The dataset does not require cells to be defined.

        Args:
            point_cloud: The point cloud to add.
            scalars: The scalars to use for coloring or an array of scalar values.
            **kwargs: Additional keyword arguments are passed to the ImguiPlotter.add_points function

        Returns:
            an Actor instances representing the point cloud in the viewer.
        """

        if not pv.is_pyvista_dataset(point_cloud):
            # custom conversion
            if hasattr(point_cloud, "to_vtk"):
                point_cloud = point_cloud.to_vtk(point_cloud, scalars=scalars, add_cells=False)
    
        # remove some kwargs from the arguments as they cause strange
        # behavior for point clouds or make things very sluggish:
        # -----------------------------------------------------------------------------------------------------------------
            
        # the actual size of the points is controlled via the point size attribute of prop as the option to add points
        # uses this to scale the point gaussians (slow!)
        point_size = kwargs.pop('point_size', 0.0)

        # the default is to render the points as splats so explicitly set this to False
        render_points_as_spheres = kwargs.pop('render_points_as_spheres', False)

        opacity = kwargs.pop('opacity', 1.0)

        # interpolate_before_map causes the plot function to segfault as vtk does not support this so remove it
        kwargs.pop('interpolate_before_map', None)

        # pass the arguments to the regular add_points function
        actor = self.add_points(point_cloud,
                                scalars=scalars,
                                style='points_gaussian',
                                point_size=0,
                                render_points_as_spheres=render_points_as_spheres,
                                interpolate_before_map=False,
                                opacity=1.0,
                                **kwargs)
        
        # set the point size directly in the prop
        actor.prop.point_size = point_size
        # add_points strangely sets the opacity to 0.9999 for some reason. This causes the depth buffer to break, so
        # we revert this setting
        actor.prop.opacity = opacity

        return actor