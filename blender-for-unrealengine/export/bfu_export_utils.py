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

if "bpy" in locals():
    import importlib
    if "bfu_write_text" in locals():
        importlib.reload(bfu_write_text)
    if "bfu_basics" in locals():
        importlib.reload(bfu_basics)
    if "bfu_utils" in locals():
        importlib.reload(bfu_utils)
    if "bfu_export_get_info" in locals():
        importlib.reload(bfu_export_get_info)

from .. import bfu_write_text
from .. import bfu_basics
from ..bfu_basics import *
from .. import bfu_utils
from ..bfu_utils import *
from ..bbpl import utils

from . import bfu_export_get_info
from .bfu_export_get_info import *

dup_temp_name = "BFU_Temp"  # DuplicateTemporarilyNameForUe4Export
Export_temp_preFix = "_ESO_Temp"  # _ExportSubObject_TempName


def GetExportFullpath(dirpath, filename):
    absdirpath = bpy.path.abspath(dirpath)
    VerifiDirs(absdirpath)
    return os.path.join(absdirpath, filename)


def ApplyProxyData(obj):

    # Apply proxy data if needed.
    if GetExportProxyChild(obj) is None:
        return
    def ReasignProxySkeleton(newArmature, oldArmature):
        for select in bpy.context.selected_objects:
            if select.type == "CURVE":
                for mod in select.modifiers:
                    if mod.type == "HOOK" and mod.object == oldArmature:
                        matrix_inverse = mod.matrix_inverse.copy()
                        mod.object = newArmature
                        mod.matrix_inverse = matrix_inverse

            else:
                for mod in select.modifiers:
                    if mod.type == 'ARMATURE' and mod.object == oldArmature:
                        mod.object = newArmature

        for bone in newArmature.pose.bones:
            for cons in bone.constraints:
                if hasattr(cons, 'target'):
                    if cons.target == oldArmature:
                        cons.target = newArmature
                    else:
                        ChildProxyName = (
                            cons.target.name +
                            "_UEProxyChild"
                        )
                        if ChildProxyName in bpy.data.objects:
                            cons.target = bpy.data.objects[ChildProxyName]

    # Get old armature in selected objects
    OldProxyChildArmature = None
    for selectedObj in bpy.context.selected_objects:
        if selectedObj != obj and selectedObj.type == "ARMATURE":
            OldProxyChildArmature = selectedObj

    # Reasing parent + add to remove
    if OldProxyChildArmature is not None:
        ToRemove = []
        ToRemove.append(OldProxyChildArmature)
        for selectedObj in bpy.context.selected_objects:
            if selectedObj != obj:
                if selectedObj.parent == OldProxyChildArmature:
                    # Reasing parent and keep position
                    SavedPos = selectedObj.matrix_world.copy()
                    selectedObj.name += "_UEProxyChild"
                    selectedObj.parent = obj
                    selectedObj.matrix_world = SavedPos
                else:
                    ToRemove.append(selectedObj)
        ReasignProxySkeleton(obj, OldProxyChildArmature)
        SavedSelect = GetCurrentSelection()
        RemovedObjects = CleanDeleteObjects(ToRemove)
        SavedSelect.RemoveFromListByName(RemovedObjects)
        SetCurrentSelection(SavedSelect)


def BakeArmatureAnimation(armature, frame_start, frame_end):
    # Change to pose mode
    SavedSelect = GetCurrentSelection()
    bpy.ops.object.select_all(action='DESELECT')
    SelectSpecificObject(armature)
    bpy.ops.nla.bake(
        frame_start=frame_start-10,
        frame_end=frame_end+10,
        only_selected=False,
        visual_keying=True,
        clear_constraints=True,
        use_current_action=False,
        bake_types={'POSE'}
        )
    bpy.ops.object.select_all(action='DESELECT')
    SetCurrentSelection(SavedSelect)


