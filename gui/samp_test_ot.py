# DemonFF - Blender scripts for working with Renderware & R*/SA-MP formats in Blender
# 2023 - 2026 spicybung

import bpy

from ..ops import samp_test


class SCENE_OT_demonff_stop_test_server(bpy.types.Operator):
    bl_idname = "scene.demonff_stop_test_server"
    bl_label = "Stop Test"
    bl_description = "Close the test game and stop the test server"

    def execute(self, context):
        samp_test.stop_server_process()
        samp_test.stop_running_gta()
        self.report({"INFO"}, "DemonFF local model test stopped")
        return {"FINISHED"}


class SCENE_OT_demonff_test_selected_model(bpy.types.Operator):
    bl_idname = "scene.demonff_test_selected_model"
    bl_label = "Test Selected Model"
    bl_description = (
        "Export the selected model, start the local test server, open the selected "
        "multiplayer launcher, and connect to 127.0.0.1:7777"
    )

    def execute(self, context):
        try:
            package_root = samp_test.get_local_test_root(create=True)
            game_root = samp_test.resolve_gtasa_game_root(
                context.scene.dff.samp_game_root
            )
            context.scene.dff.samp_game_root = str(game_root)

            runtime = samp_test.ensure_local_runtime(
                package_root,
                game_root,
                context.scene.dff.samp_client_executable,
            )
            context.scene.dff.samp_client_executable = str(runtime.client_executable)

            samp_test.stop_server_process()
            _dff_path, _txd_path, live_anchor = samp_test.export_selected_model(
                context,
                runtime.server_root,
            )
            samp_test.write_and_compile_gamemode(
                runtime.server_root,
                runtime.pawn_compiler,
                runtime.include_directory,
                runtime.pawn_include_name,
            )
            samp_test.configure_test_server(
                runtime.server_root,
                runtime.server_executable,
            )
            samp_test.start_server(runtime.server_executable, runtime.server_root)
            if context.scene.dff.samp_live_transform:
                samp_test.start_live_transform_sync(live_anchor)
            launched_client = samp_test.launch_client(
                runtime.client_executable,
                runtime.source_game_root,
                runtime.fallback_client_executable,
            )
        except Exception as error:
            samp_test.stop_server_process()
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        if context.scene.dff.samp_live_transform:
            self.report(
                {"INFO"},
                "Test started. Moving or rotating the selected model updates it in-game.",
            )
        else:
            self.report({"INFO"}, "Test started")
        return {"FINISHED"}


class SCENE_OT_demonff_open_game_root(bpy.types.Operator):
    bl_idname = "scene.demonff_open_game_root"
    bl_label = "Open Game Root"
    bl_description = "Open the GTA San Andreas folder selected for the local model test"

    def execute(self, context):
        root_text = context.scene.dff.samp_game_root
        root = samp_test.normalize_directory_path(root_text)

        if root is None or not root.is_dir():
            self.report({"ERROR"}, "Select a valid GTA San Andreas Game Root first")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=str(root))
        return {"FINISHED"}


class SCENE_OT_demonff_open_local_test_root(bpy.types.Operator):
    bl_idname = "scene.demonff_open_local_test_root"
    bl_label = "Open Test Files"
    bl_description = "Open DemonFF's writable GTASA test package in Blender's user folder"

    def execute(self, context):
        try:
            local_root = samp_test.get_local_test_root(create=True)
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=str(local_root))
        return {"FINISHED"}
