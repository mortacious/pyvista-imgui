from __future__ import annotations
from vtkmodules.util import numpy_support as VN
from vtkmodules.vtkCommonCore import vtkFloatArray
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkFiltersCore import vtkTriangleMeshPointNormals
from vtkmodules.vtkRenderingOpenGL2 import vtkOpenGLPolyDataMapper
from vtkmodules.vtkCommonTransforms import vtkTransform

import numpy as np
from numpy.typing import ArrayLike
from pyvista.plotting.render_window_interactor import _style_factory
import pyvista as pv
from typing import Any, Sequence


class DefaultInteractorKeybindsMixin:
    def __init__(self) -> None:
        self.add_observer('CharEvent', self.on_char_event)
        self.__key_dispatcher = {
            'f': self._fly_to_point,
            'r': self._reset_camera,
            'p': self._pick,
        }

    def on_char_event(self, obj: Any, event: Any) -> None:
        interactor = self.GetInteractor()
        key = interactor.GetKeyCode()
        event_pos = interactor.GetEventPosition()
        self.FindPokedRenderer(event_pos[0], event_pos[1])

        try:
            self.__key_dispatcher[key]()
        except KeyError:
            pass

    def _fly_to_point(self) -> None:
        interactor = self.GetInteractor()
        event_pos = interactor.GetEventPosition()
        self._set_pivot(event_pos)
        self._show_pivot_sphere()

        interactor.SetDolly(1.0)
        interactor.FlyTo(self.GetCurrentRenderer(), self.pivot)
        self._hide_pivot_sphere()

    def _reset_camera(self) -> None:
        renderer = self.GetCurrentRenderer()
        if renderer:
            renderer.ResetCamera()
        self.GetInteractor().Render()

    def _pick(self) -> None:
        interactor = self.GetInteractor()
        renderer = self.GetCurrentRenderer()
        if renderer:
            interactor.StartPickCallback()
            picker = interactor.GetPicker()
            if picker:
                event_pos = interactor.GetEventPosition()
                picker.Pick(event_pos[0], event_pos[1], 0.0, renderer)
            interactor.EndPickCallback()


__all__ = ["InteractorStylePivot"]

def _normalize(v: ArrayLike) -> ArrayLike:
    """Normalize the array

    Args:
        v: _description_

    Returns:
        _description_
    """
    v = np.asarray(v)
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def _create_pivot_sphere(radius: float = 0.25, resolution: int = 16) -> pv.Actor:
    sphere = vtkSphereSource()
    sphere.SetRadius(radius)
    sphere.SetThetaResolution(resolution)
    sphere.SetPhiResolution(resolution)
    norms = vtkTriangleMeshPointNormals()
    norms.SetInputConnection(sphere.GetOutputPort())
    norms.Update()
    sphere_mapper = vtkOpenGLPolyDataMapper()
    sphere_mapper.SetInputConnection(norms.GetOutputPort())
    del sphere

    pivot_sphere = pv.Actor()
    pivot_sphere.mapper = sphere_mapper

    pivot_sphere.GetProperty().SetColor(1, 1, 1)
    pivot_sphere.prop.SetRepresentationToSurface()
    pivot_sphere.prop.SetAmbientColor(0.2, 0.2, 1.0)
    pivot_sphere.prop.SetDiffuseColor(1.0, 0.65, 0.7)
    pivot_sphere.prop.SetSpecularColor(1.0, 1.0, 1.0)
    pivot_sphere.prop.SetSpecular(0.5)
    pivot_sphere.prop.SetDiffuse(0.7)
    pivot_sphere.prop.SetAmbient(0.5)
    pivot_sphere.prop.SetSpecularPower(20.0)
    pivot_sphere.prop.SetOpacity(1.0)
    #sp = pivot_sphere.GetShaderProperty()

    # modify the shader to generate the normal colors
    # sp.AddVertexShaderReplacement(
    #     "//VTK::Normal::Dec",
    #     True,
    #     "//VTK::Normal::Dec\n"
    #     "  varying vec3 myNormalMCVSOutput;\n",
    #     False)
    # sp.AddVertexShaderReplacement(
    #     "//VTK::Normal::Impl",
    #     True,
    #     "//VTK::Normal::Impl\n"
    #     "  myNormalMCVSOutput = normalMC;\n",
    #     False)
    # sp.AddFragmentShaderReplacement(
    #     "//VTK::Normal::Dec",
    #     True,
    #     "//VTK::Normal::Dec\n"
    #     "  varying vec3 myNormalMCVSOutput;\n",
    #     False)
    # sp.AddFragmentShaderReplacement(
    #     "//VTK::Normal::Impl",
    #     True,
    #     "//VTK::Normal::Impl\n"
    #     "  diffuseColor = abs(myNormalMCVSOutput);\n",
    #     False)

    del sphere_mapper

    return pivot_sphere