def DuplicateSelectForExport(new_name="duplicated Obj"):
    # Note: Need look for a optimized duplicate, This is too long

    scene = bpy.context.scene

    class DuplicateData():
        def __init__(self):
            self.data_to_remove = []
            self.origin_select = None
            self.duplicate_select = None

        def SetOriginSelect(self):
            select = bbpl.utils.UserSelectSave()
            select.SaveCurrentSelect()
            self.origin_select = select

        def SetDuplicateSelect(self):
            select = bbpl.utils.UserSelectSave()
            select.SaveCurrentSelect()
            self.duplicate_select = select

    class DelegateOldData():
        # contain a data to remove and function for remove

        def __init__(self, data_name, data_type):
            self.data_name = data_name
            self.data_type = data_type

        def RemoveData(self):
            RemoveUselessSpecificData(self.data_name, self.data_type)

    duplicate_data = DuplicateData()
    duplicate_data.SetOriginSelect()
    for user_selected in duplicate_data.origin_select.user_selecteds:
        if user_selected:
            SaveObjCurrentName(user_selected)
            if user_selected.type == "ARMATURE":
                SetObjProxyData(user_selected)

    data_to_remove = []

    actionNames = [action.name for action in bpy.data.actions]
    bpy.ops.object.duplicate()

    currentSelectNames = [
        currentSelectName.name
        for currentSelectName in bpy.context.selected_objects
    ]
    for objSelect in currentSelectNames:
        if objSelect not in bpy.context.selected_objects:
            bpy.data.objects[objSelect].select_set(True)

    # Make sigle user and clean useless data.
    for objScene in bpy.context.selected_objects:
        if objScene.data is not None:
            oldData = objScene.data.name
            objScene.data = objScene.data.copy()
            data_to_remove.append(DelegateOldData(oldData, objScene.type))

    # Clean create actions by duplication
    for action in bpy.data.actions:
        if action.name not in actionNames:
            bpy.data.actions.remove(action)

    duplicate_data.SetDuplicateSelect()

    return duplicate_data


def SetDuplicateNameForExport(duplicate_data, origin_prefix="or_"):
    for user_selected in duplicate_data.origin_select.user_selecteds:
        user_selected.name = origin_prefix+user_selected.name

    for user_selected in duplicate_data.duplicate_select.user_selecteds:
        user_selected.name = GetObjOriginName(user_selected)


def ResetDuplicateNameAfterExport(duplicate_data):
    for user_selected in duplicate_data.origin_select.user_selecteds:
        user_selected.name = GetObjOriginName(user_selected)
        ClearObjOriginNameVar(user_selected)


def MakeSelectVisualReal():
    select = bbpl.utils.UserSelectSave()
    select.SaveCurrentSelect()

    previous_objects = list(bpy.data.objects)
    # Visual Transform Apply
    bpy.ops.object.visual_transform_apply()

    # Make Instances Real
    bpy.ops.object.duplicates_make_real(
        use_base_parent=True,
        use_hierarchy=True
        )

    select.ResetSelectByName()

    # Select the new objects
    for obj in bpy.data.objects:
        if obj not in previous_objects:
            obj.select_set(True)

# Sockets


def SetSocketsExportName(obj):
    '''
    Try to apply the custom SocketName
    '''

    scene = bpy.context.scene
    for socket in GetSocketDesiredChild(obj):
        if socket.bfu_use_socket_custom_Name:
            if socket.bfu_socket_custom_Name in scene.objects:
                print(
                    'Can\'t rename socket "' +
                    socket.name +
                    '" to "'+socket.bfu_socket_custom_Name +
                    '".'
                    )
            else:
                # Save the previous name
                socket["BFU_PreviousSocketName"] = socket.name
                socket.name = f"SOCKET_{socket.bfu_socket_custom_Name}"


def SetSocketsExportTransform(obj):
    # Set socket Transform for Unreal

    addon_prefs = GetAddonPrefs()
    for socket in GetSocketDesiredChild(obj):
        socket["BFU_PreviousSocketScale"] = socket.scale
        socket["BFU_PreviousSocketLocation"] = socket.location
        socket["BFU_PreviousSocketRotationEuler"] = socket.rotation_euler
        if GetShouldRescaleSocket():
            socket.delta_scale *= GetRescaleSocketFactor()

        if addon_prefs.staticSocketsAdd90X:
            savedScale = socket.scale.copy()
            savedLocation = socket.location.copy()
            AddMat = mathutils.Matrix.Rotation(math.radians(90.0), 4, 'X')
            socket.matrix_world = socket.matrix_world @ AddMat
            socket.scale.x = savedScale.x
            socket.scale.z = savedScale.y
            socket.scale.y = savedScale.z
            socket.location = savedLocation


def ResetSocketsExportName(obj):
    # Reset socket Name

    scene = bpy.context.scene
    for socket in GetSocketDesiredChild(obj):
        if "BFU_PreviousSocketName" in socket:
            socket.name = socket["BFU_PreviousSocketName"]
            del socket["BFU_PreviousSocketName"]


def ResetSocketsTransform(obj):
    # Reset socket Transform

    scene = bpy.context.scene
    for socket in GetSocketDesiredChild(obj):
        if "BFU_PreviousSocketScale" in socket:
            socket.scale = socket["BFU_PreviousSocketScale"]
            del socket["BFU_PreviousSocketScale"]
        if "BFU_PreviousSocketLocation" in socket:
            socket.location = socket["BFU_PreviousSocketLocation"]
            del socket["BFU_PreviousSocketLocation"]
        if "BFU_PreviousSocketRotationEuler" in socket:
            socket.rotation_euler = socket["BFU_PreviousSocketRotationEuler"]
            del socket["BFU_PreviousSocketRotationEuler"]


