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


from operator import contains
import bpy
import fnmatch
import mathutils
import math
import time
import sys

if "bpy" in locals():
    import importlib
    if "bfu_basics" in locals():
        importlib.reload(bfu_basics)
    if "bfu_ui_utils" in locals():
        importlib.reload(bfu_ui_utils)

from . import bfu_basics
from .bfu_basics import *
from .bfu_utils import *
from . import bfu_ui_utils


def CorrectBadProperty(list=None):
    # Corrects bad properties

    objs = list if list is not None else GetAllCollisionAndSocketsObj()
    UpdatedProp = 0
    for obj in objs:
        if obj.ExportEnum == "export_recursive":
            obj.ExportEnum = "auto"
            UpdatedProp += 1
    return UpdatedProp


def UpdateNameHierarchy(list=None):
    # Updates hierarchy names

    objs = list if list is not None else GetAllCollisionAndSocketsObj()
    UpdatedHierarchy = 0
    for obj in objs:
        if fnmatch.fnmatchcase(obj.name, "UBX*"):
            UpdateUe4Name("Box", [obj])
            UpdatedHierarchy += 1
        if fnmatch.fnmatchcase(obj.name, "UCP*"):
            UpdateUe4Name("Capsule", [obj])
            UpdatedHierarchy += 1
        if fnmatch.fnmatchcase(obj.name, "USP*"):
            UpdateUe4Name("Sphere", [obj])
            UpdatedHierarchy += 1
        if fnmatch.fnmatchcase(obj.name, "UCX*"):
            UpdateUe4Name("Convex", [obj])
            UpdatedHierarchy += 1
        if fnmatch.fnmatchcase(obj.name, "SOCKET*"):
            UpdateUe4Name("Socket", [obj])
            UpdatedHierarchy += 1
        return UpdatedHierarchy


def GetVertexWithZeroWeight(Armature, Mesh):
    vertices = []
    for vertex in Mesh.data.vertices:
        cumulateWeight = 0
        if len(vertex.groups) > 0:
            for GroupElem in vertex.groups:
                if (Mesh.vertex_groups[GroupElem.group].name in
                        Armature.data.bones):
                    cumulateWeight += GroupElem.weight
        if cumulateWeight == 0:
            vertices.append(vertex)
    return vertices


def ContainsArmatureModifier(obj):
    return any(mod.type == "ARMATURE" for mod in obj.modifiers)


def GetSkeletonMeshs(obj):
    meshs = []
    if GetAssetType(obj) == "SkeletalMesh":  # Skeleton /  Armature
        childs = GetExportDesiredChilds(obj)
        meshs.extend(child for child in childs if child.type == "MESH")
    return meshs


