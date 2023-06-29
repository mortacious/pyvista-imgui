from .texture_render_window import VTKOpenGLTextureRenderWindow
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkRenderWindowInteractor

import enum
from abc import ABC, abstractmethod
from weakref import WeakValueDictionary

import typing as typ

__all__ = ['VTKImguiRenderWindowInteractor', 'RendererBackend', 'register_backend']


class RendererBackend(object):
    _backends = WeakValueDictionary()
    def __init__(self, 
                 interactor: vtkRenderWindowInteractor, 
                 render_window: vtkRenderWindow,
                 border = False) -> None:
        self.interactor = interactor
        self.render_window = render_window
        self.border = border

    @abstractmethod
    def render(self, size: typ.Optional[tuple[int, int]] = None):
        pass

    @abstractmethod
    def process_events(self):
        pass

    @abstractmethod
    def show(title: typ.Optional[str] = None, 
             window_size: tuple[int, int] = (1400, 1080)):
        pass

    @classmethod
    def _register(cls, clss, name):
        cls._backends[name] = clss

    @classmethod
    def from_name(cls, name, interactor, render_window, border=False):
        return cls._backends[name](interactor, render_window, border=border)
        

def register_backend(name) -> typ.Callable:
    def _backend_decoractor(backend_cls: typ.Type[RendererBackend]) -> typ.Type[RendererBackend]:
        assert issubclass(backend_cls, RendererBackend)
        RendererBackend._register(backend_cls, name)
        return backend_cls
    return _backend_decoractor


class VTKImguiRenderWindowInteractor(object):
    """
    A RenderWindowInteractor to integrate VTK's rendering within an existing imgui ui.
    It uses the VTKOpenGLTextureRenderWindow to render VTK's output into an openGl-texture,
    which is displayed as an image within imgui.

    All interaction events are passed to the underlying interactor to be handled, so all
    mouse interactions are the same as in regular VTK.

    Parameters
    ----------
    border, optional
        display a border around the created imgui widget, by default False
    """
    def __init__(self, 
                 border: bool = False,
                 backend = None) -> None:
        if backend is None:
            backend = 'imgui_bundle'

        self.renwin = VTKOpenGLTextureRenderWindow(viewport_size=(0, 0))

        self.interactor = vtkGenericRenderWindowInteractor()

        self.imgui_backend = RendererBackend.from_name(backend, self.interactor, self.renwin)

        # do not render unless explicitly requested, as imgui has control over the event loop
        self.interactor.EnableRenderOff()
        self.renwin.SetInteractor(self.interactor)

    def close(self):
        self.renwin.close()
    
    def __getattr__(self, attr):
        """
        Makes the object behave like a vtkRenderWindowInteractor
        """
        if attr == '__vtk__':
            return lambda t=self.interactor: t
        elif hasattr(self.interactor, attr):
            return getattr(self.interactor, attr)
        else:
            raise AttributeError(self.__class__.__name__ +
                  " has no attribute named " + attr)


    def render(self, size: typ.Optional[tuple[int, int]] = None) -> None:
        """
        Renders the contents of the internal render window into an existing imgui ui 
        with the specified size. This method should be called when building 
        and updating the ui.

        Parameters
        ----------
        size, optional
            the size of the result in the ui in pixels, 
            if None (default) the maximum available size is used.
        """
        self.imgui_backend.render(size)

    def process_events(self) -> None:
        """
        Handle events by passing them to the underlying vtk interactor. This method is called automatically
        on rendering.
        """
        self.imgui_backend.process_events()

