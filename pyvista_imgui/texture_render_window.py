# This class is a port of the integration done in the imgui-vtk library (https://github.com/trlsmax/imgui-vtk) 
# which is available under the folloing license:

# MIT License

# Copyright (c) 2023 imgui-vtk Contributors

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from vtkmodules.vtkRenderingOpenGL2 import vtkGenericOpenGLRenderWindow
from OpenGL.GL import *
import typing as typ


__all__ = ['VTKOpenGLTextureRenderWindow']


class VTKOpenGLTextureRenderWindow(object):
    """
    Class to render the output of one or multiple vtk renderers into an opengl texture object. The texture can be retrieved for use in other visualization packages based on opengl.
    """
    def __init__(self, 
                 viewport_size: tuple[int, int] = (0, 0)) -> None:
        """
        A specialization of a vtkRenderWindow that renders itself into an opengl texture 
        when calling the 'render' method. 
        The resulting texture an be retrieved for use in external visualization packages based on opengl.

        The size of the resulting texture can be resized dynamically upon calling 'render'
        Parameters
        ----------
        viewport_size, optional
            the default viewport size in pixels, by default (0, 0)
        """
        self._tex = 0
        self._first_render = True
        self._renderers = []

        self.viewport_size = viewport_size

        self.render_window = vtkGenericOpenGLRenderWindow()
        self.render_window.SetSize(*self.viewport_size)

        # the render window is always current as it is rendering into a texture when explicitly requested
        self.render_window.SetIsCurrent(True)
        self.render_window.SwapBuffersOn()
        self.render_window.SetOffScreenRendering(True)
        self.render_window.SetFrameBlitModeToNoBlit()

    def __del__(self) -> None:
        self.close()


    def close(self):
        if self._tex:
            try:
                glDeleteTextures(1, [self._tex])
            except:
                pass # homehow OpenGL sometimes throws errors on shutdown so just catch them here for now
        self._first_render = True
        
    @property
    def texture_id(self) -> typ.Optional[int]:
        """
        Returns the texture id of the rendererd texture. 
        If nothing has been rendererd yet, None is returned instead.
        """
        if self._first_render:
            return None # no texture has been created yet
        return self._tex

    def render(self, size: typ.Optional[tuple[int, int]] = None) -> None:
        """ 
        Renders the vtk output into a texture of given size.

        Parameters
        ----------
        size, optional
            the size of the texture. It None (default), the current size of the internal texture is used.
        """
        if size is None:
            size = self.viewport_size
        self.set_viewport_size(size)

        self.render_window.Render()
        self.render_window.WaitForCompletion()

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
        # skip if nothing has changed
        if ((self.viewport_size[0] == new_size[0] and self.viewport_size[1] == new_size[1]) or 
            new_size[0] <= 0 or new_size[1] <= 0) and not self._first_render:
            return

        self.viewport_size = new_size
        # init the internal render window to use the current (texture) context
        self.render_window.InitializeFromCurrentContext() #IMPORTANT: initialize the current opengl context before messing with the textures!
        self.render_window.SetSize(int(self.viewport_size[0]), int(self.viewport_size[1]))
        # create a texture object to render into
        if not self._first_render:
            glDeleteTextures([self._tex])
        self._tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self._tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, int(self.viewport_size[0]), 
                     int(self.viewport_size[1]), 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        
        glBindTexture(GL_TEXTURE_2D, 0)

        for renderer in self.render_window.GetRenderers():
            renderer.ResetCamera()

        # use the texture
        vtk_fbo = self.render_window.GetDisplayFramebuffer()
        vtk_fbo.Bind()
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._tex, 0)
        vtk_fbo.UnBind()

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        self._first_render = False