def UpdateUnrealPotentialError():
    # Find and reset list of all potential error in scene

    addon_prefs = GetAddonPrefs()
    PotentialErrors = bpy.context.scene.potentialErrorList
    PotentialErrors.clear()

    # prepares the data to avoid unnecessary loops
    objToCheck = []
    for Asset in GetFinalAssetToExport():
        if Asset.obj in GetAllobjectsByExportType("export_recursive"):
            if Asset.obj not in objToCheck:
                objToCheck.append(Asset.obj)
            for child in GetExportDesiredChilds(Asset.obj):
                if child not in objToCheck:
                    objToCheck.append(child)

    MeshTypeToCheck = []
    for obj in objToCheck:
        if obj.type == 'MESH':
            MeshTypeToCheck.append(obj)

    MeshTypeWithoutCol = []  # is Mesh Type To Check Without Collision
    for obj in MeshTypeToCheck:
        if not CheckIsCollision(obj):
            MeshTypeWithoutCol.append(obj)

    def CheckUnitScale():
        # Check if the unit scale is equal to 0.01.
        if addon_prefs.notifyUnitScalePotentialError:
            if not math.isclose(
                    bpy.context.scene.unit_settings.scale_length,
                    0.01,
                    rel_tol=1e-5):
                MyError = PotentialErrors.add()
                MyError.name = bpy.context.scene.name
                MyError.type = 1
                MyError.text = (
                    'Scene "'+bpy.context.scene.name +
                    '" has a UnitScale egal to ' +
                    str(bpy.context.scene.unit_settings.scale_length))
                MyError.text += (
                    '\nFor Unreal unit scale equal to 0.01 is recommended.')
                MyError.text += (
                    '\n(You can disable this potential error in addon_prefs)')
                MyError.object = None
                MyError.correctRef = "SetUnrealUnit"
                MyError.correctlabel = 'Set Unreal Unit'

    def CheckObjType():
        # Check if objects use a non-recommended type
        for obj in objToCheck:
            if (obj.type == "SURFACE" or
                    obj.type == "META" or
                    obj.type == "FONT"):
                MyError = PotentialErrors.add()
                MyError.name = obj.name
                MyError.type = 1
                MyError.text = (
                    'Object "'+obj.name +
                    '" is a '+obj.type +
                    '. The object of the type SURFACE,' +
                    ' META and FONT is not recommended.')
                MyError.object = obj
                MyError.correctRef = "ConvertToMesh"
                MyError.correctlabel = 'Convert to mesh'

    def CheckShapeKeys():
        for obj in MeshTypeToCheck:
            if obj.data.shape_keys is not None:
                # Check that no modifiers is destructive for the key shapes
                if len(obj.data.shape_keys.key_blocks) > 0:
                    for modif in obj.modifiers:
                        if modif.type != "ARMATURE":
                            MyError = PotentialErrors.add()
                            MyError.name = obj.name
                            MyError.type = 2
                            MyError.object = obj
                            MyError.itemName = modif.name
                            MyError.text = (
                                'In object "'+obj.name +
                                '" the modifier '+modif.type +
                                ' named "'+modif.name +
                                '" can destroy shape keys.' +
                                ' Please use only Armature modifier' +
                                ' with shape keys.')
                            MyError.correctRef = "RemoveModfier"
                            MyError.correctlabel = 'Remove modifier'

                # Check that the key shapes are not out of bounds for Unreal
                for key in obj.data.shape_keys.key_blocks:
                    # Min
                    if key.slider_min < -5:
                        MyError = PotentialErrors.add()
                        MyError.name = obj.name
                        MyError.type = 1
                        MyError.object = obj
                        MyError.itemName = key.name
                        MyError.text = (
                            'In object "'+obj.name +
                            '" the shape key "'+key.name +
                            '" is out of bounds for Unreal.' +
                            ' The min range of must not be inferior to -5.')
                        MyError.correctRef = "SetKeyRangeMin"
                        MyError.correctlabel = 'Set min range to -5'

                    # Max
                    if key.slider_max > 5:
                        MyError = PotentialErrors.add()
                        MyError.name = obj.name
                        MyError.type = 1
                        MyError.object = obj
                        MyError.itemName = key.name
                        MyError.text = (
                            'In object "'+obj.name +
                            '" the shape key "'+key.name +
                            '" is out of bounds for Unreal.' +
                            ' The max range of must not be superior to 5.')
                        MyError.correctRef = "SetKeyRangeMax"
                        MyError.correctlabel = 'Set max range to -5'

    def CheckUVMaps():
        # Check that the objects have at least one UV map valid
        for obj in MeshTypeWithoutCol:
            if len(obj.data.uv_layers) < 1:
                MyError = PotentialErrors.add()
                MyError.name = obj.name
                MyError.type = 1
                MyError.text = (
                    'Object "'+obj.name +
                    '" does not have any UV Layer.')
                MyError.object = obj
                MyError.correctRef = "CreateUV"
                MyError.correctlabel = 'Create Smart UV Project'

    def CheckBadStaicMeshExportedLikeSkeletalMesh():
        # Check if the correct object is defined as exportable
        for obj in MeshTypeToCheck:
            for modif in obj.modifiers:
                if modif.type == "ARMATURE":
                    if obj.ExportEnum == "export_recursive":
                        MyError = PotentialErrors.add()
                        MyError.name = obj.name
                        MyError.type = 1
                        MyError.text = (
                            'In object "'+obj.name +
                            '" the modifier '+modif.type +
                            ' named "'+modif.name +
                            '" will not be applied when exported' +
                            ' with StaticMesh assets.\nNote: with armature' +
                            ' if you want export objets as skeletal mesh you' +
                            ' need set only the armature as' +
                            ' export_recursive not the childs')
                        MyError.object = obj

    def CheckArmatureScale():
        # Check if the ARMATURE use the same value on all scale axes
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                if obj.scale.z != obj.scale.y or obj.scale.z != obj.scale.x:
                    MyError = PotentialErrors.add()
                    MyError.name = obj.name
                    MyError.type = 2
                    MyError.text = (
                        'In object "'+obj.name +
                        '" do not use the same value on all scale axes ')
                    MyError.text += (
                        '\nScale x:' +
                        str(obj.scale.x)+' y:'+str(obj.scale.y) +
                        ' z:'+str(obj.scale.z))
                    MyError.object = obj

    def CheckArmatureNumber():
        # check Modifier or Constraint ARMATURE number = 1
        for obj in objToCheck:
            meshs = GetSkeletonMeshs(obj)
            for mesh in meshs:
                # Count
                armature_modifiers = 0
                armature_constraint = 0
                for mod in mesh.modifiers:
                    if mod.type == "ARMATURE":
                        armature_modifiers += 1
                for const in mesh.constraints:
                    if const.type == "ARMATURE":
                        armature_constraint += 1

                # Check result > 1
                if armature_modifiers + armature_constraint > 1:
                    MyError = PotentialErrors.add()
                    MyError.name = mesh.name
                    MyError.type = 2
                    MyError.text = (
                        'In object "'+mesh.name + '" ' +
                        str(armature_modifiers) + ' Armature modifier(s) and ' +
                        str(armature_modifiers) + ' Armature constraint(s) was found. ' +
                        ' Please use only one Armature modifier or one Armature constraint.')
                    MyError.object = mesh

                # Check result == 0
                if armature_modifiers + armature_constraint == 0:
                    MyError = PotentialErrors.add()
                    MyError.name = mesh.name
                    MyError.type = 2
                    MyError.text = (
                        'In object "'+mesh.name + '" ' +
                        ' no Armature modifiers or constraints was found. ' +
                        ' Please use only one Armature modifier or one Armature constraint.')
                    MyError.object = mesh

    def CheckArmatureModData():
        # check the parameter of Modifier ARMATURE
        for obj in MeshTypeToCheck:
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    if mod.use_deform_preserve_volume:
                        MyError = PotentialErrors.add()
                        MyError.name = obj.name
                        MyError.type = 2
                        MyError.text = (
                            'In object "'+obj.name +
                            '" the modifier '+mod.type +
                            ' named "'+mod.name +
                            '". The parameter Preserve Volume' +
                            ' must be set to False.')
                        MyError.object = obj
                        MyError.itemName = mod.name
                        MyError.correctRef = "PreserveVolume"
                        MyError.correctlabel = 'Set Preserve Volume to False'

    def CheckArmatureConstData():
        # check the parameter of constraint ARMATURE
        for obj in MeshTypeToCheck:
            for const in obj.constraints:
                if const.type == "ARMATURE":
                    pass
                    # TO DO.

    def CheckArmatureBoneData():
        # check the parameter of the ARMATURE bones
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                for bone in obj.data.bones:
                    if (not obj.exportDeformOnly or
                            (bone.use_deform and obj.exportDeformOnly)):

                        if bone.bbone_segments > 1:
                            MyError = PotentialErrors.add()
                            MyError.name = obj.name
                            MyError.type = 1
                            MyError.text = (
                                'In object3 "'+obj.name +
                                '" the bone named "'+bone.name +
                                '". The parameter Bendy Bones / Segments' +
                                ' must be set to 1.')
                            MyError.text += (
                                '\nBendy bones are not supported by' +
                                ' Unreal Engine, so that better to disable' +
                                ' it if you want the same animation preview' +
                                ' in Unreal and blender.')
                            MyError.object = obj
                            MyError.itemName = bone.name
                            MyError.selectPoseBoneButton = True
                            MyError.correctRef = "BoneSegments"
                            MyError.correctlabel = 'Set Bone Segments to 1'
                            MyError.docsOcticon = 'bendy-bone'

    def CheckArmatureValidChild():
        # Check that skeleton also has a mesh to export

        for obj in objToCheck:
            export_as_proxy = GetExportAsProxy(obj)
            if GetAssetType(obj) == "SkeletalMesh":
                childs = GetExportDesiredChilds(obj)
                validChild = 0
                for child in childs:
                    if child.type == "MESH":
                        validChild += 1
                if export_as_proxy:
                    if GetExportProxyChild(obj) is not None:
                        validChild += 1
                if validChild < 1:
                    MyError = PotentialErrors.add()
                    MyError.name = obj.name
                    MyError.type = 2
                    MyError.text = (
                        'Object "'+obj.name +
                        '" is an Armature and does not have' +
                        ' any valid children.')
                    MyError.object = obj

    def CheckArmatureChildWithBoneParent():
        # If you use Parent Bone to parent your mesh to your armature the import will fail.
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                childs = GetExportDesiredChilds(obj)
                for child in childs:
                    if child.type == "MESH":
                        if child.parent_type == 'BONE':
                            MyError = PotentialErrors.add()
                            MyError.name = child.name
                            MyError.type = 2
                            MyError.text = (
                                'Object "'+child.name +
                                '" use Parent Bone to parent. ' +
                                '\n If you use Parent Bone to parent your mesh to your armature the import will fail.')
                            MyError.object = child
                            MyError.docsOcticon = 'armature-child-with-bone-parent'

    def CheckArmatureMultipleRoots():
        # Check that skeleton have multiples roots
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                rootBones = GetArmatureRootBones(obj)

                if len(rootBones) > 1:
                    MyError = PotentialErrors.add()
                    MyError.name = obj.name
                    MyError.type = 1
                    MyError.text = (
                        'Object "'+obj.name +
                        '" have Multiple roots bones.' +
                        ' Unreal only support single root bone')
                    MyError.text += '\nA custom root bone will be added at the export.'
                    MyError.text += ' '+str(len(rootBones))+' root bones found: '
                    MyError.text += '\n'
                    for rootBone in rootBones:
                        MyError.text += rootBone.name+', '
                    MyError.object = obj

    def CheckArmatureNoDeformBone():
        # Check that skeleton have at less one deform bone
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                if obj.exportDeformOnly:
                    for bone in obj.data.bones:
                        if bone.use_deform:
                            return
                    MyError = PotentialErrors.add()
                    MyError.name = obj.name
                    MyError.type = 2
                    MyError.text = (
                        'Object "'+obj.name +
                        '" don\'t have any deform bones.' +
                        ' Unreal will import it like a StaticMesh.')
                    MyError.object = obj

    def CheckMarkerOverlay():
        # Check that there is no overlap with the Marker
        usedFrame = []
        for marker in bpy.context.scene.timeline_markers:
            if marker.frame in usedFrame:
                MyError = PotentialErrors.add()
                MyError.type = 2
                MyError.text = (
                    'In the scene timeline the frame "' +
                    str(marker.frame)+'" contains overlaped Markers' +
                    '\n To avoid camera conflict in the generation' +
                    ' of sequencer you must use max one marker per frame.')
            else:
                usedFrame.append(marker.frame)

    def CheckVertexGroupWeight():
        # Check that all vertex have a weight
        for obj in objToCheck:
            meshs = GetSkeletonMeshs(obj)
            for meshs in meshs:
                if meshs.type == "MESH":
                    if ContainsArmatureModifier(meshs):
                        # Result data
                        VertexWithZeroWeight = GetVertexWithZeroWeight(
                            obj,
                            meshs)
                        if len(VertexWithZeroWeight) > 0:
                            MyError = PotentialErrors.add()
                            MyError.name = meshs.name
                            MyError.type = 1
                            MyError.text = (
                                'Object named "'+meshs.name +
                                '" contains '+str(len(VertexWithZeroWeight)) +
                                ' vertex with zero cumulative valid weight.')
                            MyError.text += (
                                '\nNote: Vertex groups must have' +
                                ' a bone with the same name to be valid.')
                            MyError.object = meshs
                            MyError.selectVertexButton = True
                            MyError.selectOption = "VertexWithZeroWeight"

    def CheckZeroScaleKeyframe():
        # Check that animations do not use a invalid value
        for obj in objToCheck:
            if GetAssetType(obj) == "SkeletalMesh":
                for action in GetActionToExport(obj):
                    for fcurve in action.fcurves:
                        if fcurve.data_path.split(".")[-1] == "scale":
                            for key in fcurve.keyframe_points:
                                xCurve, yCurve = key.co
                                if key.co[1] == 0:
                                    MyError = PotentialErrors.add()
                                    MyError.type = 2
                                    MyError.text = (
                                        'In action "'+action.name +
                                        '" at frame '+str(key.co[0]) +
                                        ', the bone named "' +
                                        fcurve.data_path.split('"')[1] +
                                        '" has a zero value in scale' +
                                        ' transform. ' +
                                        'This is invalid in Unreal.')

    CheckUnitScale()
    CheckObjType()
    CheckShapeKeys()
    CheckUVMaps()
    CheckBadStaicMeshExportedLikeSkeletalMesh()
    CheckArmatureScale()
    CheckArmatureNumber()
    CheckArmatureModData()
    CheckArmatureConstData()
    CheckArmatureBoneData()
    CheckArmatureValidChild()
    CheckArmatureMultipleRoots()
    CheckArmatureChildWithBoneParent()
    CheckArmatureNoDeformBone()
    CheckMarkerOverlay()
    CheckVertexGroupWeight()
    CheckZeroScaleKeyframe()

    return PotentialErrors