# Main asset


class PrepareExportName():
    def __init__(self, obj, is_armature):
        # Rename temporarily the assets
        if obj:

            self.target_object = obj
            self.is_armature = is_armature
            self.old_asset_name = ""
            self.new_asset_name = ""

            scene = bpy.context.scene
            if self.is_armature:
                self.new_asset_name = GetDesiredExportArmatureName(obj)
            else:
                self.new_asset_name = obj.name  # Keep the same name

    def SetExportName(self):

        '''
        Set the name of the asset for export
        '''

        obj = self.target_object
        if obj.name != self.new_asset_name:
            self.old_asset_name = obj.name
            scene = bpy.context.scene
            # Avoid same name for two assets
            if self.new_asset_name in scene.objects:
                confli_asset = scene.objects[self.new_asset_name]
                confli_asset.name = dup_temp_name
            obj.name = self.new_asset_name

    def ResetNames(self):
        '''
        Reset names after export
        '''

        if self.old_asset_name != "":
            obj = self.target_object
            obj.name = self.old_asset_name

            scene = bpy.context.scene
            if dup_temp_name in scene.objects:
                armature = scene.objects[dup_temp_name]
                armature.name = self.new_asset_name

# UVs


def ConvertGeometryNodeAttributeToUV(obj):
    # obj = bpy.context.active_object  # Debug
    if not obj.convert_geometry_node_attribute_to_uv:
        return
    attrib_name = obj.convert_geometry_node_attribute_to_uv_name

        # I need apply the geometry modifier for get the data.
        # So this work only when I do export of the duplicate object.

    if hasattr(obj.data, "attributes") and attrib_name in obj.data.attributes:
        # TO DO: Bad why to do this. Need found a way to convert without using ops.
        obj.data.attributes.active = obj.data.attributes[attrib_name]

        # Because a bug Blender set the wrong attribute as active in 3.5.
        if obj.data.attributes.active != obj.data.attributes[attrib_name]:
            for x, attribute in enumerate(obj.data.attributes):
                if attribute.name == attrib_name:
                    obj.data.attributes.active_index = x

        SavedSelect = GetCurrentSelection()
        SelectSpecificObject(obj)
        if obj.data.attributes.active:
            if bpy.app.version >= (3, 5, 0):
                bpy.ops.geometry.attribute_convert(mode='GENERIC', domain='CORNER', data_type='FLOAT2')
            else:
                bpy.ops.geometry.attribute_convert(mode='UV_MAP', domain='CORNER', data_type='FLOAT2')
        SetCurrentSelection(SavedSelect)
        return


def CorrectExtremUVAtExport(obj):
    if obj.correct_extrem_uv_scale:
        SavedSelect = GetCurrentSelection()
        if GoToMeshEditMode():
            CorrectExtremeUV(2)
            bbpl.utils.SafeModeSet('OBJECT')
            SetCurrentSelection(SavedSelect)
            return True
    return False

# Armature


def ConvertArmatureConstraintToModifiers(armature):
    for obj in GetExportDesiredChilds(armature):
        previous_enabled_armature_constraints = []

        for const in obj.constraints:
            if const.type == "ARMATURE" and const.enabled is True:
                previous_enabled_armature_constraints.append(const.name)

                # Disable constraint
                const.enabled = False

                # Remove All Vertex Group
                # TO DO:

                # Add Vertex Group
                for target in const.targets:
                    bone_name = target.subtarget
                    group = obj.vertex_groups.new(name=bone_name)

                    vertex_indices = range(0, len(obj.data.vertices))
                    group.add(vertex_indices, 1.0, 'REPLACE')

                    # Add armature modifier
                mod = obj.modifiers.new(f"BFU_Const_{const.name}", "ARMATURE")
                mod.object = armature

        # Save data for reset after export
        obj["BFU_PreviousEnabledArmatureConstraints"] = previous_enabled_armature_constraints


def ResetArmatureConstraintToModifiers(armature):
    for obj in GetExportDesiredChilds(armature):
        if "BFU_PreviousEnabledArmatureConstraints" in obj:
            for const_names in obj["BFU_PreviousEnabledArmatureConstraints"]:
                const = obj.constraints[const_names]

                # Remove created armature for export
                mod = obj.modifiers[f"BFU_Const_{const_names}"]
                obj.modifiers.remove(mod)

                # Remove created Vertex Group
                for target in const.targets:
                    bone_name = target.subtarget
                    old_vertex_group = obj.vertex_groups[bone_name]
                    obj.vertex_groups.remove(old_vertex_group)

                # Enable back constraint
                const.enabled = True

# Vertex Color


