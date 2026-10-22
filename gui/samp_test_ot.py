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
    bl_label = "Test Selected Models"
    bl_description = (
        "Test all selected models. Large Pawn/open.mp map selections use their original DFF/TXD "
        "files and lightweight placement data instead of rebuilding thousands of duplicate meshes"
    )

    def execute(self, context):
        samp_test.begin_test_progress("Test Selected Models")
        try:
            samp_test.test_progress("Stage 1/10: resolving the writable test package and GTA SA root")
            package_root = samp_test.get_local_test_root(create=True)
            game_root = samp_test.resolve_gtasa_game_root(
                context.scene.dff.samp_game_root
            )
            context.scene.dff.samp_game_root = str(game_root)

            samp_test.test_progress("Stage 2/10: checking the reusable server/compiler runtime")
            runtime = samp_test.ensure_local_runtime(
                package_root,
                game_root,
                context.scene.dff.samp_client_executable,
            )
            context.scene.dff.samp_client_executable = str(runtime.client_executable)

            samp_test.test_progress("Stage 3/10: stopping the previous server process")
            samp_test.stop_server_process()

            samp_test.test_progress("Stage 4/10: exporting or reusing the selected models")
            _dff_path, _txd_path, live_anchor = samp_test.export_selected_model(
                context,
                runtime.server_root,
            )

            player_target = None
            if context.scene.dff.samp_player_sync:
                samp_test.test_progress("Stage 5/10: resolving the live player/ped target")
                player_target = samp_test.resolve_player_sync_target(context)
            else:
                samp_test.test_progress("Stage 5/10: player-to-Blender tracking is disabled")

            samp_test.test_progress("Stage 6/10: preparing the data-driven Pawn gamemode")
            samp_test.write_and_compile_gamemode(
                runtime.server_root,
                runtime.pawn_compiler,
                runtime.include_directory,
                runtime.pawn_include_name,
            )

            samp_test.test_progress("Stage 7/10: writing the local server configuration")
            samp_test.configure_test_server(
                runtime.server_root,
                runtime.server_executable,
            )

            samp_test.test_progress("Stage 8/10: starting the local test server")
            samp_test.start_server(
                runtime.server_executable,
                runtime.server_root,
                initial_transform=samp_test.get_test_model_transform(),
            )

            samp_test.test_progress("Stage 9/10: enabling Blender/game live synchronization")
            live_transform_enabled = (
                context.scene.dff.samp_live_transform
                and samp_test.LAST_TEST_SUPPORTS_LIVE_TRANSFORM
            )
            if samp_test.objects_share_transform_hierarchy(
                player_target,
                live_anchor,
            ):
                live_transform_enabled = False

            if live_transform_enabled:
                samp_test.start_live_transform_sync(live_anchor)

            if context.scene.dff.samp_player_sync:
                samp_test.start_player_sync(
                    context,
                    target=player_target,
                    follow_view=context.scene.dff.samp_player_follow_view,
                )

            samp_test.test_progress("Stage 10/10: launching the multiplayer client")
            samp_test.launch_client(
                runtime.client_executable,
                runtime.source_game_root,
                runtime.fallback_client_executable,
            )
        except Exception as error:
            samp_test.stop_server_process()
            samp_test.finish_test_progress(False, str(error))
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        samp_test.finish_test_progress(
            True,
            "%d placement(s) from %d source model(s) using %s"
            % (
                samp_test.LAST_TEST_PLACEMENT_COUNT,
                samp_test.LAST_TEST_SOURCE_MODEL_COUNT,
                samp_test.LAST_TEST_EXPORT_MODE,
            ),
        )

        if samp_test.LAST_TEST_EXPORT_MODE in {
            "FAST_PLACEMENTS",
            "FAST_STATIC_MAP",
            "LINKED_INSTANCES",
            "LINKED_STATIC_MAP",
        }:
            self.report(
                {"INFO"},
                "Test started: %d placements from %d source model(s), without rebuilding duplicate geometry."
                % (
                    samp_test.LAST_TEST_PLACEMENT_COUNT,
                    samp_test.LAST_TEST_SOURCE_MODEL_COUNT,
                ),
            )
        elif context.scene.dff.samp_player_sync:
            self.report(
                {"INFO"},
                "Test started. The selected models are in-game and player movement is mirrored into Blender.",
            )
        elif context.scene.dff.samp_live_transform:
            self.report({"INFO"}, "Test started")
        else:
            self.report({"INFO"}, "Test started")
        return {"FINISHED"}


class SCENE_OT_demonff_use_active_player_target(bpy.types.Operator):
    bl_idname = "scene.demonff_use_active_player_target"
    bl_label = "Use Active as Player"
    bl_description = (
        "Use the active object or ped root as the Blender target for live player movement"
    )

    def execute(self, context):
        active_object = context.view_layer.objects.active
        if active_object is None:
            self.report({"ERROR"}, "Select the ped or root object to follow")
            return {"CANCELLED"}

        target_object = samp_test.choose_player_sync_target(active_object)
        samp_test.set_configured_player_sync_target(context, target_object)
        self.report(
            {"INFO"},
            f"Player movement will drive {target_object.name}",
        )
        return {"FINISHED"}


class SCENE_OT_demonff_create_player_tracker(bpy.types.Operator):
    bl_idname = "scene.demonff_create_player_tracker"
    bl_label = "Create Player Tracker"
    bl_description = (
        "Create a lightweight Blender empty that follows the SA-MP/open.mp player"
    )

    def execute(self, context):
        tracker = samp_test.create_player_tracker_object(context)
        samp_test.set_configured_player_sync_target(context, tracker)

        for obj in context.selected_objects:
            obj.select_set(False)
        tracker.select_set(True)
        context.view_layer.objects.active = tracker

        self.report({"INFO"}, "Created DemonFF Live Player tracker")
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


class SCENE_OT_demonff_clean_test_files(bpy.types.Operator):
    bl_idname = "scene.demonff_clean_test_files"
    bl_label = "Clean Generated Test Files"
    bl_description = (
        "Delete generated test DFF/TXD files, live state files and logs without "
        "removing the reusable server or compiler"
    )

    def execute(self, context):
        samp_test.stop_server_process()
        removed_count, removed_bytes = samp_test.clean_generated_test_files()
        self.report(
            {"INFO"},
            "Removed %d generated file(s), freeing %s"
            % (
                removed_count,
                samp_test.format_byte_count(removed_bytes),
            ),
        )
        return {"FINISHED"}