def SelectPotentialErrorObject(errorIndex):
    # Select potential error

    bbpl.utils.SafeModeSet('OBJECT', bpy.context.active_object)
    scene = bpy.context.scene
    error = scene.potentialErrorList[errorIndex]
    obj = error.object

    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # show collection for select object
    for collection in bpy.data.collections:
        for ColObj in collection.objects:
            if ColObj == obj:
                SetCollectionUse(collection)
    bpy.ops.view3d.view_selected()
    return obj


def SelectPotentialErrorVertex(errorIndex):
    # Select potential error
    SelectPotentialErrorObject(errorIndex)
    bbpl.utils.SafeModeSet('EDIT')

    scene = bpy.context.scene
    error = scene.potentialErrorList[errorIndex]
    obj = error.object
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')

    bbpl.utils.SafeModeSet('OBJECT')
    if error.selectOption == "VertexWithZeroWeight":
        for vertex in GetVertexWithZeroWeight(obj.parent, obj):
            vertex.select = True
    bbpl.utils.SafeModeSet('EDIT')
    bpy.ops.view3d.view_selected()
    return obj


def SelectPotentialErrorPoseBone(errorIndex):
    # Select potential error
    SelectPotentialErrorObject(errorIndex)
    bbpl.utils.SafeModeSet('POSE')

    scene = bpy.context.scene
    error = scene.potentialErrorList[errorIndex]
    obj = error.object
    bone = obj.data.bones[error.itemName]

    # Make bone visible if hide in a layer
    for x, layer in enumerate(bone.layers):
        if not obj.data.layers[x] and layer:
            obj.data.layers[x] = True

    bpy.ops.pose.select_all(action='DESELECT')
    obj.data.bones.active = bone
    bone.select = True

    bpy.ops.view3d.view_selected()
    return obj


