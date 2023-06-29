import pyvista as pv
from pyvista_imgui import ImguiPlotter
from threading import Thread
import time

sphere = pv.Sphere()

plotter = ImguiPlotter()
plotter.add_axes()
plotter.add_mesh(sphere, render=False)

done = False

def plot():
    try:
        plotter.show()
    finally:
        done = True

t = Thread(target=plot)
t.start()


while not done:
    time.sleep(0.5)
    print("sleeping")
t.join()

