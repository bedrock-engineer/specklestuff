"""Speckle's web viewer in a notebook, fed with Speckle objects instead of a server."""

from specklewidgets.models import models_gz
from specklewidgets.speckle_viewer import Marker, SpeckleViewer

__all__ = ["Marker", "SpeckleViewer", "models_gz"]
