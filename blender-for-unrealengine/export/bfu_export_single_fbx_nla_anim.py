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
    if "bfu_check_potential_error" in locals():
        importlib.reload(bfu_check_potential_error)
    if "bfu_export_utils" in locals():
        importlib.reload(bfu_export_utils)


from .. import bfu_write_text
from .. import bfu_basics
from ..bfu_basics import *
from .. import bfu_utils
from ..bfu_utils import *
from .. import bfu_check_potential_error

from . import bfu_export_utils
from .bfu_export_utils import *


def ProcessNLAAnimExport(obj):
    scene = bpy.context.scene
    addon_prefs = GetAddonPrefs()
    dirpath = os.path.join(GetObjExportDir(obj), scene.anim_subfolder_name)

    scene.frame_end += 1  # Why ?

    MyAsset = scene.UnrealExportedAssetsList.add()
    MyAsset.object = obj
    MyAsset.skeleton_name = obj.name
    MyAsset.asset_name = GetNLAExportFileName(obj)
    MyAsset.folder_name = obj.exportFolderName
    MyAsset.asset_type = "NlAnim"
    MyAsset.StartAssetExport()

    ExportSingleFbxNLAAnim(dirpath, GetNLAExportFileName(obj), obj)
    file = MyAsset.files.add()
    file.name = GetNLAExportFileName(obj)
    file.path = dirpath
    file.type = "FBX"

    MyAsset.EndAssetExport(True)
    return MyAsset


def ExportSingleFbxNLAAnim(
        dirpath,
        filename,
        obj
        ):

    '''
    #####################################################
            #NLA ANIMATION
    #####################################################
    '''
    # Export a single NLA Animation

    scene = bpy.context.scene
    addon_prefs = GetAddonPrefs()
    export_as_proxy = GetExportAsProxy(obj)
    export_proxy_child = GetExportProxyChild(obj)

    bbpl.utils.SafeModeSet('OBJECT')

    SelectParentAndDesiredChilds(obj)
    asset_name = PrepareExportName(obj, True)
    if export_as_proxy is False:
        duplicate_data = DuplicateSelectForExport()
        SetDuplicateNameForExport(duplicate_data)

    if export_as_proxy is False:
        MakeSelectVisualReal()

    BaseTransform = obj.matrix_world.copy()
    active = bpy.context.view_layer.objects.active
    asset_name.target_object = active

    export_procedure = active.bfu_export_procedure

    animation_data = bbpl.anim_utils.AnimationManagment()
    animation_data.SaveAnimationData(obj)
    animation_data.SetAnimationData(active, True)

    if export_as_proxy:
        ApplyProxyData(active)
        RemoveSocketFromSelectForProxyArmature()

    if addon_prefs.bakeArmatureAction:
        BakeArmatureAnimation(active, scene.frame_start, scene.frame_end)

    ApplyExportTransform(active, "NLA")  # Apply export transform before rescale

    # This will rescale the rig and unit scale to get a root bone egal to 1
    ShouldRescaleRig = GetShouldRescaleRig(active)
    if ShouldRescaleRig:

        rrf = GetRescaleRigFactor()  # rigRescaleFactor
        savedUnitLength = bpy.context.scene.unit_settings.scale_length
        bpy.context.scene.unit_settings.scale_length = 0.01  # *= 1/rrf

        oldScale = active.scale.z

        ApplySkeletalExportScale(active, rrf, target_animation_data=animation_data, is_a_proxy=export_as_proxy)
        RescaleAllActionCurve(rrf*oldScale, savedUnitLength/0.01)

        for selected in bpy.context.selected_objects:
            if selected.type == "MESH":
                RescaleShapeKeysCurve(selected, 1/rrf)

        RescaleSelectCurveHook(1/rrf)
        ResetArmaturePose(active)

        RescaleRigConsraints(active, rrf)

    scene.frame_start = GetDesiredNLAStartEndTime(active)[0]
    scene.frame_end = GetDesiredNLAStartEndTime(active)[1]

    asset_name.SetExportName()

    if export_procedure == "auto-rig-pro":
        ExportAutoProRig(
            filepath=GetExportFullpath(dirpath, filename),
            # export_rig_name=GetDesiredExportArmatureName(active),
            bake_anim=True,
            anim_export_name_string=active.animation_data.action.name,
            mesh_smooth_type="FACE",
            arp_simplify_fac=active.SimplifyAnimForExport
            )

    elif export_procedure == "normal":
        bpy.ops.export_scene.fbx(
            filepath=GetExportFullpath(dirpath, filename),
            check_existing=False,
            use_selection=True,
            global_scale=GetObjExportScale(active),
            object_types={'ARMATURE', 'EMPTY', 'MESH'},
            use_custom_props=addon_prefs.exportWithCustomProps,
            add_leaf_bones=False,
            use_armature_deform_only=active.exportDeformOnly,
            bake_anim=True,
            bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False,
            bake_anim_force_startend_keying=True,
            bake_anim_step=GetAnimSample(active),
            bake_anim_simplify_factor=active.SimplifyAnimForExport,
            use_metadata=addon_prefs.exportWithMetaData,
            primary_bone_axis=active.exportPrimaryBaneAxis,
            secondary_bone_axis=active.exporSecondaryBoneAxis,
            axis_forward=active.exportAxisForward,
            axis_up=active.exportAxisUp,
            bake_space_transform=False
            )

    ResetArmaturePose(active)
    # scene.frame_start -= active.bfu_anim_action_start_frame_offset
    # scene.frame_end -= active.bfu_anim_action_end_frame_offset

    asset_name.ResetNames()

    ResetArmaturePose(obj)

    # Reset Transform
    obj.matrix_world = BaseTransform

    # This will rescale the rig and unit scale to get a root bone egal to 1
    if ShouldRescaleRig:
        # Reset Curve an unit
        bpy.context.scene.unit_settings.scale_length = savedUnitLength
        RescaleAllActionCurve(1/(rrf*oldScale), 0.01/savedUnitLength)

    if export_as_proxy is False:
        CleanDeleteObjects(bpy.context.selected_objects)
        for data in duplicate_data.data_to_remove:
            data.RemoveData()

        ResetDuplicateNameAfterExport(duplicate_data)

    for obj in scene.objects:
        ClearAllBFUTempVars(obj)