_TrackBallStyle = _style_factory('TrackballCamera')


class InteractorStylePivot(DefaultInteractorKeybindsMixin, _TrackBallStyle):
    """
    Custom interactor style that does every interaction relative to a pivot point under the mouse pointer.
    The pivot point is picked on every mouse click using a window size dependent tolerance. If there is no point under
    the mouse the previous pivot point is used.

    Args:
        parent: The parent of this instance
        pivot_sphere_radius: The radius of the pivot sphere. Defaults to 0.25.
        pivot_sphere_resolution: The number of segments used to draw the sphere. Defaults to 16.
    """
    def __init__(self, parent: Any, 
                 pivot_sphere_radius: float = 0.25, 
                 pivot_sphere_resolution: int = 16) -> None:
        _TrackBallStyle.__init__(self, parent)
        DefaultInteractorKeybindsMixin.__init__(self)
        self.remove_observers()
        self.add_observer("LeftButtonPressEvent", self._left_button_press_event)
        self.add_observer("LeftButtonReleaseEvent", self._left_button_release_event)
        self.add_observer("RightButtonPressEvent", self._right_button_press_event)
        self.add_observer("RightButtonReleaseEvent", self._right_button_release_event)
        self.add_observer("MouseMoveEvent", self._mouse_move_event)
        self.add_observer("MiddleButtonPressEvent", self._middle_button_press_event)
        self.add_observer("MiddleButtonReleaseEvent", self._middle_button_release_event)
        self.add_observer("MouseWheelForwardEvent", self._mousewheel_forward_event)
        self.add_observer("MouseWheelBackwardEvent", self._mousewheel_backward_event)

        # create focus sphere actor
        self._pivot_sphere_radius = pivot_sphere_radius
        self._pivot_sphere_resolution = pivot_sphere_resolution
        self._pivot_sphere_visible = False

        self._pivot_sphere = _create_pivot_sphere(pivot_sphere_radius, pivot_sphere_resolution)

        self.left_down = False
        self.right_down = False
        self.state = 0
        self.pivot = [0, 0, 0]
        self.tolerance = 0.002

    @property
    def pivot_sphere_radius(self) -> float:
        return self._pivot_sphere_radius

    @pivot_sphere_radius.setter
    def pivot_sphere_radius(self, radius: float) -> None:
        show_again = False
        if self._pivot_sphere_visible:
            show_again = True
            self._hide_pivot_sphere()
        self._pivot_sphere_radius = radius
        self._pivot_sphere = _create_pivot_sphere(self._pivot_sphere_radius, self._pivot_sphere_resolution)
        if show_again:
            self._show_pivot_sphere()

    @property
    def pivot_sphere_resolution(self) -> int:
        return self._pivot_sphere_resolution

    @pivot_sphere_resolution.setter
    def pivot_sphere_resolution(self, resolution: int) -> None:
        show_again = False
        if self._pivot_sphere_visible:
            show_again = True
            self._hide_pivot_sphere()
        self._pivot_sphere_resolution = resolution
        self._pivot_sphere = _create_pivot_sphere(self._pivot_sphere_radius, self._pivot_sphere_resolution)
        if show_again:
            self._show_pivot_sphere()

    @property
    def tolerance(self) -> float:
        """
        Tolerance of the mouse pointer in percentage of the window diagonal size.

        Returns:
            the tolerance parameter

        """
        return self.__tolerance

    @tolerance.setter
    def tolerance(self, tol: float) -> None:
        """
        Tolerance of the mouse pointer in percentage of the window diagonal size.

        Args:
            tol: the new tolerance
        """
        self.__tolerance = tol

    @property
    def translation_plane_normal(self) -> np.ndarray:
        """
        EXPERIMENTAL
        The plane normal used for the translation.

        Returns:
            The normal vector
        """
        return getattr(self, '_translation_plane_normal', None)

    @translation_plane_normal.setter
    def translation_plane_normal(self, plane: ArrayLike) -> None:
        """        
        EXPERIMENTAL
        The plane normal used for the translation

        Args:
            plane: the plane normal
        """
        plane = np.asarray(plane).ravel()
        if len(plane) != 3:
            raise ValueError("Plane must be a normalized vector of 3 components")
        self._translation_plane_normal = plane

    def _set_pivot(self, event_pos: tuple[int, int]) -> None:
        """
        Pick a new pivot point based on the event position.
        The point is determined by extracting an area from the renderer's depth buffer
        and choosing the pixel position closest to the event position. This position is then projected
        into world coordinates.

        Args:
            event_pos: the event position in display coordinates

        Returns:
            True, if a new pivot point has been picked, False otherwise
        """
        self.FindPokedRenderer(event_pos[0], event_pos[1])
        renwin = self.GetInteractor().GetRenderWindow()
        win_size = np.asarray(renwin.GetSize())
        diagonal_len = np.sqrt(np.sum(win_size**2))
        vfa = vtkFloatArray()
        extent = int(np.ceil(self.tolerance * diagonal_len))
        renwin.GetZbufferData(event_pos[0] - extent, event_pos[1] - extent, event_pos[0]+extent, event_pos[1]+extent, vfa)
        size = extent * 2 + 1
        data = VN.vtk_to_numpy(vfa).reshape(size, size) - 1.0

        nonzero = np.nonzero(data)
        if len(nonzero[0]) > 0:
            distances_screen = (nonzero[0] - extent) ** 2 + (nonzero[1] - extent) ** 2
            distances_scene = data[nonzero]

            distances_total = distances_scene * (distances_screen + 1 + 100) #distances_screen * 0.5 + distances_scene * 0.5

            #print("distances_scene", distances_scene.min(), distances_scene.max())
            #print("distances_screen", distances_screen.min(), distances_screen.max())
            min_id = np.argmin(distances_total)
            nearest_index = (nonzero[0][min_id], nonzero[1][min_id])
            event_pos = (event_pos[0] - extent + nearest_index[0], event_pos[1] - extent + nearest_index[1])
            renderer = self.GetCurrentRenderer()
            world = np.zeros(4)
            self.ComputeDisplayToWorld(renderer, *event_pos, data[nearest_index] + 1.0, world)
            for i in range(3):
                self.pivot[i] = world[i] / world[3]
            return True
        return False

    def _scale_pivot_sphere(self) -> None:
        camera = self.GetCurrentRenderer().GetActiveCamera()
        from_pos = camera.GetPosition()
        vec = np.asarray(self.pivot) - np.asarray(from_pos)
        at_v = _normalize(camera.GetDirectionOfProjection())
        s = 0.02 * np.dot(at_v, vec)
        self._pivot_sphere.SetScale(s, s, s)

    def _show_pivot_sphere(self) -> None:
        """
        Show a sphere at the pivot position
        """
        self._pivot_sphere.SetPosition(self.pivot)
        # calculate scale so focus sphere always is the same size on the screen
        self._scale_pivot_sphere()
        self._focus_sphere_renderer = self.GetCurrentRenderer()
        self._focus_sphere_renderer.AddActor(self._pivot_sphere)
        self._pivot_sphere_visible = True

        self.GetInteractor().Render()

    def _hide_pivot_sphere(self) -> None:
        """
        Hide the sphere if it is visible
        """
        sphere_renderer = getattr(self, '_focus_sphere_renderer', None)
        if sphere_renderer:
            sphere_renderer.RemoveActor(self._pivot_sphere)
            self._pivot_sphere_visible = False

    def _left_button_press_event(self, obj: Any, event: Any) -> None:
        click_pos = self.GetInteractor().GetEventPosition()
        self.left_down = True
        if not self.right_down:
            self._set_pivot(click_pos)
            self._show_pivot_sphere()
        self.last_pos = click_pos

        super().OnLeftButtonDown()

    def _right_button_press_event(self, obj: Any, event: Any) -> None:
        click_pos = self.GetInteractor().GetEventPosition()
        self.right_down = True
        if not self.left_down:
            self._set_pivot(click_pos)
            self._show_pivot_sphere()
        self.last_pos = click_pos
        super().OnMiddleButtonDown()

    def _middle_button_press_event(self, obj: Any, event: Any) -> None:
        click_pos = self.GetInteractor().GetEventPosition()
        self._set_pivot(click_pos)
        self._show_pivot_sphere()
        self.last_pos = click_pos
        super().OnRightButtonDown()

    def _left_button_release_event(self, obj: Any, event: Any) -> None:
        self.left_down = False
        if not self.right_down:
            self._hide_pivot_sphere()
        super().OnLeftButtonUp()

    def _right_button_release_event(self, obj: Any, event: Any) -> None:
        self.right_down = False
        if not self.left_down:
            self._hide_pivot_sphere()
        super().OnMiddleButtonUp()

    def _middle_button_release_event(self, obj: Any, event: Any) -> None:
        self._hide_pivot_sphere()
        super().OnRightButtonUp()

    def _mousewheel_forward_event(self, obj: Any, event: Any) -> None:
        event_pos = self.GetInteractor().GetEventPosition()
        self.FindPokedRenderer(event_pos[0], event_pos[1])
        ret = self._set_pivot(event_pos)
        if ret != 0:
            camera = self.GetCurrentRenderer().GetActiveCamera()
            self.StartDolly()
            delta = self.GetMotionFactor() * -0.005 * self.GetMouseWheelMotionFactor()
            if camera.GetParallelProjection():
                camera.SetParallelScale(camera.GetParallelScale / delta)
            else:
                self._dolly_camera(delta)
            self.EndDolly()

    def _mousewheel_backward_event(self, obj: Any, event: Any) -> None:
        event_pos = self.GetInteractor().GetEventPosition()
        self.FindPokedRenderer(event_pos[0], event_pos[1])
        ret = self._set_pivot(event_pos)
        if ret != 0:
            camera = self.GetCurrentRenderer().GetActiveCamera()
            self.StartDolly()
            delta = self.GetMotionFactor() * 0.005 * self.GetMouseWheelMotionFactor()
            if camera.GetParallelProjection():
                camera.SetParallelScale(camera.GetParallelScale / delta)
            else:
                self._dolly_camera(delta)
            self.EndDolly()

    def _mouse_move_event(self, obj: Any, event: Any) -> None:
        interactor = self.GetInteractor()
        event_pos = interactor.GetEventPosition()
        self.FindPokedRenderer(event_pos[0], event_pos[1])

        if self.GetState() == 1:
            # custom rotation
            self._rotate()
        elif self.GetState() == 2:
            self._pan()
        elif self.GetState() == 3:
            # custom spin
            self._spin()
        elif self.GetState() == 4:
            self._dolly()
        else:
            super().OnMouseMove()

        # rescale the pivot sphere upon each mouse move so it is always the same size on screen
        self._scale_pivot_sphere()
        self.last_pos = event_pos
        self.GetInteractor().Render()

    def _normalize_mouse(self, coord: tuple[int, int]) -> None:
        size = self.GetInteractor().GetRenderWindow().GetSize()
        return -1.0 + 2.0 * coord[0] / size[0], -1.0 + 2.0 * coord[1] / size[1]

    def _get_right_v_and_up_v(self, pivot: ArrayLike, camera: pv.Camera) -> tuple[float, float]:
        cam_pos = np.array(camera.GetPosition())
        pivot = np.asarray(pivot)
        vector_to_pivot = pivot - cam_pos

        if self.translation_plane_normal is None:
            view_plane_normal = _normalize(camera.GetViewPlaneNormal())
        else:
            view_plane_normal = _normalize(self.translation_plane_normal)

        l = -np.dot(vector_to_pivot, view_plane_normal)
        view_angle = camera.GetViewAngle() * np.pi / 180

        size = self.GetInteractor().GetRenderWindow().GetSize()
        scalex = size[0] / size[1] * ((2 * l * np.tan(view_angle / 2)) / 2)
        scaley = ((2 * l * np.tan(view_angle / 2)) / 2)

        view_up = camera.GetViewUp()
        right_v = _normalize(np.cross(view_up, view_plane_normal)) * scalex
        up_v = _normalize(np.cross(view_plane_normal, right_v)) * scaley

        return right_v, up_v

    def _translate_camera(self, translation: ArrayLike) -> None:
        camera = self.GetCurrentRenderer().GetActiveCamera()
        cam_pos = np.asarray(camera.GetPosition())
        cam_focal = np.asarray(camera.GetFocalPoint())

        cam_pos_new = cam_pos + translation
        cam_focal_new = cam_focal + translation

        camera.SetPosition(cam_pos_new)
        camera.SetFocalPoint(cam_focal_new)

        if self.GetAutoAdjustCameraClippingRange():
            self.GetCurrentRenderer().ResetCameraClippingRange()

        if self.GetInteractor().GetLightFollowCamera():
            self.GetCurrentRenderer().UpdateLightsGeometryToFollowCamera()

    def _rotate_camera(self, point: ArrayLike, azimuth: float, elevation: float) -> None:
        camera = self.GetCurrentRenderer().GetActiveCamera()
        focal_point = camera.GetFocalPoint()
        view_up = camera.GetViewUp()
        position = camera.GetPosition()

        axis = [0, 0, 0]
        axis[0] = -1 * camera.GetViewTransformMatrix().GetElement(0,0)
        axis[1] = -1 * camera.GetViewTransformMatrix().GetElement(0,1)
        axis[2] = -1 * camera.GetViewTransformMatrix().GetElement(0,2)

        transform = vtkTransform()
        transform.Identity()
        transform.Translate(*point)
        transform.RotateWXYZ(azimuth, view_up)
        transform.RotateWXYZ(elevation, axis)
        transform.Translate(*[-1*x for x in point])

        new_position = transform.TransformPoint(position)
        new_focal_point = transform.TransformPoint(focal_point)

        camera.SetPosition(new_position)
        camera.SetFocalPoint(new_focal_point)

        camera.OrthogonalizeViewUp()

        if self.GetAutoAdjustCameraClippingRange():
            self.GetCurrentRenderer().ResetCameraClippingRange()

        if self.GetInteractor().GetLightFollowCamera():
            self.GetCurrentRenderer().UpdateLightsGeometryToFollowCamera()

    def _pan(self) -> None:
        event_pos = self.GetInteractor().GetEventPosition()
        event_pos_normalized = self._normalize_mouse(event_pos)
        last_pos_normalized = self._normalize_mouse(self.last_pos)

        deltax = event_pos_normalized[0] - last_pos_normalized[0]
        deltay = event_pos_normalized[1] - last_pos_normalized[1]

        camera = self.GetCurrentRenderer().GetActiveCamera()

        right_v, up_v = self._get_right_v_and_up_v(self.pivot, camera)
        offset_v = (-deltax * right_v + (-deltay * up_v))

        self._translate_camera(offset_v)

    def _rotate(self) -> None:
        interactor = self.GetInteractor()
        dx = interactor.GetEventPosition()[0] - interactor.GetLastEventPosition()[0]
        dy = interactor.GetEventPosition()[1] - interactor.GetLastEventPosition()[1]
        size = self.GetCurrentRenderer().GetRenderWindow().GetSize()

        delta_elevation = -20.0 / size[1]
        delta_azimuth = -20.0 / size[0]

        rxf = dx * delta_azimuth * self.GetMotionFactor()
        ryf = dy * delta_elevation * self.GetMotionFactor()

        self._rotate_camera(self.pivot, rxf, ryf)

    def _dolly_camera(self, delta: float) -> None:
        camera = self.GetCurrentRenderer().GetActiveCamera()
        cam_pos = np.array(camera.GetPosition())

        move = np.asarray(self.pivot) - cam_pos
        offset = move * delta * -4
        self._translate_camera(offset)

        if self.GetAutoAdjustCameraClippingRange():
            self.GetCurrentRenderer().ResetCameraClippingRange()

        if self.GetInteractor().GetLightFollowCamera():
            self.GetCurrentRenderer().UpdateLightsGeometryToFollowCamera()

    def _dolly(self) -> None:
        event_pos = self.GetInteractor().GetEventPosition()
        event_pos_normalized = self._normalize_mouse(event_pos)
        last_pos_normalized = self._normalize_mouse(self.last_pos)

        delta = event_pos_normalized[1] - last_pos_normalized[1]
        self._dolly_camera(delta)

    def _spin(self) -> None:
        center = self.GetCurrentRenderer().GetCenter()
        pivot = self.pivot
        event_pos = self.GetInteractor().GetEventPosition()
        last_event_pos = self.last_pos

        new_angle = np.degrees(np.arctan2(event_pos[1] - center[1], event_pos[0]-center[0]))

        old_angle = np.degrees(np.arctan2(last_event_pos[1] - center[1], last_event_pos[0] - center[0]))

        camera = self.GetCurrentRenderer().GetActiveCamera()

        # transform = vtk.vtkTransform()
        # transform.Identity()
        # transform.Translate(*pivot)
        # transform.RotateWXYZ(new_angle - old_angle, camera.GetDirectionOfProjection())
        #
        # position = camera.GetPosition()
        # focal_point = camera.GetFocalPoint()
        # new_position = transform.TransformPoint(position)
        # new_focal_point = transform.TransformPoint(focal_point)
        #
        # camera.SetPosition(new_position)
        # camera.SetFocalPoint(new_focal_point)

        camera.Roll(new_angle - old_angle)
        camera.OrthogonalizeViewUp()

    def remove_observers(self) -> None:
        for obs in self._observers:
            self.RemoveObserver(obs)