def TryToCorrectPotentialError(errorIndex):
    # Try to correct potential error

    scene = bpy.context.scene
    error = scene.potentialErrorList[errorIndex]
    global successCorrect
    successCorrect = False

    local_view_areas = MoveToGlobalView()

    MyCurrentDataSave = bbpl.utils.UserSceneSave()
    MyCurrentDataSave.SaveCurrentScene()

    bbpl.utils.SafeModeSet('OBJECT', MyCurrentDataSave.user_select_class.user_active)

    print("Start correct")

    def SelectObj(obj):
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    # Correction list

    if error.correctRef == "SetUnrealUnit":
        bpy.context.scene.unit_settings.scale_length = 0.01
        successCorrect = True

    if error.correctRef == "ConvertToMesh":
        obj = error.object
        SelectObj(obj)
        bpy.ops.object.convert(target='MESH')
        successCorrect = True

    if error.correctRef == "SetKeyRangeMin":
        obj = error.object
        key = obj.data.shape_keys.key_blocks[error.itemName]
        key.slider_min = -5
        successCorrect = True

    if error.correctRef == "SetKeyRangeMax":
        obj = error.object
        key = obj.data.shape_keys.key_blocks[error.itemName]
        key.slider_max = 5
        successCorrect = True

    if error.correctRef == "CreateUV":
        obj = error.object
        SelectObj(obj)
        if bbpl.utils.SafeModeSet("EDIT", obj):
            bpy.ops.uv.smart_project()
            successCorrect = True
        else:
            successCorrect = False

    if error.correctRef == "RemoveModfier":
        obj = error.object
        mod = obj.modifiers[error.itemName]
        obj.modifiers.remove(mod)
        successCorrect = True

    if error.correctRef == "PreserveVolume":
        obj = error.object
        mod = obj.modifiers[error.itemName]
        mod.use_deform_preserve_volume = False
        successCorrect = True

    if error.correctRef == "BoneSegments":
        obj = error.object
        bone = obj.data.bones[error.itemName]
        bone.bbone_segments = 1
        successCorrect = True

    if error.correctRef == "InheritScale":
        obj = error.object
        bone = obj.data.bones[error.itemName]
        bone.use_inherit_scale = True
        successCorrect = True

    # ----------------------------------------Reset data
    MyCurrentDataSave.ResetSelectByName()
    MyCurrentDataSave.ResetSceneAtSave()
    MoveToLocalView(local_view_areas)

    # ----------------------------------------

    if successCorrect:
        scene.potentialErrorList.remove(errorIndex)
        print("end correct, Error: " + error.correctRef)
        return "Corrected"
    print("end correct, Error not found")
    return "Correct fail"


class BFU_OT_UnrealPotentialError(bpy.types.PropertyGroup):
    type: bpy.props.IntProperty(default=0)  # 0:Info, 1:Warning, 2:Error
    object: bpy.props.PointerProperty(type=bpy.types.Object)
    ###
    selectObjectButton: bpy.props.BoolProperty(default=True)
    selectVertexButton: bpy.props.BoolProperty(default=False)
    selectPoseBoneButton: bpy.props.BoolProperty(default=False)
    ###
    selectOption: bpy.props.StringProperty(default="None")  # 0:VertexWithZeroWeight
    itemName: bpy.props.StringProperty(default="None")
    text: bpy.props.StringProperty(default="Unknown")
    correctRef: bpy.props.StringProperty(default="None")
    correctlabel: bpy.props.StringProperty(default="Fix it !")
    correctDesc: bpy.props.StringProperty(default="Correct target error")
    docsOcticon: bpy.props.StringProperty(default="None")


classes = (
    BFU_OT_UnrealPotentialError,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.potentialErrorList = bpy.props.CollectionProperty(type=BFU_OT_UnrealPotentialError)


def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.potentialErrorList