def SetVertexColorForUnrealExport(parent):

    objs = GetExportDesiredChilds(parent)
    objs.append(parent)

    for obj in objs:
        if obj.type == "MESH":
            vced = VertexColorExportData(obj, parent)
            if vced.export_type == "REPLACE":

                vertex_colors = utils.getVertexColors(obj)

                # Save the previous target
                obj.data["BFU_PreviousTargetIndex"] = vertex_colors.active_index

                # Ser the vertex color for export
                vertex_colors.active_index = vced.index


def ClearVertexColorForUnrealExport(parent):

    objs = GetExportDesiredChilds(parent)
    objs.append(parent)
    for obj in objs:
        if obj.type == "MESH" and "BFU_PreviousTargetIndex" in obj.data:
            del obj.data["BFU_PreviousTargetIndex"]


def GetShouldRescaleRig(obj):
    # This will return if the rig should be rescale.

    if obj.bfu_export_procedure == "auto-rig-pro":
        return False

    addon_prefs = GetAddonPrefs()
    if addon_prefs.rescaleFullRigAtExport == "auto":

        return not math.isclose(
            bpy.context.scene.unit_settings.scale_length,
            0.01,
            rel_tol=1e-5,
        )
    return addon_prefs.rescaleFullRigAtExport == "custom_rescale"


def GetRescaleRigFactor():
    # This will return the rescale factor.

    addon_prefs = GetAddonPrefs()
    if addon_prefs.rescaleFullRigAtExport == "auto":
        return 100 * bpy.context.scene.unit_settings.scale_length
    else:
        return addon_prefs.newRigScale  # rigRescaleFactor


def GetShouldRescaleSocket():
    # This will return if the socket should be rescale.

    addon_prefs = GetAddonPrefs()
    if addon_prefs.rescaleSocketsAtExport == "auto":
        return bpy.context.scene.unit_settings.scale_length != 0.01
    return addon_prefs.rescaleSocketsAtExport == "custom_rescale"


def GetRescaleSocketFactor():
    # This will return the rescale factor.

    addon_prefs = GetAddonPrefs()
    if addon_prefs.rescaleSocketsAtExport == "auto":
        return 1/(100*bpy.context.scene.unit_settings.scale_length)
    else:
        return addon_prefs.staticSocketsImportedSize


def ExportAutoProRig(
        filepath,
        use_selection=True,
        export_rig_name="root",
        bake_anim=True,
        anim_export_name_string="",
        mesh_smooth_type="OFF",
        arp_simplify_fac=0.0
        ):

    bpy.context.scene.arp_engine_type = 'unreal'
    bpy.context.scene.arp_export_rig_type = 'mped'  # types: 'humanoid', 'mped'
    bpy.context.scene.arp_ge_sel_only = use_selection

    # Rig
    bpy.context.scene.arp_export_twist = False
    bpy.context.scene.arp_export_noparent = False
    bpy.context.scene.arp_units_x100 = True
    bpy.context.scene.arp_ue_root_motion = True

    # Anim
    bpy.context.scene.arp_bake_actions = bake_anim
    bpy.context.scene.arp_export_name_actions = True
    bpy.context.scene.arp_export_name_string = anim_export_name_string
    bpy.context.scene.arp_simplify_fac = arp_simplify_fac

    # Misc
    bpy.context.scene.arp_mesh_smooth_type = mesh_smooth_type
    bpy.context.scene.arp_use_tspace = False
    bpy.context.scene.arp_fix_fbx_matrix = False
    bpy.context.scene.arp_fix_fbx_rot = False
    bpy.context.scene.arp_init_fbx_rot = False
    bpy.context.scene.arp_bone_axis_primary_export = 'Y'
    bpy.context.scene.arp_bone_axis_secondary_export = 'X'
    bpy.context.scene.arp_export_rig_name = export_rig_name

    # export it
    print("Start AutoProRig Export")
    bpy.ops.id.arp_export_fbx_panel(filepath=filepath)


def ExportSingleAdditionalTrackCamera(dirpath, filename, obj):
    # Export additional camera track for ue4
    # FocalLength
    # FocusDistance
    # Aperture

    absdirpath = bpy.path.abspath(dirpath)
    VerifiDirs(absdirpath)
    AdditionalTrack = bfu_write_text.WriteCameraAnimationTracks(obj)
    return bfu_write_text.ExportSingleJson(
        AdditionalTrack,
        absdirpath,
        filename
        )


def ExportAdditionalParameter(dirpath, unreal_exported_asset):
    # Export additional parameter from static and skeletal mesh track for ue4
    # SocketsList

    filename = unreal_exported_asset.GetFilename("_AdditionalTrack.json")

    absdirpath = bpy.path.abspath(dirpath)
    VerifiDirs(absdirpath)
    AdditionalTrack = bfu_write_text.WriteSingleMeshAdditionalParameter(unreal_exported_asset)
    return bfu_write_text.ExportSingleJson(
        AdditionalTrack,
        absdirpath,
        filename
        )
