from vtkmodules.vtkRenderingOpenGL2 import vtkGenericOpenGLRenderWindow, vtkTextureObject
from vtkmodules.vtkCommonCore import VTK_UNSIGNED_CHAR
import typing as typ


__all__ = ['VTKOpenGLTextureRenderWindow']


class VTKOpenGLTextureRenderWindow(object):
    """
    Class to render the output of one or multiple vtk renderers into an opengl texture object. The texture can be retrieved for use in other visualization packages based on opengl.
    """
    def __init__(self) -> None:
        """
        A specialization of a vtkRenderWindow that renders itself into an opengl texture 
        when calling the 'render' method. 
        The resulting texture an be retrieved for use in external visualization packages based on opengl.

        The size of the resulting texture can be resized dynamically upon calling 'render'
        """
  
        self._tex = None
        self._renderers = []

        self._texture_size = (0, 0)

        self.render_window = vtkGenericOpenGLRenderWindow()
        self.render_window.SetIsCurrent(True)
 
    @property
    def texture_id(self) -> typ.Optional[int]:
        """
        Returns the texture id of the rendererd texture. 
        If nothing has been rendererd yet, None is returned instead.
        """
        if self._tex is None:
            return None # no texture has been created yet
        return self._tex.GetHandle()
    
    @property
    def size(self) -> tuple[int, int]:
        return self.render_window.GetSize()
    
    @size.setter
    def size(self, size: tuple[int, int]) -> None:
        self.render_window.SetSize(int(size[0]), int(size[1]))

    def render(self) -> None:
        """ 
        Renders the vtk output into a texture of appropriate size.
        """
        self.set_viewport_size(self.size)

        vtk_fbo = self.render_window.GetDisplayFramebuffer()
        vtk_fbo.SetContext(self.render_window)
        vtk_fbo.SaveCurrentBindingsAndBuffers()
        vtk_fbo.Bind()
        vtk_fbo.AddColorAttachment(0, self._tex)
        vtk_fbo.AddDepthAttachment()
        vtk_fbo.ActivateBuffer(0)

        self.render_window.Render()
        #self.render_window.WaitForCompletion()

        vtk_fbo.RestorePreviousBindingsAndBuffers()

    def __getattr__(self, attr):
        """
        Makes the object behave like a vtkRenderWindow
        """
        if attr == '__vtk__':
            return lambda t=self.render_window: t
        elif hasattr(self.render_window, attr):
            return getattr(self.render_window, attr)
        else:
            raise AttributeError(self.__class__.__name__ +
                  " has no attribute named " + attr)
        
    def set_viewport_size(self, new_size: tuple[int, int]) -> None:
        """
        Sets the internal texture size in pixels. If the new size is different from
        the current size, a new texture is allocated.

        Parameters
        ----------
        new_size
            the new size of the viewport
        """

        # init the internal render window to use the current (texture) context
        # create a texture object to render into
        if self._tex is None:
            # init the opengl context here
            self.render_window.OpenGLInitContext()
            self.render_window.OpenGLInitState()
            self.render_window.MakeCurrent()

            # setup color texture
            self._tex = vtkTextureObject()
            self._tex.SetContext(self.render_window)

            # allocate the texture object using the initial size
            self._tex.Create2D(new_size[0], new_size[1], 4, VTK_UNSIGNED_CHAR, False)
            self._tex.SetWrapS(vtkTextureObject.ClampToEdge)
            self._tex.SetWrapT(vtkTextureObject.ClampToEdge)
            self._tex.SetMinificationFilter(vtkTextureObject.Linear)
            self._tex.SetLinearMagnification(True)
            self._tex.Bind()
            self._tex.SendParameters()

        current_size = self.size
        # if nothing has changed just return
        if current_size == new_size or any(s <= 0 for s in new_size):
            return
        
        self.size = new_size
        self._tex.Resize(new_size[0], new_size[1])
