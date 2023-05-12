# ====================== BEGIN GPL LICENSE BLOCK ============================
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.	 If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#
# ======================= END GPL LICENSE BLOCK =============================


import bpy
import time
import math

from .. import bfu_write_text
from .. import bfu_basics
from ..bfu_basics import *
from .. import bfu_utils
from ..bfu_utils import *
from enum import Enum

from ..bbpl import utils

import importlib
if "bfu_write_text" in locals():
    importlib.reload(bfu_write_text)
if "bfu_basics" in locals():
    importlib.reload(bfu_basics)
if "bfu_utils" in locals():
    importlib.reload(bfu_utils)


class VertexColorExportData:
    def __init__(self, obj, parent=None):
        self.obj = obj
        self.parent = parent
        self.export_type = "IGNORE"
        self.name = ""
        self.color = (1.0, 1.0, 1.0)
        self.index = -1

        if self.GetPropertyOwner():
            if self.GetPropertyOwner().VertexColorImportOption == "IGNORE":
                self.export_type = "IGNORE"

            elif self.GetPropertyOwner().VertexColorImportOption == "OVERRIDE":
                self.color = self.GetPropertyOwner().VertexOverrideColor
                self.export_type = "OVERRIDE"

            elif self.GetPropertyOwner().VertexColorImportOption == "REPLACE":
                index = self.GetChosenVertexIndex()
                print(index)
                if index != -1:
                    self.index = index
                    self.name = self.GetChosenVertexName()
                    self.export_type = "REPLACE"

    def GetPropertyOwner(self):
        # Return the object to use for the property or return self if none
        return self.parent if self.parent else self.obj

    def GetChosenVertexIndex(self):

        obj = self.obj
        if obj.type != "MESH":
            return -1

        VertexColorToUse = self.GetPropertyOwner().VertexColorToUse
        VertexColorIndexToUse = self.GetPropertyOwner().VertexColorIndexToUse

        if obj and obj.data:
            vertex_colors = utils.getVertexColors(obj)
            if len(vertex_colors) > 0:

                if VertexColorToUse == "FirstIndex":
                    return 0

                if VertexColorToUse == "LastIndex":
                    return len(vertex_colors)-1

                if VertexColorToUse == "ActiveIndex":
                    return utils.getVertexColors_RenderColorIndex(obj)

                if (
                    VertexColorToUse == "CustomIndex"
                    and VertexColorIndexToUse < len(vertex_colors)
                ):
                    return VertexColorIndexToUse
        return -1

    def GetChosenVertexName(self):

        index = self.GetChosenVertexIndex()
        if index == -1:
            return "None"

        if obj := self.obj:
            if obj.type == "MESH" and obj.data:
                vertex_colors = utils.getVertexColors(obj)
                if obj.VertexColorIndexToUse < len(vertex_colors):
                    return vertex_colors[index].name

        return "None"

    def GetVertexByIndex(self, index):
        self.obj
