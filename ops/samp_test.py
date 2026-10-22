# DemonFF - Blender scripts for working with Renderware & R*/SA-MP formats in Blender
# 2023 - 2026 spicybung

import bisect
import hashlib
import json
import math
import os
import shutil
import socket
import stat
import struct
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from collections import namedtuple
from pathlib import Path, PurePosixPath

import bpy
import mathutils

from . import dff_samp_exporter, txd_exporter
from .map_transform import quaternion_to_gta_euler_degrees
from ..data.bone_data import (
    DIRECT_ID_PROPERTY_NAMES,
    directIdFromBoneName,
)

SERVER_PROCESS = None
SERVER_LOG_HANDLE = None
SERVER_ROOT = None
CLIENT_WATCH_TIMER = None
LIVE_TEST_OBJECT = None
LIVE_TEST_LAST_TRANSFORM = None
LIVE_TEST_ACTIVE = False
LIVE_TEST_BASE_ROTATION = None
LIVE_TEST_REVISION = 0
PLAYER_SYNC_TARGET = None
PLAYER_SYNC_ARMATURE = None
PLAYER_SYNC_ACTIVE = False
PLAYER_SYNC_FOLLOW_VIEW = False
PLAYER_SYNC_LAST_REVISION = -1
PLAYER_SYNC_BASIS_OFFSET = None
PLAYER_SYNC_ALIGNMENT_LOCAL = None
PLAYER_SYNC_POSITION_OFFSET = None
PLAYER_SYNC_HEADING_OFFSET = 0.0
PLAYER_SYNC_AUTO_ALIGN_PED = True
PLAYER_SYNC_CREATED_TARGET = False
PLAYER_SYNC_PREVIOUS_STATE = None
PLAYER_SYNC_LAST_STATE = None
PLAYER_SYNC_STATE_RECEIVED_TIME = 0.0
PLAYER_SYNC_ORIGINAL_ACTION = None
PLAYER_SYNC_ORIGINAL_FRAME = None
PLAYER_SYNC_ACTION = None
PLAYER_SYNC_ACTION_TOKEN = None
PLAYER_SYNC_ACTION_START_TIME = 0.0
PLAYER_SYNC_ACTION_START_FRAME = 0.0
PLAYER_SYNC_ACTION_LOOP = True
PLAYER_SYNC_RUNTIME_ANIMATION = None
PLAYER_SYNC_RUNTIME_TRACKS = []
PLAYER_SYNC_RUNTIME_MISSING_TRACKS = []
PLAYER_SYNC_RUNTIME_FIRST_FRAME = 0.0
PLAYER_SYNC_RUNTIME_LAST_FRAME = 0.0
PLAYER_SYNC_RUNTIME_SOURCE_FPS = 30.0
PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME = None
PLAYER_SYNC_RUNTIME_LAST_LOG_TIME = 0.0
PLAYER_SYNC_MUTED_NLA_TRACKS = []
PLAYER_SYNC_ORIGINAL_POSE_POSITION = None
PLAYER_SYNC_ANIMATION_ENABLED = True
PLAYER_SYNC_AUTO_LOAD_IFP = True
PLAYER_SYNC_GAME_ROOT = None
PLAYER_SYNC_ANIMATION_STATUS = ""
PLAYER_SYNC_IFP_CACHE = {}
PLAYER_SYNC_TRANSFORM_ROOTS = []
PLAYER_SYNC_TRANSFORM_BASE_MATRICES = {}
PLAYER_SYNC_MODEL_FRAME_WORLD = None
PLAYER_SYNC_MODEL_FRAME_DESCRIPTION = ""
LAST_TEST_EXPORT_MODE = "PACKED"
LAST_TEST_PLACEMENT_COUNT = 0
LAST_TEST_SOURCE_MODEL_COUNT = 0
LAST_TEST_SUPPORTS_LIVE_TRANSFORM = True
LAST_TEST_MATERIAL_TXD_COUNT = 0
LAST_TEST_MATERIAL_TEXTURE_COUNT = 0
TEST_PROGRESS_STARTED_AT = 0.0
TEST_PROGRESS_LAST_AT = 0.0
FAST_TEST_LAST_REJECTION = ""
LOCAL_RUNTIME_CACHE_KEY = None
LOCAL_RUNTIME_CACHE_VALUE = None
TEST_ASSET_INDEX_CACHE = {}

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 7777
LOCAL_PLAYER_NAME = "DemonFF_Tester"
TEST_BUILD_TAG = "direct-ped-ifp-sampler-all-groups-facing-v5"
TEST_MODE_NAME = "demonff_blender_test"
TEST_MODEL_NAME = "dftest"
TEST_BASE_MODEL_ID = 18631
TEST_CUSTOM_MODEL_ID = -29999
TEST_DRAW_DISTANCE = 300.0
COLLISION_PLUGIN_ID = 0x0253F2FF
SAMP_KEY_SPRINT = 8
SAMP_KEY_JUMP = 32
SAMP_KEY_WALK = 1024


def dff_has_embedded_collision(file_path):
    try:
        data = Path(file_path).read_bytes()
    except OSError:
        return False

    marker = struct.pack("<I", COLLISION_PLUGIN_ID)
    search_offset = 0

    while True:
        chunk_offset = data.find(marker, search_offset)
        if chunk_offset < 0:
            return False

        if chunk_offset + 12 <= len(data):
            chunk_size = struct.unpack_from("<I", data, chunk_offset + 4)[0]
            chunk_end = chunk_offset + 12 + chunk_size
            if chunk_size > 0 and chunk_end <= len(data):
                return True

        search_offset = chunk_offset + 1

TEST_MODEL_POSITION = (0.0, 0.0, 0.0)
TEST_MODEL_ROTATION = (0.0, 0.0, 0.0)
LIVE_TRANSFORM_INTERVAL = 0.1
LIVE_TRANSFORM_FILE_NAME = "demonff_live_transform.txt"
PLAYER_STATE_INTERVAL = 1.0 / 60.0
PLAYER_STATE_FILE_NAME = "demonff_player_state.txt"
PLAYER_STATE_MAX_PREDICTION_SECONDS = 0.10
PLAYER_ALIGNMENT_ROOT_BONE_NAMES = (
    "root",
    "sceneroot",
    "bip01",
    "male",
    "malebase",
    "pelvis",
)
BUNDLED_PED_IFP_RELATIVE_PATH = Path("resources") / "anim" / "ped.ifp"
PLAYER_TRACKER_COLLECTION_NAME = "DemonFF Live Tracking"
PLAYER_TRACKER_OBJECT_NAME = "DemonFF Live Player"
LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY = "demonff_live_player_only"
MAX_ACTIVE_MODEL_OBJECTS = 512
MAX_PACKED_TEST_OBJECTS = 16384
FAST_TEST_PLACEMENT_THRESHOLD = 1
STATIC_MAP_PLACEMENT_THRESHOLD = 512
MAX_TEXTURES_PER_TEST_TXD = 999
FAST_TEST_MODEL_PREFIX = "df_"
MATERIAL_TEST_TXD_PREFIX = "dm_"
EMPTY_TEST_TXD_NAME = "de.txd"
GENERATED_TEST_MODEL_PATTERNS = (
    "demonff_test_model*.dff",
    "demonff_test_model*.txd",
    "demonff_fast_*.dff",
    "demonff_fast_*.txd",
    "df_*.dff",
    "df_*.txd",
    "d????????????.dff",
    "t????????????.txd",
    "dg*.dff",
    "tg*.txd",
    "g????????????.dff",
    "x????????????.txd",
    "dm_*.txd",
    "de.txd",
)
TEST_MODEL_DEFINITION_FILE_NAME = "demonff_test_models.txt"
TEST_PLACEMENT_FILE_NAME = "demonff_test_placements.txt"
TEST_PIVOT_MODEL_ID = 19300
LOCAL_RCON_PASSWORD = "demonff_test_local"
GENERATED_CONFIG_MARKER = "DemonFF Blender local model test server"
GTASA_DIRECTORY_NAME = "GTASA"
TEST_SERVER_DIRECTORY_NAME = "DemonFFTestServer"
GAME_LINK_MARKER_NAME = ".demonff_game_root.txt"
GAME_LINK_DIRECTORY_NAMES = ("anim", "audio", "data", "models", "movies", "text")
GAME_LINK_FILE_NAMES = ("gta_sa.exe",)
COMMON_GTASA_ROOTS = (
    Path(r"C:\Program Files (x86)\Rockstar Games\Grand Theft Auto San Andreas"),
    Path(r"C:\Program Files\Rockstar Games\Grand Theft Auto San Andreas"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto San Andreas"),
    Path(r"C:\Program Files\Steam\steamapps\common\Grand Theft Auto San Andreas"),
)
DOWNLOAD_CACHE_DIRECTORY_NAME = ".demonff_downloads"
CLIENT_PAYLOAD_ARCHIVE_NAME = "demonff_gtasa_client_payload.zip"
SAMP_SERVER_ARCHIVE_NAME = "samp03DL_svr_R1_win32.zip"
STREAMER_ARCHIVE_NAME = "samp-streamer-plugin.zip"
OMP_SERVER_EXECUTABLE_NAMES = ("omp-server.exe",)
SAMP_SERVER_EXECUTABLE_NAMES = ("samp-server.exe",)
OMP_CLIENT_EXECUTABLE_NAMES = (
    "omp-launcher.exe",
    "open.mp launcher.exe",
    "openmp-launcher.exe",
)
SAMP_CLIENT_EXECUTABLE_NAMES = ("samp.exe",)

SAMP_SERVER_DOWNLOAD_URLS = (
    "https://github.com/Goodup302/sa-mp-0.3.DL-R1/raw/refs/heads/master/samp03DL_svr_R1_win32.zip",
    "https://raw.githubusercontent.com/Goodup302/sa-mp-0.3.DL-R1/master/samp03DL_svr_R1_win32.zip",
)
STREAMER_RELEASE_API_URL = (
    "https://api.github.com/repos/samp-incognito/"
    "samp-streamer-plugin/releases/latest"
)
STREAMER_FALLBACK_DOWNLOAD_URL = (
    "https://github.com/samp-incognito/samp-streamer-plugin/"
    "releases/download/v2.9.6/samp-streamer-plugin-2.9.6.zip"
)
DOWNLOAD_USER_AGENT = "DemonFF/0.6.9 Blender SA-MP model tester"

LocalRuntime = namedtuple(
    "LocalRuntime",
    (
        "gtasa_root",
        "source_game_root",
        "package_root",
        "server_root",
        "server_executable",
        "server_kind",
        "client_executable",
        "client_kind",
        "fallback_client_executable",
        "pawn_compiler",
        "include_directory",
        "pawn_include_name",
        "streamer_plugin",
    ),
)


def begin_test_progress(label="Test Selected Models"):
    global TEST_PROGRESS_STARTED_AT
    global TEST_PROGRESS_LAST_AT

    now = time.perf_counter()
    TEST_PROGRESS_STARTED_AT = now
    TEST_PROGRESS_LAST_AT = now
    print("", flush=True)
    print("=" * 72, flush=True)
    print(
        f"[DemonFF Test +0.000s] {label} started [{TEST_BUILD_TAG}]",
        flush=True,
    )


def test_progress(message, current=None, total=None):
    global TEST_PROGRESS_STARTED_AT
    global TEST_PROGRESS_LAST_AT

    now = time.perf_counter()
    if TEST_PROGRESS_STARTED_AT <= 0.0:
        TEST_PROGRESS_STARTED_AT = now
        TEST_PROGRESS_LAST_AT = now

    elapsed = now - TEST_PROGRESS_STARTED_AT
    delta = now - TEST_PROGRESS_LAST_AT
    TEST_PROGRESS_LAST_AT = now

    if current is not None and total:
        total_value = max(1, int(total))
        current_value = max(0, min(int(current), total_value))
        percent = (float(current_value) / float(total_value)) * 100.0
        prefix = f"[{current_value}/{total_value} {percent:5.1f}%] "
    else:
        prefix = ""

    print(
        f"[DemonFF Test +{elapsed:8.3f}s | step {delta:7.3f}s] {prefix}{message}",
        flush=True,
    )


def finish_test_progress(success=True, message=""):
    now = time.perf_counter()
    elapsed = max(0.0, now - TEST_PROGRESS_STARTED_AT)
    state = "finished" if success else "failed"
    suffix = f": {message}" if message else ""
    print(f"[DemonFF Test +{elapsed:8.3f}s] {state}{suffix}", flush=True)
    print("=" * 72, flush=True)


def progress_checkpoint(index, total, maximum_messages=20):
    total = max(1, int(total))
    stride = max(1, total // max(1, int(maximum_messages)))
    return index == 1 or index == total or index % stride == 0


def set_fast_test_rejection(reason):
    global FAST_TEST_LAST_REJECTION
    FAST_TEST_LAST_REJECTION = str(reason or "")


def get_blender_user_root():
    user_root_text = bpy.utils.resource_path('USER')
    if not user_root_text:
        config_root_text = bpy.utils.user_resource('CONFIG')
        if config_root_text:
            user_root_text = str(Path(config_root_text).expanduser().parent)

    if not user_root_text:
        raise RuntimeError("Blender did not report its user folder.")

    try:
        user_root = Path(user_root_text).expanduser().resolve()
    except OSError:
        user_root = Path(user_root_text).expanduser().absolute()

    try:
        user_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise RuntimeError(f"Could not use Blender's user folder: {error}") from error

    return user_root


def get_blender_install_root():
    return get_blender_user_root()


def get_addon_root():
    return Path(__file__).resolve().parent.parent


def normalize_directory_path(path_value):
    if path_value is None:
        return None

    if isinstance(path_value, Path):
        path = path_value
    else:
        path_text = str(path_value).strip().strip('"')
        if not path_text:
            return None
        try:
            path_text = bpy.path.abspath(path_text)
        except Exception:
            pass
        path = Path(path_text)

    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def find_case_insensitive_path(root, relative_parts):
    current = normalize_directory_path(root)
    if current is None or not current.is_dir():
        return None

    for part in relative_parts:
        direct = current / part
        if direct.exists():
            current = direct
            continue

        try:
            matches = [entry for entry in current.iterdir() if entry.name.lower() == part.lower()]
        except OSError:
            return None

        if not matches:
            return None
        current = matches[0]

    return current


def validate_gtasa_game_root(game_root):
    root = normalize_directory_path(game_root)
    if root is None or not root.is_dir():
        return False, "The selected GTA San Andreas Game Root does not exist."

    required_files = (
        ("gta_sa.exe",),
        ("data", "gta.dat"),
        ("models", "gta3.img"),
    )
    missing = []

    for relative_parts in required_files:
        found = find_case_insensitive_path(root, relative_parts)
        if found is None or not found.is_file():
            missing.append(str(Path(*relative_parts)))

    if missing:
        missing_text = ", ".join(missing)
        return False, (
            f"{root} is not a complete GTA San Andreas installation. "
            f"Missing: {missing_text}"
        )

    return True, ""


def find_preferred_gtasa_game_root():
    candidates = list(COMMON_GTASA_ROOTS)

    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    program_files = os.environ.get("ProgramFiles")

    if program_files_x86:
        candidates.insert(
            0,
            Path(program_files_x86) / "Rockstar Games" / "Grand Theft Auto San Andreas",
        )
    if program_files:
        candidates.append(
            Path(program_files) / "Rockstar Games" / "Grand Theft Auto San Andreas"
        )

    for candidate in unique_path_candidates(candidates):
        valid, _ = validate_gtasa_game_root(candidate)
        if valid:
            return candidate

    return normalize_directory_path(COMMON_GTASA_ROOTS[0])


def get_default_gtasa_game_root_text():
    preferred = find_preferred_gtasa_game_root()
    return str(preferred) if preferred is not None else ""


def unique_path_candidates(paths):
    results = []
    seen = set()

    for path in paths:
        normalized = normalize_directory_path(path)
        if normalized is None:
            continue
        key = os.path.normcase(str(normalized))
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)

    return results


def resolve_gtasa_game_root(configured_root):
    configured = normalize_directory_path(configured_root)
    preferred = find_preferred_gtasa_game_root()
    candidates = unique_path_candidates((configured, preferred, *COMMON_GTASA_ROOTS))
    errors = []

    for candidate in candidates:
        valid, detail = validate_gtasa_game_root(candidate)
        if valid:
            return candidate
        if candidate == configured and detail:
            errors.append(detail)

    if errors:
        raise RuntimeError(errors[0])

    raise RuntimeError(
        "GTA San Andreas was not found. Set Game Root in DemonFF - SAMP I/O. "
        r"The usual folder is C:\Program Files (x86)\Rockstar Games\Grand Theft Auto San Andreas."
    )



def paths_refer_to_same_location(first_path, second_path):
    first = normalize_directory_path(first_path)
    second = normalize_directory_path(second_path)
    if first is None or second is None:
        return False

    try:
        return os.path.samefile(first, second)
    except OSError:
        return os.path.normcase(str(first)) == os.path.normcase(str(second))

def path_is_within(path_value, root_value):
    path = normalize_directory_path(path_value)
    root = normalize_directory_path(root_value)

    if path is None or root is None:
        return False

    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        path_text = os.path.normcase(os.path.abspath(str(path)))
        root_text = os.path.normcase(os.path.abspath(str(root)))
        try:
            return os.path.commonpath((path_text, root_text)) == root_text
        except ValueError:
            return False
def create_directory_link(link_path, target_path):
    link_path = Path(link_path)
    target_path = Path(target_path)

    if link_path.exists():
        return False

    link_path.parent.mkdir(parents=True, exist_ok=True)

    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/D", "/C", "mklink", "/J", str(link_path), str(target_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0 and link_path.exists():
            return True

    try:
        os.symlink(str(target_path), str(link_path), target_is_directory=True)
        return True
    except OSError as error:
        raise RuntimeError(
            f"Could not link {link_path.name} to the selected GTA SA Game Root: {error}"
        ) from error


def create_file_link(link_path, target_path):
    link_path = Path(link_path)
    target_path = Path(target_path)

    if link_path.exists():
        return False

    link_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.link(str(target_path), str(link_path))
        return True
    except OSError:
        pass

    try:
        os.symlink(str(target_path), str(link_path))
        return True
    except OSError:
        pass

    try:
        shutil.copy2(target_path, link_path)
        return True
    except OSError as error:
        raise RuntimeError(
            f"Could not make {link_path.name} available in DemonFF's GTASA folder: {error}"
        ) from error


def is_link_like_path(path):
    path = Path(path)
    if path.is_symlink():
        return True

    if os.name != "nt":
        return False

    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, OSError):
        return False

    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def remove_link_like_path(path):
    path = Path(path)
    if not is_link_like_path(path):
        return False

    try:
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            os.rmdir(path)
        else:
            path.unlink()
        return True
    except OSError:
        if os.name != "nt":
            return False

    result = subprocess.run(
        ["cmd", "/D", "/C", "rmdir", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def ensure_package_game_links(package_root, game_root):
    package_root = normalize_directory_path(package_root)
    game_root = normalize_directory_path(game_root)

    if package_root is None or game_root is None:
        raise RuntimeError("DemonFF could not resolve the local GTASA package or Game Root.")

    valid_root, detail = validate_gtasa_game_root(game_root)
    if not valid_root:
        raise RuntimeError(detail)

    package_root.mkdir(parents=True, exist_ok=True)
    marker_path = package_root / GAME_LINK_MARKER_NAME

    previous_root = None
    try:
        previous_text = marker_path.read_text(encoding="utf-8").strip()
        if previous_text:
            previous_root = normalize_directory_path(previous_text)
    except OSError:
        pass

    root_changed = previous_root is not None and not paths_refer_to_same_location(
        previous_root,
        game_root,
    )

    if root_changed:
        for directory_name in GAME_LINK_DIRECTORY_NAMES:
            remove_link_like_path(package_root / directory_name)

    for directory_name in GAME_LINK_DIRECTORY_NAMES:
        source = find_case_insensitive_path(game_root, (directory_name,))
        destination = package_root / directory_name

        if source is None or not source.is_dir():
            continue

        if destination.exists():
            if paths_refer_to_same_location(destination, source):
                continue
            if not remove_link_like_path(destination):
                continue

        create_directory_link(destination, source)

    for file_name in GAME_LINK_FILE_NAMES:
        source = find_case_insensitive_path(game_root, (file_name,))
        destination = package_root / file_name

        if source is None or not source.is_file():
            continue

        if destination.exists() or destination.is_symlink():
            if paths_refer_to_same_location(destination, source):
                continue

            if not remove_link_like_path(destination):
                try:
                    destination.unlink()
                except OSError as error:
                    raise RuntimeError(
                        f"Could not replace {destination.name} in DemonFF's GTASA folder: {error}"
                    ) from error

        create_file_link(destination, source)

    try:
        marker_path.write_text(str(game_root), encoding="utf-8")
    except OSError:
        pass

    return package_root


def normalize_archive_name(name):
    return name.replace('\\', '/').lstrip('/')


def safe_destination(root, archive_name):
    clean_name = normalize_archive_name(archive_name)
    pure_path = PurePosixPath(clean_name)

    if not clean_name or pure_path.is_absolute() or '..' in pure_path.parts:
        raise RuntimeError(f"Unsafe path in downloaded package: {archive_name}")

    destination = root.joinpath(*pure_path.parts)
    root_resolved = root.resolve()
    destination_resolved = destination.resolve()

    try:
        destination_resolved.relative_to(root_resolved)
    except ValueError as error:
        raise RuntimeError(f"Unsafe path in downloaded package: {archive_name}") from error

    return destination


def copy_zip_member(archive, member, destination, overwrite=False):
    if member.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        return

    if destination.exists() and not overwrite:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(destination.name + ".demonff_tmp")

    if temporary_path.exists():
        temporary_path.unlink()

    with archive.open(member, 'r') as source, open(temporary_path, 'wb') as output:
        shutil.copyfileobj(source, output, length=1024 * 1024)

    os.replace(temporary_path, destination)


def install_bundled_client_payload(gtasa_root):
    payload_path = get_addon_root() / "local_test_package" / CLIENT_PAYLOAD_ARCHIVE_NAME
    if not payload_path.is_file():
        return False

    try:
        with zipfile.ZipFile(payload_path, 'r') as archive:
            for member in archive.infolist():
                normalized_name = normalize_archive_name(member.filename)
                if not normalized_name:
                    continue
                destination = safe_destination(gtasa_root, normalized_name)
                copy_zip_member(archive, member, destination, overwrite=False)
    except (OSError, zipfile.BadZipFile) as error:
        raise RuntimeError(f"Could not install the bundled SA-MP client files: {error}") from error

    return True



def create_local_test_scaffold(package_root):
    server_root = package_root / TEST_SERVER_DIRECTORY_NAME

    try:
        package_root.mkdir(parents=True, exist_ok=True)
        server_root.mkdir(parents=True, exist_ok=True)

        for directory in (
            server_root / "gamemodes",
            server_root / "filterscripts",
            server_root / "models",
            server_root / "plugins",
            server_root / "scriptfiles",
            server_root / "pawno",
            server_root / "pawno" / "include",
        ):
            directory.mkdir(parents=True, exist_ok=True)
    except PermissionError as error:
        raise RuntimeError(
            f"Windows denied write access to {package_root}. "
            "Check that your Blender user folder is writable."
        ) from error
    except OSError as error:
        raise RuntimeError(f"Could not create the local model-test package: {error}") from error

    template_root = get_addon_root() / "local_test_package" / GTASA_DIRECTORY_NAME

    if template_root.is_dir():
        for source in template_root.rglob("*"):
            relative_path = source.relative_to(template_root)
            destination = package_root / relative_path

            try:
                if source.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif source.is_file() and not destination.exists():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
            except OSError:
                pass

    return package_root


def get_local_test_root(create=False):
    gtasa_root = get_blender_user_root() / GTASA_DIRECTORY_NAME

    if create:
        return create_local_test_scaffold(gtasa_root)

    if not gtasa_root.is_dir():
        raise RuntimeError(
            f"The required local test package folder does not exist: {gtasa_root}. "
            "Create or extract the GTASA package in Blender's user folder."
        )

    return gtasa_root


def clean_generated_test_files():
    try:
        package_root = get_local_test_root(create=False)
    except RuntimeError:
        return 0, 0

    server_roots = [get_test_server_root(package_root)]
    server_executable = find_server_executable(package_root)
    if server_executable is not None:
        executable_root = server_executable.parent
        if executable_root not in server_roots:
            server_roots.append(executable_root)

    removed_count = 0
    removed_bytes = 0
    visited_paths = set()

    def remove_file(path):
        nonlocal removed_count
        nonlocal removed_bytes

        path = Path(path)
        try:
            path_key = os.path.normcase(str(path.resolve()))
        except OSError:
            path_key = os.path.normcase(str(path.absolute()))

        if path_key in visited_paths:
            return
        visited_paths.add(path_key)

        try:
            if not path.is_file():
                return
            removed_bytes += path.stat().st_size
            path.unlink()
            removed_count += 1
        except OSError:
            pass

    for server_root in server_roots:
        models_directory = server_root / "models"
        scriptfiles_directory = server_root / "scriptfiles"

        for pattern in (
            f"{TEST_MODEL_NAME}*.dff",
            f"{TEST_MODEL_NAME}*.txd",
            *GENERATED_TEST_MODEL_PATTERNS,
        ):
            if models_directory.is_dir():
                for generated_model in models_directory.glob(pattern):
                    remove_file(generated_model)

        for generated_state in (
            scriptfiles_directory / LIVE_TRANSFORM_FILE_NAME,
            scriptfiles_directory / PLAYER_STATE_FILE_NAME,
            scriptfiles_directory / TEST_MODEL_DEFINITION_FILE_NAME,
            scriptfiles_directory / TEST_PLACEMENT_FILE_NAME,
        ):
            remove_file(generated_state)

        for log_name in (
            "demonff_server_console.log",
            "demonff_openmp_server.log",
            "server_log.txt",
            "log-core.log",
            "demonff_client_launch.log",
        ):
            remove_file(server_root / log_name)

        if not server_root.is_dir():
            continue

        for temporary_file in server_root.rglob("*"):
            if not temporary_file.is_file():
                continue
            if not (
                temporary_file.name.endswith(".demonff_tmp")
                or temporary_file.name.endswith(".part")
            ):
                continue
            remove_file(temporary_file)

    return removed_count, removed_bytes


def format_byte_count(byte_count):
    size = float(max(0, byte_count))
    units = ("bytes", "KB", "MB", "GB", "TB")
    unit_index = 0

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.2f} {units[unit_index]}"


def get_test_server_root(gtasa_root):
    return gtasa_root / TEST_SERVER_DIRECTORY_NAME


def find_file_case_insensitive(directory, names):
    if directory is None or not directory.is_dir():
        return None

    wanted = {name.lower() for name in names}
    try:
        entries = tuple(directory.iterdir())
    except OSError:
        return None

    for entry in entries:
        try:
            if entry.is_file() and entry.name.lower() in wanted:
                return entry
        except OSError:
            continue
    return None


def find_file_bounded(directory, names, maximum_depth=3, skipped_directories=()):
    if directory is None or not directory.is_dir():
        return None

    wanted = {name.lower() for name in names}
    skipped = {name.lower() for name in skipped_directories}
    root_depth = len(directory.parts)

    try:
        walker = os.walk(directory)
    except OSError:
        return None

    for current_root_text, directory_names, file_names in walker:
        current_root = Path(current_root_text)
        depth = len(current_root.parts) - root_depth

        directory_names[:] = [
            name
            for name in directory_names
            if name.lower() not in skipped and depth < maximum_depth
        ]

        for file_name in file_names:
            if file_name.lower() in wanted:
                return current_root / file_name

        if depth >= maximum_depth:
            directory_names[:] = []

    return None


def unique_existing_directories(paths):
    directories = []
    seen = set()

    for path in paths:
        if path is None:
            continue

        try:
            normalized = Path(path).expanduser().resolve()
        except OSError:
            normalized = Path(path).expanduser().absolute()

        key = os.path.normcase(str(normalized))
        if key in seen or not normalized.is_dir():
            continue

        seen.add(key)
        directories.append(normalized)

    return directories


def get_server_search_roots(gtasa_root):
    default_server_root = get_test_server_root(gtasa_root)
    return unique_existing_directories((
        default_server_root,
        gtasa_root / "open.mp",
        gtasa_root / "openmp",
        gtasa_root / "omp",
        gtasa_root / "server",
        gtasa_root,
    ))


def find_server_executable(gtasa_root):
    search_roots = get_server_search_roots(gtasa_root)
    skipped = (
        DOWNLOAD_CACHE_DIRECTORY_NAME,
        "audio",
        "anim",
        "data",
        "models",
        "text",
    )

    for executable_names in (OMP_SERVER_EXECUTABLE_NAMES, SAMP_SERVER_EXECUTABLE_NAMES):
        for root in search_roots:
            executable = find_file_case_insensitive(root, executable_names)
            if executable is not None:
                return executable

        for root in search_roots:
            executable = find_file_bounded(
                root,
                executable_names,
                maximum_depth=3,
                skipped_directories=skipped,
            )
            if executable is not None:
                return executable

    return None



def get_openmp_launcher_search_roots(gtasa_root, package_root=None):
    local_app_data = os.environ.get("LOCALAPPDATA")
    roaming_app_data = os.environ.get("APPDATA")
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")

    roots = [
        gtasa_root,
        gtasa_root / "open.mp",
        gtasa_root / "openmp",
        gtasa_root / "omp",
    ]

    if local_app_data:
        local_root = Path(local_app_data)
        roots.extend((
            local_root / "Programs" / "open.mp Launcher",
            local_root / "Programs" / "open.mp",
            local_root / "mp.open.launcher",
            local_root / "Programs",
        ))

    if roaming_app_data:
        roots.append(Path(roaming_app_data) / "mp.open.launcher")

    if program_files:
        roots.extend((
            Path(program_files) / "open.mp Launcher",
            Path(program_files) / "open.mp",
        ))

    if program_files_x86:
        roots.extend((
            Path(program_files_x86) / "open.mp Launcher",
            Path(program_files_x86) / "open.mp",
        ))

    if package_root is not None:
        roots.extend((
            package_root,
            package_root / "open.mp",
            package_root / "openmp",
            package_root / "omp",
        ))

    return unique_existing_directories(roots)


def find_openmp_client_executable(gtasa_root, package_root=None):
    search_roots = get_openmp_launcher_search_roots(gtasa_root, package_root)
    skipped = (
        DOWNLOAD_CACHE_DIRECTORY_NAME,
        "audio",
        "anim",
        "data",
        "models",
        "text",
    )

    for root in search_roots:
        executable = find_file_case_insensitive(root, OMP_CLIENT_EXECUTABLE_NAMES)
        if executable is not None:
            return executable

    for root in search_roots:
        executable = find_file_bounded(
            root,
            OMP_CLIENT_EXECUTABLE_NAMES,
            maximum_depth=3,
            skipped_directories=skipped,
        )
        if executable is not None:
            return executable

    executable_from_path = shutil.which("omp-launcher.exe")
    if executable_from_path:
        executable_path = Path(executable_from_path)
        if executable_path.is_file():
            return executable_path

    return None


def find_samp_client_executable(gtasa_root, package_root=None):
    roots = []
    if package_root is not None:
        roots.append(package_root)
    roots.append(gtasa_root)

    for root in unique_existing_directories(roots):
        samp_client = find_file_case_insensitive(root, SAMP_CLIENT_EXECUTABLE_NAMES)
        if samp_client is not None:
            return samp_client

    for root in unique_existing_directories(roots):
        samp_client = find_file_bounded(
            root,
            SAMP_CLIENT_EXECUTABLE_NAMES,
            maximum_depth=2,
            skipped_directories=(
                DOWNLOAD_CACHE_DIRECTORY_NAME,
                TEST_SERVER_DIRECTORY_NAME,
                "audio",
                "anim",
                "data",
                "models",
                "text",
            ),
        )
        if samp_client is not None:
            return samp_client

    return None


def resolve_configured_client_executable(configured_executable):
    configured = normalize_directory_path(configured_executable)
    if configured is None:
        return None

    if not configured.is_file():
        raise RuntimeError(
            f"The selected Multiplayer Launcher does not exist: {configured}"
        )

    valid_names = {
        name.lower()
        for name in OMP_CLIENT_EXECUTABLE_NAMES + SAMP_CLIENT_EXECUTABLE_NAMES
    }
    if configured.name.lower() not in valid_names:
        raise RuntimeError(
            "Multiplayer Launcher must be omp-launcher.exe or samp.exe."
        )

    return configured



def find_client_executables(gtasa_root, package_root=None, configured_executable=None):
    configured = resolve_configured_client_executable(configured_executable)

    if configured is not None:
        configured_is_old_package_copy = (
            package_root is not None
            and path_is_within(configured, package_root)
        )

        if not configured_is_old_package_copy:
            return configured, None

    openmp_client = find_openmp_client_executable(gtasa_root, None)
    if openmp_client is not None:
        return openmp_client, None

    samp_client = find_samp_client_executable(gtasa_root, None)
    if samp_client is not None:
        return samp_client, None

    if configured is not None:
        return configured, None

    return None, None



def get_default_multiplayer_launcher_text():
    try:
        game_root = find_preferred_gtasa_game_root()
    except Exception:
        return ""

    if game_root is None:
        return ""

    client_executable, _ = find_client_executables(
        game_root,
        None,
    )
    return str(client_executable) if client_executable is not None else ""


def executable_kind(executable, openmp_names):
    if executable is None:
        return "unknown"
    return "open.mp" if executable.name.lower() in {name.lower() for name in openmp_names} else "SA-MP"


def find_pawn_compiler(server_root):
    for editor_directory_name in ("qawno", "pawno"):
        editor_root = server_root / editor_directory_name
        compiler = find_file_case_insensitive(editor_root, ("pawncc.exe",))
        include_directory = editor_root / "include"

        if compiler is not None and include_directory.is_dir():
            return compiler, include_directory

    compiler = find_file_bounded(
        server_root,
        ("pawncc.exe",),
        maximum_depth=3,
        skipped_directories=(
            DOWNLOAD_CACHE_DIRECTORY_NAME,
            "gamemodes",
            "filterscripts",
            "models",
            "plugins",
            "scriptfiles",
        ),
    )

    if compiler is not None:
        include_directory = compiler.parent / "include"
        if include_directory.is_dir():
            return compiler, include_directory

    return None, None


def find_pawn_include_name(server_executable, include_directory):
    if include_directory is None:
        return None

    openmp_include = find_file_case_insensitive(include_directory, ("open.mp.inc",))
    samp_include = find_file_case_insensitive(include_directory, ("a_samp.inc",))
    server_is_openmp = executable_kind(server_executable, OMP_SERVER_EXECUTABLE_NAMES) == "open.mp"

    if server_is_openmp and openmp_include is not None:
        return "open.mp"
    if samp_include is not None:
        return "a_samp"
    if openmp_include is not None:
        return "open.mp"
    return None


def build_request(url):
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": DOWNLOAD_USER_AGENT,
            "Accept": "application/octet-stream, application/zip, application/json",
        },
    )


def ensure_online_access():
    if hasattr(bpy.app, "online_access") and not bpy.app.online_access:
        raise RuntimeError(
            "Blender Online Access is disabled. Enable Online Access before downloading SA-MP test runtime components."
        )


def download_to_file(url, destination):
    ensure_online_access()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(destination.name + ".part")

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with urllib.request.urlopen(build_request(url), timeout=120) as response:
            with open(temporary_path, 'wb') as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
        if temporary_path.exists():
            temporary_path.unlink()
        raise RuntimeError(f"Could not download {url}: {error}") from error

    if not temporary_path.is_file() or temporary_path.stat().st_size < 1024:
        if temporary_path.exists():
            temporary_path.unlink()
        raise RuntimeError(f"The downloaded file from {url} was empty or incomplete.")

    os.replace(temporary_path, destination)
    return destination


def download_from_urls(urls, destination):
    errors = []

    for url in urls:
        try:
            return download_to_file(url, destination)
        except RuntimeError as error:
            errors.append(str(error))

    detail = errors[-1] if errors else "No download URL was available."
    raise RuntimeError(detail)


def read_json_url(url):
    ensure_online_access()
    try:
        with urllib.request.urlopen(build_request(url), timeout=60) as response:
            raw_data = response.read()
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
        raise RuntimeError(f"Could not read {url}: {error}") from error

    try:
        return json.loads(raw_data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"The response from {url} was not valid JSON.") from error


def get_streamer_download_urls():
    urls = []

    try:
        release_data = read_json_url(STREAMER_RELEASE_API_URL)
        for asset in release_data.get("assets", []):
            name = str(asset.get("name", "")).lower()
            download_url = str(asset.get("browser_download_url", ""))
            if name.endswith('.zip') and 'streamer' in name and download_url:
                urls.append(download_url)
                break
    except RuntimeError:
        pass

    if STREAMER_FALLBACK_DOWNLOAD_URL not in urls:
        urls.append(STREAMER_FALLBACK_DOWNLOAD_URL)

    return tuple(urls)


def archive_is_readable(path):
    if not path.is_file() or path.stat().st_size < 1024:
        return False

    try:
        with zipfile.ZipFile(path, 'r') as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def find_archive_member(archive, filename, preferred_parts=()):
    filename_lower = filename.lower()
    candidates = []

    for member in archive.infolist():
        normalized_name = normalize_archive_name(member.filename)
        if not normalized_name or member.is_dir():
            continue

        parts = tuple(part.lower() for part in PurePosixPath(normalized_name).parts)
        if parts and parts[-1] == filename_lower:
            score = sum(1 for part in preferred_parts if part.lower() in parts)
            candidates.append((score, len(parts), member))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1], item[2].filename.lower()))
    return candidates[0][2]


def install_samp_server_archive(archive_path, server_root):
    try:
        with zipfile.ZipFile(archive_path, 'r') as archive:
            executable_member = find_archive_member(archive, "samp-server.exe")
            if executable_member is None:
                raise RuntimeError("The SA-MP server archive does not contain samp-server.exe.")

            executable_name = normalize_archive_name(executable_member.filename)
            prefix_parts = PurePosixPath(executable_name).parts[:-1]

            for member in archive.infolist():
                normalized_name = normalize_archive_name(member.filename)
                if not normalized_name:
                    continue

                member_parts = PurePosixPath(normalized_name).parts
                if prefix_parts and member_parts[:len(prefix_parts)] != prefix_parts:
                    continue

                relative_parts = member_parts[len(prefix_parts):]
                if not relative_parts:
                    continue

                relative_name = '/'.join(relative_parts)
                destination = safe_destination(server_root, relative_name)
                copy_zip_member(archive, member, destination, overwrite=False)
    except zipfile.BadZipFile as error:
        raise RuntimeError("The downloaded SA-MP server archive is not a valid ZIP file.") from error


def install_streamer_archive(archive_path, server_root, include_directory):
    try:
        with zipfile.ZipFile(archive_path, 'r') as archive:
            plugin_member = find_archive_member(
                archive,
                "streamer.dll",
                preferred_parts=("plugins", "windows", "win32"),
            )
            include_member = find_archive_member(
                archive,
                "streamer.inc",
                preferred_parts=("pawno", "qawno", "include"),
            )

            if plugin_member is None or include_member is None:
                raise RuntimeError(
                    "The Streamer package does not contain both streamer.dll and streamer.inc."
                )

            copy_zip_member(
                archive,
                plugin_member,
                server_root / "plugins" / "streamer.dll",
                overwrite=True,
            )
            copy_zip_member(
                archive,
                include_member,
                include_directory / "streamer.inc",
                overwrite=True,
            )
    except zipfile.BadZipFile as error:
        raise RuntimeError("The downloaded Streamer archive is not a valid ZIP file.") from error


def pawn_runtime_is_complete(server_executable, server_root):
    compiler, include_directory = find_pawn_compiler(server_root)
    include_name = find_pawn_include_name(server_executable, include_directory)
    return bool(compiler and include_directory and include_name)


def streamer_runtime_is_complete(server_root, include_directory):
    if include_directory is None:
        return False

    include_path = find_file_case_insensitive(include_directory, ("streamer.inc",))
    plugin_path = find_file_case_insensitive(server_root / "plugins", ("streamer.dll",))
    return include_path is not None and plugin_path is not None


def get_samp_server_archive(gtasa_root):
    cache_root = gtasa_root / DOWNLOAD_CACHE_DIRECTORY_NAME
    archive_path = cache_root / SAMP_SERVER_ARCHIVE_NAME

    if not archive_is_readable(archive_path):
        if archive_path.exists():
            archive_path.unlink()
        download_from_urls(SAMP_SERVER_DOWNLOAD_URLS, archive_path)

    return archive_path


def ensure_server_and_pawn_runtime(gtasa_root):
    server_executable = find_server_executable(gtasa_root)
    server_root = server_executable.parent if server_executable is not None else get_test_server_root(gtasa_root)

    if server_executable is None or not pawn_runtime_is_complete(server_executable, server_root):
        archive_path = get_samp_server_archive(gtasa_root)
        install_samp_server_archive(archive_path, server_root)
        server_executable = find_server_executable(gtasa_root)

    if server_executable is None:
        raise RuntimeError(
            "DemonFF could not find omp-server.exe or samp-server.exe after installing the local test server."
        )

    server_root = server_executable.parent
    if not pawn_runtime_is_complete(server_executable, server_root):
        archive_path = get_samp_server_archive(gtasa_root)
        install_samp_server_archive(archive_path, server_root)

    if not pawn_runtime_is_complete(server_executable, server_root):
        raise RuntimeError(
            "The local test server is present, but pawncc.exe and its a_samp.inc or open.mp.inc include are missing."
        )

    return server_executable, server_root


def ensure_streamer_runtime(gtasa_root, server_root, include_directory):
    if streamer_runtime_is_complete(server_root, include_directory):
        return

    cache_root = gtasa_root / DOWNLOAD_CACHE_DIRECTORY_NAME
    archive_path = cache_root / STREAMER_ARCHIVE_NAME

    if not archive_is_readable(archive_path):
        if archive_path.exists():
            archive_path.unlink()
        download_from_urls(get_streamer_download_urls(), archive_path)

    install_streamer_archive(archive_path, server_root, include_directory)

    if not streamer_runtime_is_complete(server_root, include_directory):
        raise RuntimeError(
            "Streamer downloaded, but streamer.dll or streamer.inc was still missing."
        )



def validate_local_runtime(
    package_root,
    source_game_root,
    server_executable=None,
    configured_client_executable=None,
):
    missing = []

    valid_source_root, source_root_error = validate_gtasa_game_root(source_game_root)
    if not valid_source_root:
        missing.append(source_root_error)

    if package_root is None or not package_root.is_dir():
        missing.append(f"DemonFF's writable test folder does not exist: {package_root}")

    client_executable, fallback_client_executable = find_client_executables(
        source_game_root,
        package_root,
        configured_client_executable,
    )
    if client_executable is None:
        missing.append(
            "Multiplayer Launcher: omp-launcher.exe or samp.exe. "
            "Select it in DemonFF - SAMP I/O."
        )

    if server_executable is None:
        server_executable = find_server_executable(package_root)

    if server_executable is None:
        missing.append(r"DemonFFTestServer\omp-server.exe or samp-server.exe")
        server_root = get_test_server_root(package_root)
    else:
        server_root = server_executable.parent

    pawn_compiler, include_directory = find_pawn_compiler(server_root)
    if pawn_compiler is None:
        missing.append(str(server_root / "qawno or pawno" / "pawncc.exe"))

    pawn_include_name = find_pawn_include_name(server_executable, include_directory)
    if pawn_include_name is None:
        missing.append(str(server_root / "qawno or pawno" / "include" / "a_samp.inc or open.mp.inc"))

    if include_directory is None or find_file_case_insensitive(include_directory, ("streamer.inc",)) is None:
        missing.append(str(server_root / "qawno or pawno" / "include" / "streamer.inc"))

    streamer_plugin = find_file_case_insensitive(
        server_root / "plugins",
        ("streamer.dll",),
    )
    if streamer_plugin is None:
        missing.append(str(server_root / "plugins" / "streamer.dll"))

    if missing:
        missing_text = "\n - ".join(str(item) for item in missing if item)
        raise RuntimeError(
            "The automatic local model-test package could not finish installing. Missing:\n - "
            f"{missing_text}"
        )

    return LocalRuntime(
        gtasa_root=source_game_root,
        source_game_root=source_game_root,
        package_root=package_root,
        server_root=server_root,
        server_executable=server_executable,
        server_kind=executable_kind(server_executable, OMP_SERVER_EXECUTABLE_NAMES),
        client_executable=client_executable,
        client_kind=executable_kind(client_executable, OMP_CLIENT_EXECUTABLE_NAMES),
        fallback_client_executable=fallback_client_executable,
        pawn_compiler=pawn_compiler,
        include_directory=include_directory,
        pawn_include_name=pawn_include_name,
        streamer_plugin=streamer_plugin,
    )



def local_runtime_cache_key(package_root, source_game_root, configured_client_executable):
    values = []
    for value in (package_root, source_game_root, configured_client_executable):
        if value is None:
            values.append("")
            continue
        try:
            normalized = Path(value).expanduser().absolute()
            values.append(os.path.normcase(os.path.normpath(str(normalized))))
        except Exception:
            values.append(os.path.normcase(os.path.normpath(str(value))))
    return tuple(values)


def local_runtime_cache_is_usable(runtime):
    if runtime is None:
        return False

    required_files = (
        runtime.server_executable,
        runtime.client_executable,
        runtime.pawn_compiler,
        runtime.streamer_plugin,
    )
    if any(path is None or not Path(path).is_file() for path in required_files):
        return False

    if runtime.include_directory is None or not Path(runtime.include_directory).is_dir():
        return False

    include_name = str(runtime.pawn_include_name or "").strip()
    if not include_name:
        return False

    return True


def ensure_local_runtime(
    package_root,
    source_game_root,
    configured_client_executable=None,
):
    global LOCAL_RUNTIME_CACHE_KEY
    global LOCAL_RUNTIME_CACHE_VALUE

    package_root = normalize_directory_path(package_root)
    source_game_root = normalize_directory_path(source_game_root)
    if package_root is None:
        raise RuntimeError("DemonFF could not resolve its writable local test folder.")
    if source_game_root is None:
        raise RuntimeError("DemonFF could not resolve the GTA San Andreas Game Root.")

    valid_source_root, source_error = validate_gtasa_game_root(source_game_root)
    if not valid_source_root:
        source_game_root = resolve_gtasa_game_root(source_game_root)

    cache_key = local_runtime_cache_key(
        package_root,
        source_game_root,
        configured_client_executable,
    )
    if (
        LOCAL_RUNTIME_CACHE_KEY == cache_key
        and local_runtime_cache_is_usable(LOCAL_RUNTIME_CACHE_VALUE)
    ):
        test_progress("Runtime check: reused the already validated local server/compiler paths")
        return LOCAL_RUNTIME_CACHE_VALUE

    test_progress("Runtime check: validating the reusable local test package")
    package_root = create_local_test_scaffold(package_root)
    server_executable, server_root = ensure_server_and_pawn_runtime(package_root)
    pawn_compiler, include_directory = find_pawn_compiler(server_root)
    ensure_streamer_runtime(package_root, server_root, include_directory)

    runtime = validate_local_runtime(
        package_root,
        source_game_root,
        server_executable,
        configured_client_executable,
    )
    LOCAL_RUNTIME_CACHE_KEY = cache_key
    LOCAL_RUNTIME_CACHE_VALUE = runtime
    test_progress("Runtime check: server, compiler, streamer, and launcher are ready")
    return runtime


def get_udp_port_process_ids(port):
    if os.name != "nt":
        return []

    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "udp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        return []

    process_ids = []
    suffix = f":{int(port)}"

    for line in result.stdout.splitlines():
        columns = line.split()
        if len(columns) < 4 or columns[0].upper() != "UDP":
            continue

        local_address = columns[1]
        if not local_address.endswith(suffix):
            continue

        try:
            process_id = int(columns[-1])
        except ValueError:
            continue

        if process_id > 0 and process_id != os.getpid() and process_id not in process_ids:
            process_ids.append(process_id)

    return process_ids


def get_process_name_by_id(process_id):
    if os.name != "nt" or not process_id:
        return ""

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {process_id}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        return ""

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("INFO:"):
            continue
        return stripped.lstrip('"').split('",', 1)[0]
    return ""


def kill_process_id(process_id):
    if os.name != "nt" or not process_id:
        return False

    result = subprocess.run(
        ["taskkill", "/F", "/PID", str(process_id)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def release_local_test_port():
    killed_any = False
    allowed_names = {
        name.lower()
        for name in OMP_SERVER_EXECUTABLE_NAMES + SAMP_SERVER_EXECUTABLE_NAMES
    }

    for process_id in get_udp_port_process_ids(LOCAL_PORT):
        process_name = get_process_name_by_id(process_id).lower()
        if process_name not in allowed_names:
            continue
        if kill_process_id(process_id):
            killed_any = True

    if killed_any:
        time.sleep(0.75)


def udp_port_is_available(host=LOCAL_HOST, port=LOCAL_PORT):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        test_socket.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        test_socket.close()


def read_server_log_tail(log_path, maximum_lines=20):
    try:
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    return "\n".join(lines[-maximum_lines:])


def server_log_failure_detail(log_path):
    log_tail = read_server_log_tail(log_path, maximum_lines=30)
    if not log_tail:
        return ""

    failure_phrases = (
        "unable to start server",
        "address already in use",
        "failed to bind",
        "runtime error",
        "script[gamemodes/",
        "could not load",
    )

    for line in reversed(log_tail.splitlines()):
        lowered = line.lower()
        if any(phrase in lowered for phrase in failure_phrases):
            return line

    return ""


def get_object_world_components(obj):
    location, rotation, scale = obj.matrix_world.decompose()
    if rotation.magnitude > 1.0e-12:
        rotation.normalize()
    return location, rotation, scale


def get_object_world_transform(obj, base_rotation=None):
    location, rotation, _scale = get_object_world_components(obj)
    if base_rotation is not None:
        rotation = rotation @ base_rotation.inverted()

    rotation_degrees = quaternion_to_gta_euler_degrees(rotation)
    return (
        float(location.x),
        float(location.y),
        float(location.z),
        float(rotation_degrees[0]),
        float(rotation_degrees[1]),
        float(rotation_degrees[2]),
    )


def get_test_object_dff_type(obj):
    if obj is None:
        return ""
    try:
        return str(getattr(getattr(obj, "dff", None), "type", "") or "")
    except Exception:
        return ""


def is_test_effect_helper_object(obj):
    return get_test_object_dff_type(obj) == "2DFX"


def resolve_effect_live_anchor(effect_object, export_set):
    current = effect_object
    while current is not None:
        current = getattr(current, "parent", None)
        if current is None:
            break
        if current not in export_set:
            continue
        dff_type = get_test_object_dff_type(current)
        if dff_type == "OBJ" and current.type in {"MESH", "EMPTY", "ARMATURE"}:
            return current

    source_keys = []
    for key in (
        "demonff_2dfx_source_model_key",
        "demonff_2dfx_source_model",
        "DFF_Name",
    ):
        try:
            value = str(effect_object.get(key, "") or "").strip()
        except Exception:
            value = ""
        if value:
            source_keys.append(re.sub(r"\.dff$", "", value, flags=re.IGNORECASE).lower())

    if source_keys:
        for candidate in export_set:
            if get_test_object_dff_type(candidate) != "OBJ":
                continue
            candidate_names = [getattr(candidate, "name", "")]
            for key in (
                "demonff_2dfx_source_model_key",
                "demonff_2dfx_source_model",
                "DFF_Name",
            ):
                try:
                    candidate_names.append(str(candidate.get(key, "") or ""))
                except Exception:
                    pass
            normalized_names = {
                re.sub(r"\.\d{3,}$", "", re.sub(r"\.dff$", "", str(name), flags=re.IGNORECASE)).lower()
                for name in candidate_names
                if str(name).strip()
            }
            if any(source_key in normalized_names for source_key in source_keys):
                return candidate

    return None


def choose_live_test_anchor(context, export_objects):
    export_set = set(export_objects)
    active_object = context.view_layer.objects.active

    if active_object in export_set:
        if is_test_effect_helper_object(active_object):
            resolved = resolve_effect_live_anchor(active_object, export_set)
            if resolved is not None:
                return resolved
        else:
            return active_object

    selected = [obj for obj in context.selected_objects if obj in export_set]
    for selected_object in selected:
        if is_test_effect_helper_object(selected_object):
            resolved = resolve_effect_live_anchor(selected_object, export_set)
            if resolved is not None:
                return resolved
            continue
        return selected_object

    mesh_objects = [
        obj for obj in export_objects
        if obj.type == "MESH" and get_test_object_dff_type(obj) == "OBJ"
    ]
    if mesh_objects:
        return mesh_objects[0]

    non_effect_objects = [
        obj for obj in export_objects
        if not is_test_effect_helper_object(obj)
    ]
    return non_effect_objects[0] if non_effect_objects else export_objects[0]


def set_test_transform_from_object(obj):
    global TEST_MODEL_POSITION
    global TEST_MODEL_ROTATION
    global LIVE_TEST_BASE_ROTATION

    location, rotation, _scale = get_object_world_components(obj)
    LIVE_TEST_BASE_ROTATION = rotation.copy()
    TEST_MODEL_POSITION = (
        float(location.x),
        float(location.y),
        float(location.z),
    )
    TEST_MODEL_ROTATION = (0.0, 0.0, 0.0)
    return TEST_MODEL_POSITION + TEST_MODEL_ROTATION


def get_test_model_transform():
    return tuple(TEST_MODEL_POSITION) + tuple(TEST_MODEL_ROTATION)


def build_samp_rcon_packet(host, port, password, command):
    address_bytes = socket.inet_aton(host)
    password_bytes = str(password).encode("latin-1", errors="replace")
    command_bytes = str(command).encode("latin-1", errors="replace")

    return (
        b"SAMP"
        + address_bytes
        + struct.pack("<H", int(port))
        + b"x"
        + struct.pack("<H", len(password_bytes))
        + password_bytes
        + struct.pack("<H", len(command_bytes))
        + command_bytes
    )


def send_local_rcon_command(command):
    packet = build_samp_rcon_packet(
        LOCAL_HOST,
        LOCAL_PORT,
        LOCAL_RCON_PASSWORD,
        command,
    )
    rcon_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        rcon_socket.settimeout(0.1)
        rcon_socket.sendto(packet, (LOCAL_HOST, LOCAL_PORT))
    finally:
        rcon_socket.close()


def write_live_transform_file_for_root(server_root, transform):
    global LIVE_TEST_REVISION

    if server_root is None:
        return False

    scriptfiles_directory = Path(server_root) / "scriptfiles"
    scriptfiles_directory.mkdir(parents=True, exist_ok=True)

    LIVE_TEST_REVISION += 1
    values = " ".join(pawn_float(value) for value in transform)
    contents = f"{LIVE_TEST_REVISION} {values}\n"

    destination = scriptfiles_directory / LIVE_TRANSFORM_FILE_NAME
    destination.write_text(contents, encoding="ascii", newline="\n")
    return True


def write_live_transform_file(transform):
    return write_live_transform_file_for_root(SERVER_ROOT, transform)


def send_live_transform(transform):
    try:
        write_live_transform_file(transform)
    except OSError:
        pass

    command = "demonff_transform " + " ".join(
        pawn_float(value) for value in transform
    )
    try:
        send_local_rcon_command(command)
    except OSError:
        pass


def stop_live_transform_sync():
    global LIVE_TEST_OBJECT
    global LIVE_TEST_LAST_TRANSFORM
    global LIVE_TEST_ACTIVE

    LIVE_TEST_ACTIVE = False
    LIVE_TEST_OBJECT = None
    LIVE_TEST_LAST_TRANSFORM = None

    try:
        if bpy.app.timers.is_registered(live_transform_timer):
            bpy.app.timers.unregister(live_transform_timer)
    except Exception:
        pass


def live_transform_timer():
    global LIVE_TEST_LAST_TRANSFORM
    global LIVE_TEST_ACTIVE

    if not LIVE_TEST_ACTIVE:
        return None

    if SERVER_PROCESS is None or SERVER_PROCESS.poll() is not None:
        LIVE_TEST_ACTIVE = False
        return None

    try:
        transform = get_object_world_transform(
            LIVE_TEST_OBJECT,
            LIVE_TEST_BASE_ROTATION,
        )
    except (ReferenceError, AttributeError, RuntimeError):
        LIVE_TEST_ACTIVE = False
        return None

    rounded_transform = tuple(round(value, 5) for value in transform)
    if rounded_transform != LIVE_TEST_LAST_TRANSFORM:
        LIVE_TEST_LAST_TRANSFORM = rounded_transform
        send_live_transform(transform)

    return LIVE_TRANSFORM_INTERVAL


def start_live_transform_sync(obj):
    global LIVE_TEST_OBJECT
    global LIVE_TEST_LAST_TRANSFORM
    global LIVE_TEST_ACTIVE
    global LIVE_TEST_BASE_ROTATION

    stop_live_transform_sync()
    LIVE_TEST_OBJECT = obj
    if LIVE_TEST_BASE_ROTATION is None:
        _location, rotation, _scale = get_object_world_components(obj)
        LIVE_TEST_BASE_ROTATION = rotation.copy()

    transform = get_object_world_transform(obj, LIVE_TEST_BASE_ROTATION)
    LIVE_TEST_LAST_TRANSFORM = tuple(round(value, 5) for value in transform)
    LIVE_TEST_ACTIVE = True

    try:
        send_live_transform(transform)
        bpy.app.timers.register(
            live_transform_timer,
            first_interval=LIVE_TRANSFORM_INTERVAL,
            persistent=False,
        )
    except Exception:
        LIVE_TEST_ACTIVE = False
        LIVE_TEST_OBJECT = None
        raise


def collection_contains_child(parent_collection, child_collection):
    try:
        return child_collection.name in parent_collection.children
    except (ReferenceError, RuntimeError, AttributeError):
        return False


def collection_contains_object(collection, obj):
    try:
        return obj.name in collection.objects
    except (ReferenceError, RuntimeError, AttributeError):
        return False


def get_player_tracker_collection(context):
    collection = bpy.data.collections.get(PLAYER_TRACKER_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(PLAYER_TRACKER_COLLECTION_NAME)

    if not collection_contains_child(context.scene.collection, collection):
        try:
            context.scene.collection.children.link(collection)
        except RuntimeError:
            pass

    return collection


def create_player_tracker_object(context):
    collection = get_player_tracker_collection(context)
    tracker = bpy.data.objects.get(PLAYER_TRACKER_OBJECT_NAME)

    if tracker is None:
        tracker = bpy.data.objects.new(PLAYER_TRACKER_OBJECT_NAME, None)
        tracker.empty_display_type = "ARROWS"
        tracker.empty_display_size = 1.0
        tracker.show_in_front = True
        tracker.hide_render = True

    if not collection_contains_object(collection, tracker):
        try:
            collection.objects.link(tracker)
        except RuntimeError:
            pass

    return tracker


def resolve_player_sync_target(context):
    global PLAYER_SYNC_CREATED_TARGET

    target = getattr(context.scene.dff, "samp_player_target", None)
    if target is not None:
        PLAYER_SYNC_CREATED_TARGET = False
        return target

    target = create_player_tracker_object(context)
    set_configured_player_sync_target(context, target)
    PLAYER_SYNC_CREATED_TARGET = True
    return target


def set_player_follow_view(target, enabled):
    window_manager = getattr(bpy.context, "window_manager", None)
    if window_manager is None:
        return

    for window in window_manager.windows:
        screen = window.screen
        if screen is None:
            continue

        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue

            try:
                space = area.spaces.active
                if enabled:
                    space.lock_object = target
                elif space.lock_object == target:
                    space.lock_object = None
            except Exception:
                pass


def get_player_state_path():
    if SERVER_ROOT is None:
        return None
    return Path(SERVER_ROOT) / "scriptfiles" / PLAYER_STATE_FILE_NAME


def read_player_state():
    state_path = get_player_state_path()
    if state_path is None or not state_path.is_file():
        return None

    try:
        line = state_path.read_text(
            encoding="ascii",
            errors="replace",
        ).strip().splitlines()[-1]
    except (OSError, IndexError):
        return None

    tokens = line.split()
    if len(tokens) < 18:
        return None

    animation_start_tick = 0
    animation_library = ""
    animation_name = ""
    if len(tokens) >= 21:
        try:
            animation_start_tick = int(tokens[18])
        except (TypeError, ValueError):
            animation_start_tick = 0
        animation_library = "" if tokens[19] == "-" else tokens[19]
        animation_name = "" if tokens[20] == "-" else tokens[20]
    elif len(tokens) >= 20:
        animation_library = "" if tokens[18] == "-" else tokens[18]
        animation_name = "" if tokens[19] == "-" else tokens[19]

    try:
        return {
            "revision": int(tokens[0]),
            "tick": int(tokens[1]),
            "player_id": int(tokens[2]),
            "position": (
                float(tokens[3]),
                float(tokens[4]),
                float(tokens[5]),
            ),
            "angle": float(tokens[6]),
            "skin": int(tokens[7]),
            "keys": int(tokens[8]),
            "up_down": int(tokens[9]),
            "left_right": int(tokens[10]),
            "special_action": int(tokens[11]),
            "animation_index": int(tokens[12]),
            "in_vehicle": bool(int(tokens[13])),
            "vehicle_model": int(tokens[14]),
            "velocity": (
                float(tokens[15]),
                float(tokens[16]),
                float(tokens[17]),
            ),
            "animation_library": animation_library,
            "animation_name": animation_name,
            "animation_start_tick": animation_start_tick,
        }
    except (TypeError, ValueError):
        return None


def classify_player_motion(state):
    velocity = state["velocity"]
    horizontal_speed = math.sqrt(
        velocity[0] * velocity[0]
        + velocity[1] * velocity[1]
    )

    if state["in_vehicle"]:
        if horizontal_speed < 0.01:
            return "VEHICLE_IDLE", horizontal_speed
        return "VEHICLE_MOVING", horizontal_speed

    analog_movement = bool(state["up_down"] or state["left_right"])
    keys = int(state.get("keys", 0))
    if horizontal_speed < 0.015 and not analog_movement:
        return "IDLE", horizontal_speed
    if keys & SAMP_KEY_WALK:
        return "WALK", horizontal_speed
    if keys & SAMP_KEY_SPRINT:
        return "SPRINT", horizontal_speed
    if horizontal_speed < 0.08:
        return "WALK", horizontal_speed
    if horizontal_speed < 0.22:
        return "RUN", horizontal_speed
    return "SPRINT", horizontal_speed


def normalize_animation_identifier(value):
    return "".join(character.lower() for character in str(value) if character.isalnum())


def get_action_animation_identifier(action):
    try:
        explicit_name = action.get("DemonFF_IFP_Animation_Name", "")
    except (ReferenceError, RuntimeError, AttributeError):
        explicit_name = ""

    if explicit_name:
        return normalize_animation_identifier(explicit_name)

    action_name = action.name
    if action_name.rsplit(".", 1)[-1].isdigit():
        action_name = action_name.rsplit(".", 1)[0]
    if "::" in action_name:
        action_name = action_name.split("::")[-1]
    return normalize_animation_identifier(action_name)


def get_action_bone_compatibility(action, armature):
    if action is None or armature is None or armature.type != "ARMATURE":
        return 0.0

    bone_names = {bone.name for bone in armature.pose.bones}
    referenced_names = set()

    for curve in action.fcurves:
        data_path = curve.data_path
        prefix = 'pose.bones["'
        if not data_path.startswith(prefix):
            continue
        end_index = data_path.find('"]', len(prefix))
        if end_index < 0:
            continue
        referenced_names.add(data_path[len(prefix):end_index])

    if not referenced_names:
        return 0.0

    matching_names = sum(1 for name in referenced_names if name in bone_names)
    return matching_names / float(len(referenced_names))


def strip_generated_action_root_motion(action, armature):
    if action is None or armature is None:
        return

    root_bone_names = {
        bone.name
        for bone in armature.pose.bones
        if bone.parent is None or get_armature_bone_direct_id(bone.bone) == 0
    }
    if not root_bone_names:
        return

    prefix = 'pose.bones["'
    for curve in list(action.fcurves):
        data_path = curve.data_path
        if not data_path.endswith(".location") or not data_path.startswith(prefix):
            continue
        end_index = data_path.find('"]', len(prefix))
        if end_index < 0:
            continue
        bone_name = data_path[len(prefix):end_index]
        if bone_name in root_bone_names:
            action.fcurves.remove(curve)


def find_existing_animation_action(armature, animation_library, animation_name):
    wanted_name = normalize_animation_identifier(animation_name)
    wanted_library = normalize_animation_identifier(animation_library)
    if not wanted_name:
        return None

    best_action = None
    best_score = -1.0

    for action in bpy.data.actions:
        if get_action_animation_identifier(action) != wanted_name:
            continue

        try:
            action_library = normalize_animation_identifier(
                action.get("DemonFF_IFP_Package", "")
            )
        except (ReferenceError, RuntimeError, AttributeError):
            action_library = ""

        try:
            retarget_version = int(action.get("DemonFF_IFP_Retarget_Version", 0))
        except (TypeError, ValueError, AttributeError, ReferenceError, RuntimeError):
            retarget_version = 0
        if retarget_version != 2 or len(action.fcurves) == 0:
            continue

        compatibility = get_action_bone_compatibility(action, armature)
        if compatibility <= 0.0:
            continue

        score = compatibility
        if wanted_library and action_library == wanted_library:
            score += 1.0
        if armature.animation_data is not None and armature.animation_data.action == action:
            score += 0.25

        if score > best_score:
            best_action = action
            best_score = score

    return best_action


def get_bundled_ped_ifp_path():
    bundled_path = get_addon_root() / BUNDLED_PED_IFP_RELATIVE_PATH
    if bundled_path.is_file():
        return bundled_path
    return None


def get_player_ifp_path(game_root, animation_library):
    library_name = str(animation_library).strip()
    normalized_library = normalize_animation_identifier(library_name)

    if normalized_library == "ped":
        bundled_path = get_bundled_ped_ifp_path()
        if bundled_path is not None:
            return bundled_path

    root = normalize_directory_path(game_root)
    if root is None:
        return None

    candidates = []
    if library_name:
        candidates.append(("anim", library_name + ".ifp"))
    if normalized_library == "ped":
        candidates.append(("anim", "ped.ifp"))

    seen = set()
    for relative_parts in candidates:
        key = tuple(part.lower() for part in relative_parts)
        if key in seen:
            continue
        seen.add(key)
        path = find_case_insensitive_path(root, relative_parts)
        if path is not None and path.is_file():
            return path

    return None


def get_player_ifp_candidates(game_root, animation_library):
    library_name = str(animation_library or "").strip()
    candidates = []
    seen = set()

    def append_candidate(candidate_path):
        if candidate_path is None:
            return
        try:
            candidate_path = Path(candidate_path)
        except (TypeError, ValueError):
            return
        if not candidate_path.is_file():
            return
        try:
            key = str(candidate_path.resolve()).casefold()
        except OSError:
            key = str(candidate_path).casefold()
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate_path)

    # GetAnimationName can label an animation with a group such as FIGHT_A
    # even though the complete standard PED set is in ped.ifp. Always search
    # the supplied embedded package by the exact reported animation name.
    append_candidate(get_bundled_ped_ifp_path())

    root = normalize_directory_path(game_root)
    if root is not None:
        if library_name:
            append_candidate(
                find_case_insensitive_path(root, ("anim", library_name + ".ifp"))
            )
        append_candidate(find_case_insensitive_path(root, ("anim", "ped.ifp")))

    return candidates


def load_cached_ifp(ifp_path):
    cache_key = str(ifp_path)
    try:
        modified_time = ifp_path.stat().st_mtime_ns
    except OSError:
        return None

    cached = PLAYER_SYNC_IFP_CACHE.get(cache_key)
    if cached is not None and cached[0] == modified_time:
        return cached[1]

    from ..gui import ifp_ot

    loaded_ifp = ifp_ot.load_ifp(str(ifp_path))
    PLAYER_SYNC_IFP_CACHE[cache_key] = (modified_time, loaded_ifp)
    return loaded_ifp


def create_animation_action_from_ifp(armature, animation_library, animation_name):
    global PLAYER_SYNC_ANIMATION_STATUS

    if not PLAYER_SYNC_AUTO_LOAD_IFP:
        return None

    ifp_path = get_player_ifp_path(PLAYER_SYNC_GAME_ROOT, animation_library)
    if ifp_path is None:
        PLAYER_SYNC_ANIMATION_STATUS = (
            "No embedded or GTA SA IFP matched the reported animation library"
        )
        return None

    try:
        loaded_ifp = load_cached_ifp(ifp_path)
    except Exception as error:
        PLAYER_SYNC_ANIMATION_STATUS = f"Could not read {ifp_path.name}: {error}"
        return None

    wanted_name = normalize_animation_identifier(animation_name)
    animation = None
    for candidate in loaded_ifp.data.animations:
        if normalize_animation_identifier(candidate.name) == wanted_name:
            animation = candidate
            break

    if animation is None:
        PLAYER_SYNC_ANIMATION_STATUS = (
            f"{animation_library}:{animation_name} was not found in {ifp_path.name}"
        )
        return None

    try:
        from ..gui import ifp_ot

        keyframe_time_scale = 1.0 if loaded_ifp.version == "ANP3" else 30.0
        playback_fps = 30.0
        action, missing_bones = ifp_ot.create_action(
            armature,
            animation,
            keyframe_time_scale,
            mathutils.Matrix.Identity(4),
        )
        package_name = loaded_ifp.data.name or animation_library or ifp_path.stem
        action.name = "DemonFF::%s::%s" % (package_name, animation.name)
        action["DemonFF_IFP_Package"] = str(package_name)
        action["DemonFF_IFP_Animation_Name"] = str(animation.name)
        action["DemonFF_Source_FPS"] = float(playback_fps)
        action["DemonFF_IFP_Retarget_Version"] = 2
        action["DemonFF_IFP_Missing_Bone_Count"] = len(missing_bones)
        action["DemonFF_Source_File"] = str(ifp_path)
        strip_generated_action_root_motion(action, armature)
        if len(action.fcurves) == 0:
            bpy.data.actions.remove(action)
            PLAYER_SYNC_ANIMATION_STATUS = (
                f"{animation_library}:{animation_name} did not map to any armature bones"
            )
            return None
        print(
            "[DemonFF Ped IFP] %s:%s -> %d FCurve(s), %d missing track(s), 30 FPS"
            % (
                animation_library or "?",
                animation_name,
                len(action.fcurves),
                len(missing_bones),
            )
        )
    except Exception as error:
        PLAYER_SYNC_ANIMATION_STATUS = (
            f"Could not build {animation_library}:{animation_name}: {error}"
        )
        return None

    PLAYER_SYNC_ANIMATION_STATUS = (
        f"Loaded {animation_library}:{animation_name} from {ifp_path.name}"
    )
    return action


def animation_should_loop(animation_name, motion_name):
    normalized_name = normalize_animation_identifier(animation_name)

    looping_fragments = (
        "glide",
        "idle",
        "stance",
        "walk",
        "run",
        "sprint",
        "drive",
        "swim",
        "tread",
        "seat",
    )
    if any(fragment in normalized_name for fragment in looping_fragments):
        return True

    one_shot_fragments = (
        "jump",
        "land",
        "climb",
        "getup",
        "hit",
        "ko",
        "die",
        "drown",
        "fight",
        "attack",
        "punch",
        "kick",
        "weapon",
        "gun",
        "reload",
        "throw",
        "grenade",
        "crouchroll",
    )
    if any(fragment in normalized_name for fragment in one_shot_fragments):
        return False

    return motion_name in {
        "IDLE",
        "WALK",
        "RUN",
        "SPRINT",
        "VEHICLE_IDLE",
        "VEHICLE_MOVING",
    }


def choose_effective_player_animation(state, motion_name):
    animation_library = str(state.get("animation_library", "")).strip()
    animation_name = str(state.get("animation_name", "")).strip()

    if not animation_name:
        return "", ""

    return animation_library or "PED", animation_name



def get_ifp_animation_by_name(loaded_ifp, animation_name):
    wanted_name = normalize_animation_identifier(animation_name)
    if not wanted_name:
        return None

    for animation in loaded_ifp.data.animations:
        if normalize_animation_identifier(animation.name) == wanted_name:
            return animation
    return None


def convert_ifp_keyframe_time_to_frame(loaded_ifp, keyframe_time):
    if loaded_ifp.version == "ANP3":
        return float(keyframe_time)
    return float(keyframe_time) * 30.0


def build_runtime_ifp_tracks(armature, loaded_ifp, animation):
    from ..gui import ifp_ot

    bone_by_id, bone_by_name = ifp_ot.build_armature_bone_lookup(armature)
    runtime_tracks = []
    missing_tracks = []
    first_frame = None
    last_frame = None

    for ifp_bone in animation.bones:
        if not ifp_bone.keyframes:
            continue

        bone = ifp_ot.resolve_ifp_track_bone(
            ifp_bone,
            bone_by_id,
            bone_by_name,
        )
        if bone is None:
            missing_tracks.append(
                "%s [%s]" % (
                    str(getattr(ifp_bone, "name", "?")),
                    str(getattr(ifp_bone, "bone_id", "?")),
                )
            )
            continue

        pose_bone = armature.pose.bones.get(bone.name)
        if pose_bone is None:
            missing_tracks.append(bone.name)
            continue

        rest_local = ifp_ot.get_bone_rest_local_matrix(
            bone,
            mathutils.Matrix.Identity(4),
        )
        rest_inverse = rest_local.inverted_safe()
        rest_location = rest_local.to_translation()
        rest_rotation = rest_local.to_quaternion()
        if rest_rotation.magnitude > 0.000001:
            rest_rotation.normalize()
        else:
            rest_rotation = mathutils.Quaternion((1.0, 0.0, 0.0, 0.0))
        rest_scale = rest_local.to_scale()

        frames = []
        positions = []
        rotations = []
        scales = []
        previous_rotation = None

        for keyframe in ifp_bone.keyframes:
            frame = convert_ifp_keyframe_time_to_frame(
                loaded_ifp,
                keyframe.time,
            )
            rotation = keyframe.rot.copy()
            if rotation.magnitude > 0.000001:
                rotation.normalize()
            else:
                rotation = mathutils.Quaternion((1.0, 0.0, 0.0, 0.0))

            if previous_rotation is not None and rotation.dot(previous_rotation) < 0.0:
                rotation.negate()
            previous_rotation = rotation.copy()

            frames.append(frame)
            positions.append(keyframe.pos.copy())
            rotations.append(rotation)
            scales.append(keyframe.scl.copy())

            first_frame = frame if first_frame is None else min(first_frame, frame)
            last_frame = frame if last_frame is None else max(last_frame, frame)

        if not frames:
            continue

        pose_bone.rotation_mode = "QUATERNION"
        runtime_tracks.append({
            "pose_bone": pose_bone,
            "bone_name": bone.name,
            "direct_id": get_armature_bone_direct_id(bone),
            "has_translation": ifp_bone.keyframe_type[2] == "T",
            "has_scale": ifp_bone.keyframe_type[3] == "S",
            "frames": frames,
            "positions": positions,
            "rotations": rotations,
            "scales": scales,
            "rest_inverse": rest_inverse,
            "rest_location": rest_location,
            "rest_rotation": rest_rotation,
            "rest_scale": rest_scale,
        })

    if first_frame is None:
        first_frame = 0.0
    if last_frame is None:
        last_frame = first_frame

    return runtime_tracks, missing_tracks, first_frame, last_frame


def sample_runtime_track(track, frame):
    frames = track["frames"]
    if len(frames) == 1 or frame <= frames[0]:
        return (
            track["positions"][0].copy(),
            track["rotations"][0].copy(),
            track["scales"][0].copy(),
        )
    if frame >= frames[-1]:
        return (
            track["positions"][-1].copy(),
            track["rotations"][-1].copy(),
            track["scales"][-1].copy(),
        )

    right_index = bisect.bisect_right(frames, frame)
    left_index = max(0, right_index - 1)
    right_index = min(len(frames) - 1, right_index)

    left_frame = frames[left_index]
    right_frame = frames[right_index]
    if right_frame <= left_frame:
        factor = 0.0
    else:
        factor = (frame - left_frame) / (right_frame - left_frame)
        factor = max(0.0, min(1.0, factor))

    left_position = track["positions"][left_index]
    right_position = track["positions"][right_index]
    position = left_position.lerp(right_position, factor)

    left_rotation = track["rotations"][left_index]
    right_rotation = track["rotations"][right_index]
    rotation = left_rotation.slerp(right_rotation, factor)
    if rotation.magnitude > 0.000001:
        rotation.normalize()

    left_scale = track["scales"][left_index]
    right_scale = track["scales"][right_index]
    scale = left_scale.lerp(right_scale, factor)
    return position, rotation, scale


def reset_runtime_pose_bones(armature):
    if armature is None:
        return

    try:
        pose_bones = list(armature.pose.bones)
    except (ReferenceError, RuntimeError, AttributeError):
        return

    for pose_bone in pose_bones:
        try:
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.location = (0.0, 0.0, 0.0)
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pose_bone.scale = (1.0, 1.0, 1.0)
        except (ReferenceError, RuntimeError, AttributeError):
            continue


def configure_runtime_player_animation(armature, state, motion_name):
    global PLAYER_SYNC_ACTION_TOKEN
    global PLAYER_SYNC_ACTION_START_TIME
    global PLAYER_SYNC_ACTION_START_FRAME
    global PLAYER_SYNC_ACTION_LOOP
    global PLAYER_SYNC_RUNTIME_ANIMATION
    global PLAYER_SYNC_RUNTIME_TRACKS
    global PLAYER_SYNC_RUNTIME_MISSING_TRACKS
    global PLAYER_SYNC_RUNTIME_FIRST_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_FRAME
    global PLAYER_SYNC_RUNTIME_SOURCE_FPS
    global PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME
    global PLAYER_SYNC_ANIMATION_STATUS

    if not PLAYER_SYNC_ANIMATION_ENABLED or armature is None:
        return

    animation_library, animation_name = choose_effective_player_animation(
        state,
        motion_name,
    )
    animation_token = (
        int(state.get("animation_index", 0)),
        int(state.get("animation_start_tick", 0)),
        normalize_animation_identifier(animation_library),
        normalize_animation_identifier(animation_name),
    )
    if animation_token == PLAYER_SYNC_ACTION_TOKEN:
        return

    PLAYER_SYNC_ACTION_TOKEN = animation_token
    PLAYER_SYNC_RUNTIME_ANIMATION = None
    PLAYER_SYNC_RUNTIME_TRACKS = []
    PLAYER_SYNC_RUNTIME_MISSING_TRACKS = []
    PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME = None
    reset_runtime_pose_bones(armature)

    if not animation_name:
        PLAYER_SYNC_ANIMATION_STATUS = "Game animation index is 0"
        return

    candidate_paths = get_player_ifp_candidates(
        PLAYER_SYNC_GAME_ROOT,
        animation_library,
    )
    if not candidate_paths:
        PLAYER_SYNC_ANIMATION_STATUS = (
            "No IFP source found for %s:%s" % (
                animation_library or "?",
                animation_name,
            )
        )
        print("[DemonFF Ped IFP] " + PLAYER_SYNC_ANIMATION_STATUS)
        return

    loaded_ifp = None
    animation = None
    ifp_path = None
    load_errors = []
    for candidate_path in candidate_paths:
        try:
            candidate_ifp = load_cached_ifp(candidate_path)
        except Exception as error:
            load_errors.append("%s: %s" % (candidate_path.name, error))
            continue

        candidate_animation = get_ifp_animation_by_name(
            candidate_ifp,
            animation_name,
        )
        if candidate_animation is None:
            continue

        loaded_ifp = candidate_ifp
        animation = candidate_animation
        ifp_path = candidate_path
        break

    if animation is None or loaded_ifp is None or ifp_path is None:
        searched_names = ", ".join(path.name for path in candidate_paths)
        PLAYER_SYNC_ANIMATION_STATUS = "%s:%s not found in %s" % (
            animation_library or "?",
            animation_name,
            searched_names or "available IFP files",
        )
        if load_errors:
            PLAYER_SYNC_ANIMATION_STATUS += " (%s)" % "; ".join(load_errors)
        print("[DemonFF Ped IFP] " + PLAYER_SYNC_ANIMATION_STATUS)
        return

    try:
        (
            runtime_tracks,
            missing_tracks,
            first_frame,
            last_frame,
        ) = build_runtime_ifp_tracks(armature, loaded_ifp, animation)
    except Exception as error:
        PLAYER_SYNC_ANIMATION_STATUS = "Could not map %s:%s: %s" % (
            animation_library or "?",
            animation_name,
            error,
        )
        print("[DemonFF Ped IFP] " + PLAYER_SYNC_ANIMATION_STATUS)
        return

    if not runtime_tracks:
        PLAYER_SYNC_ANIMATION_STATUS = "%s:%s mapped to no deform bones" % (
            animation_library or "?",
            animation_name,
        )
        print("[DemonFF Ped IFP] " + PLAYER_SYNC_ANIMATION_STATUS)
        return

    server_elapsed_seconds = 0.0
    animation_start_tick = int(state.get("animation_start_tick", 0))
    state_tick = int(state.get("tick", 0))
    if animation_start_tick > 0 and state_tick >= animation_start_tick:
        server_elapsed_seconds = min(
            30.0,
            max(0.0, (state_tick - animation_start_tick) / 1000.0),
        )

    PLAYER_SYNC_RUNTIME_ANIMATION = animation
    PLAYER_SYNC_RUNTIME_TRACKS = runtime_tracks
    PLAYER_SYNC_RUNTIME_MISSING_TRACKS = missing_tracks
    PLAYER_SYNC_RUNTIME_FIRST_FRAME = float(first_frame)
    PLAYER_SYNC_RUNTIME_LAST_FRAME = float(last_frame)
    PLAYER_SYNC_RUNTIME_SOURCE_FPS = 30.0
    PLAYER_SYNC_ACTION_START_TIME = time.perf_counter() - server_elapsed_seconds
    PLAYER_SYNC_ACTION_START_FRAME = float(first_frame)
    PLAYER_SYNC_ACTION_LOOP = animation_should_loop(animation_name, motion_name)
    PLAYER_SYNC_ANIMATION_STATUS = "%s:%s -> live %s pose (%d bones)" % (
        animation_library or "?",
        animation_name,
        ifp_path.name,
        len(runtime_tracks),
    )

    print(
        "[DemonFF Ped IFP] index %d, %s:%s from %s, "
        "%d mapped bone track(s), %d missing, frames %.3f..%.3f, %s"
        % (
            int(state.get("animation_index", 0)),
            animation_library or "?",
            animation_name,
            str(ifp_path),
            len(runtime_tracks),
            len(missing_tracks),
            first_frame,
            last_frame,
            "loop" if PLAYER_SYNC_ACTION_LOOP else "one-shot",
        )
    )
    if missing_tracks:
        print(
            "[DemonFF Ped IFP] Missing tracks: %s"
            % ", ".join(missing_tracks[:12])
        )


def apply_runtime_player_animation_pose():
    global PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_LOG_TIME

    armature = PLAYER_SYNC_ARMATURE
    if (
        armature is None
        or PLAYER_SYNC_RUNTIME_ANIMATION is None
        or not PLAYER_SYNC_RUNTIME_TRACKS
    ):
        return

    first_frame = PLAYER_SYNC_RUNTIME_FIRST_FRAME
    last_frame = PLAYER_SYNC_RUNTIME_LAST_FRAME
    duration = max(0.0, last_frame - first_frame)
    elapsed_seconds = max(
        0.0,
        time.perf_counter() - PLAYER_SYNC_ACTION_START_TIME,
    )
    frame = PLAYER_SYNC_ACTION_START_FRAME + (
        elapsed_seconds * PLAYER_SYNC_RUNTIME_SOURCE_FPS
    )

    if PLAYER_SYNC_ACTION_LOOP and duration > 0.000001:
        frame = first_frame + ((frame - first_frame) % duration)
    else:
        frame = max(first_frame, min(last_frame, frame))

    if (
        PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME is not None
        and abs(frame - PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME) < 0.0001
    ):
        return

    from ..gui import ifp_ot

    for track in PLAYER_SYNC_RUNTIME_TRACKS:
        pose_bone = track["pose_bone"]
        position, rotation, scale = sample_runtime_track(track, frame)

        try:
            target_location = (
                position
                if track["has_translation"]
                else track["rest_location"]
            )
            target_scale = (
                scale
                if track["has_scale"]
                else track["rest_scale"]
            )
            target_local = ifp_ot.compose_transform_matrix(
                target_location,
                rotation,
                target_scale,
            )
            basis_matrix = track["rest_inverse"] @ target_local
            basis_location = basis_matrix.to_translation()
            basis_rotation = basis_matrix.to_quaternion()
            if basis_rotation.magnitude > 0.000001:
                basis_rotation.normalize()
            else:
                basis_rotation = mathutils.Quaternion((1.0, 0.0, 0.0, 0.0))
            basis_scale = basis_matrix.to_scale()

            if track["has_translation"] and track["direct_id"] != 0:
                pose_bone.location = basis_location
            else:
                pose_bone.location = (0.0, 0.0, 0.0)

            pose_bone.rotation_quaternion = basis_rotation
            pose_bone.scale = basis_scale
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            continue

    PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME = frame
    try:
        bpy.context.view_layer.update()
    except (ReferenceError, RuntimeError, AttributeError):
        pass

    now = time.perf_counter()
    if now - PLAYER_SYNC_RUNTIME_LAST_LOG_TIME >= 2.0:
        PLAYER_SYNC_RUNTIME_LAST_LOG_TIME = now
        print(
            "[DemonFF Ped IFP] sampled frame %.2f of %.2f directly onto %d pose bone(s)"
            % (
                frame,
                last_frame,
                len(PLAYER_SYNC_RUNTIME_TRACKS),
            )
        )


def reset_player_armature_pose(armature, clear_action=False):
    if armature is None:
        return

    try:
        animation_data = armature.animation_data
        if clear_action and animation_data is not None:
            animation_data.action = None
    except (ReferenceError, RuntimeError, AttributeError):
        pass

    try:
        pose_bones = list(armature.pose.bones)
    except (ReferenceError, RuntimeError, AttributeError):
        pose_bones = []

    for pose_bone in pose_bones:
        try:
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.location = (0.0, 0.0, 0.0)
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pose_bone.scale = (1.0, 1.0, 1.0)
        except (ReferenceError, RuntimeError, AttributeError):
            continue


def clear_player_animation_pose(armature, status):
    global PLAYER_SYNC_ACTION
    global PLAYER_SYNC_ANIMATION_STATUS

    PLAYER_SYNC_ACTION = None
    reset_player_armature_pose(armature, clear_action=True)
    PLAYER_SYNC_ANIMATION_STATUS = status


def set_player_animation_action(armature, state, motion_name):
    global PLAYER_SYNC_ACTION
    global PLAYER_SYNC_ACTION_TOKEN
    global PLAYER_SYNC_ACTION_START_TIME
    global PLAYER_SYNC_ACTION_START_FRAME
    global PLAYER_SYNC_ACTION_LOOP
    global PLAYER_SYNC_ANIMATION_STATUS

    if not PLAYER_SYNC_ANIMATION_ENABLED or armature is None:
        return

    animation_library, animation_name = choose_effective_player_animation(
        state,
        motion_name,
    )
    animation_token = (
        int(state.get("animation_index", 0)),
        int(state.get("animation_start_tick", 0)),
        normalize_animation_identifier(animation_library),
        normalize_animation_identifier(animation_name),
    )

    if animation_token == PLAYER_SYNC_ACTION_TOKEN:
        return

    PLAYER_SYNC_ACTION_TOKEN = animation_token

    if not animation_name:
        clear_player_animation_pose(
            armature,
            "The game did not report an animation name",
        )
        return

    action = find_existing_animation_action(
        armature,
        animation_library,
        animation_name,
    )
    if action is None:
        action = create_animation_action_from_ifp(
            armature,
            animation_library,
            animation_name,
        )

    if action is None:
        clear_player_animation_pose(
            armature,
            PLAYER_SYNC_ANIMATION_STATUS or "The reported animation could not be loaded",
        )
        return

    animation_data = armature.animation_data
    if animation_data is None:
        animation_data = armature.animation_data_create()

    reset_player_armature_pose(armature, clear_action=False)
    animation_data.action = action

    PLAYER_SYNC_ACTION = action
    server_elapsed_seconds = 0.0
    animation_start_tick = int(state.get("animation_start_tick", 0))
    state_tick = int(state.get("tick", 0))
    if animation_start_tick > 0 and state_tick >= animation_start_tick:
        server_elapsed_seconds = min(
            30.0,
            max(0.0, (state_tick - animation_start_tick) / 1000.0),
        )
    PLAYER_SYNC_ACTION_START_TIME = time.perf_counter() - server_elapsed_seconds
    PLAYER_SYNC_ACTION_START_FRAME = float(action.frame_range[0])
    PLAYER_SYNC_ACTION_LOOP = animation_should_loop(animation_name, motion_name)
    PLAYER_SYNC_ANIMATION_STATUS = "%s:%s -> %s" % (
        animation_library or "?",
        animation_name,
        action.name,
    )


def update_player_animation_frame():
    action = PLAYER_SYNC_ACTION
    armature = PLAYER_SYNC_ARMATURE
    if action is None or armature is None:
        return

    try:
        if armature.animation_data is None or armature.animation_data.action != action:
            return
        first_frame = float(action.frame_range[0])
        last_frame = float(action.frame_range[1])
        source_fps = float(action.get("DemonFF_Source_FPS", 30.0))
    except (ReferenceError, RuntimeError, AttributeError, TypeError, ValueError):
        return

    frame_length = max(1.0, last_frame - first_frame + 1.0)
    elapsed_seconds = max(0.0, time.perf_counter() - PLAYER_SYNC_ACTION_START_TIME)
    frame = PLAYER_SYNC_ACTION_START_FRAME + elapsed_seconds * max(1.0, source_fps)

    if PLAYER_SYNC_ACTION_LOOP:
        frame = first_frame + ((frame - first_frame) % frame_length)
    else:
        frame = min(last_frame, frame)

    scene = bpy.context.scene
    whole_frame = math.floor(frame)
    subframe = frame - whole_frame
    try:
        scene.frame_set(int(whole_frame), subframe=subframe)
    except (ReferenceError, RuntimeError, AttributeError):
        pass


def get_armature_bone_direct_id(bone):
    for property_name in DIRECT_ID_PROPERTY_NAMES:
        try:
            value = bone.get(property_name)
        except (AttributeError, ReferenceError, RuntimeError):
            value = None
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return directIdFromBoneName(getattr(bone, "name", ""))


def find_armature_bone_by_direct_id(armature, direct_id):
    if armature is None or armature.type != "ARMATURE":
        return None

    for bone in armature.data.bones:
        if get_armature_bone_direct_id(bone) == int(direct_id):
            return bone
    return None


def bone_point_in_target_space(motion_target, armature, bone, use_tail=False):
    if motion_target is None or armature is None or bone is None:
        return None

    try:
        point = bone.tail_local if use_tail else bone.head_local
        world_point = armature.matrix_world @ point
        return motion_target.matrix_world.inverted_safe() @ world_point
    except (ReferenceError, RuntimeError, AttributeError, TypeError):
        return None


def bone_point_world(armature, bone, use_tail=False):
    if armature is None or bone is None:
        return None

    try:
        point = bone.tail_local if use_tail else bone.head_local
        return armature.matrix_world @ point
    except (ReferenceError, RuntimeError, AttributeError, TypeError):
        return None


def calculate_player_anchor_world(armature, fallback_target):
    root_point = bone_point_world(
        armature,
        find_armature_bone_by_direct_id(armature, 0),
    )
    if root_point is not None:
        return root_point, "HAnim root"

    foot_points = []
    for direct_id, use_tail in ((43, True), (53, True), (2000, False), (2001, False)):
        point = bone_point_world(
            armature,
            find_armature_bone_by_direct_id(armature, direct_id),
            use_tail=use_tail,
        )
        if point is not None:
            foot_points.append(point)

    if len(foot_points) >= 2:
        anchor = sum(foot_points, mathutils.Vector((0.0, 0.0, 0.0)))
        return anchor / float(len(foot_points)), "feet fallback"

    if foot_points:
        return foot_points[0], "single-foot fallback"

    try:
        return fallback_target.matrix_world.to_translation(), "object origin"
    except (ReferenceError, RuntimeError, AttributeError):
        return mathutils.Vector((0.0, 0.0, 0.0)), "world origin"


def normalized_world_direction(vector, fallback):
    result = mathutils.Vector(vector)
    if result.length_squared <= 0.0000001:
        result = mathutils.Vector(fallback)
    if result.length_squared > 0.0000001:
        result.normalize()
    return result


def calculate_player_model_frame_world(armature, fallback_target):
    anchor, anchor_description = calculate_player_anchor_world(
        armature,
        fallback_target,
    )

    pelvis = bone_point_world(
        armature,
        find_armature_bone_by_direct_id(armature, 1),
    )
    head = bone_point_world(
        armature,
        find_armature_bone_by_direct_id(armature, 5),
    )

    left = None
    right = None
    lateral_description = ""
    for left_id, right_id, description in (
        (31, 21, "shoulders"),
        (41, 51, "thighs"),
        (43, 53, "feet"),
    ):
        candidate_left = bone_point_world(
            armature,
            find_armature_bone_by_direct_id(armature, left_id),
        )
        candidate_right = bone_point_world(
            armature,
            find_armature_bone_by_direct_id(armature, right_id),
        )
        if (
            candidate_left is not None
            and candidate_right is not None
            and (candidate_right - candidate_left).length > 0.0001
        ):
            left = candidate_left
            right = candidate_right
            lateral_description = description
            break

    if pelvis is not None and head is not None and left is not None and right is not None:
        right_axis = normalized_world_direction(
            right - left,
            (1.0, 0.0, 0.0),
        )
        up_axis = head - pelvis
        up_axis -= right_axis * up_axis.dot(right_axis)
        up_axis = normalized_world_direction(up_axis, (0.0, 0.0, 1.0))
        forward_axis = normalized_world_direction(
            up_axis.cross(right_axis),
            (0.0, 1.0, 0.0),
        )
        right_axis = normalized_world_direction(
            forward_axis.cross(up_axis),
            right_axis,
        )
        orientation_description = "HAnim %s/pelvis/head" % lateral_description
    else:
        try:
            object_rotation = fallback_target.matrix_world.to_quaternion()
            right_axis = object_rotation @ mathutils.Vector((-1.0, 0.0, 0.0))
            forward_axis = object_rotation @ mathutils.Vector((0.0, -1.0, 0.0))
            up_axis = object_rotation @ mathutils.Vector((0.0, 0.0, 1.0))
        except (ReferenceError, RuntimeError, AttributeError):
            right_axis = mathutils.Vector((1.0, 0.0, 0.0))
            forward_axis = mathutils.Vector((0.0, 1.0, 0.0))
            up_axis = mathutils.Vector((0.0, 0.0, 1.0))
        right_axis = normalized_world_direction(right_axis, (1.0, 0.0, 0.0))
        forward_axis = normalized_world_direction(forward_axis, (0.0, 1.0, 0.0))
        up_axis = normalized_world_direction(up_axis, (0.0, 0.0, 1.0))
        orientation_description = "object fallback with GTA ped 180-degree correction"

    model_frame = mathutils.Matrix.Identity(4)
    for row in range(3):
        model_frame[row][0] = right_axis[row]
        model_frame[row][1] = forward_axis[row]
        model_frame[row][2] = up_axis[row]
        model_frame[row][3] = anchor[row]

    return model_frame, "%s anchor; %s orientation" % (
        anchor_description,
        orientation_description,
    )


def get_object_all_collection_objects(collection):
    try:
        return set(collection.all_objects)
    except (ReferenceError, RuntimeError, AttributeError, TypeError):
        try:
            return set(collection.objects)
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            return set()


def find_armature_bound_meshes(armature):
    if armature is None:
        return []

    bound_meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        try:
            if any(
                modifier.type == "ARMATURE" and modifier.object == armature
                for modifier in obj.modifiers
            ):
                bound_meshes.append(obj)
        except (ReferenceError, RuntimeError, AttributeError):
            continue
    return bound_meshes


def choose_player_model_collection(selected_target, armature, bound_meshes):
    core_objects = [obj for obj in (selected_target, armature) if obj is not None]
    core_objects.extend(bound_meshes)
    if not core_objects:
        return None

    candidate_collections = []
    seen = set()
    for obj in core_objects:
        try:
            collections = list(obj.users_collection)
        except (ReferenceError, RuntimeError, AttributeError):
            collections = []
        for collection in collections:
            key = id(collection)
            if key in seen:
                continue
            seen.add(key)
            objects = get_object_all_collection_objects(collection)
            covered = sum(1 for core in core_objects if core in objects)
            if covered == 0:
                continue
            name = str(getattr(collection, "name", ""))
            dff_preference = 0 if name.lower().endswith(".dff") else 1
            candidate_collections.append((
                -covered,
                dff_preference,
                max(1, len(objects)),
                name.casefold(),
                collection,
            ))

    if not candidate_collections:
        return None
    candidate_collections.sort(key=lambda item: item[:-1])
    return candidate_collections[0][-1]


def collect_player_transform_roots(selected_target, armature):
    bound_meshes = find_armature_bound_meshes(armature)
    model_collection = choose_player_model_collection(
        selected_target,
        armature,
        bound_meshes,
    )
    allowed_objects = (
        get_object_all_collection_objects(model_collection)
        if model_collection is not None
        else set()
    )

    core_objects = []
    for obj in [armature, selected_target] + bound_meshes:
        if obj is not None and obj not in core_objects:
            core_objects.append(obj)

    roots = []
    for obj in core_objects:
        root = obj
        while root.parent is not None:
            parent = root.parent
            if allowed_objects and parent not in allowed_objects:
                break
            if not allowed_objects and parent.parent is not None:
                break
            root = parent
        if root not in roots:
            roots.append(root)

    filtered_roots = []
    for root in roots:
        if any(
            other != root and object_is_ancestor(other, root)
            for other in roots
        ):
            continue
        filtered_roots.append(root)

    if not filtered_roots and selected_target is not None:
        filtered_roots = [selected_target]

    return filtered_roots, model_collection


def make_player_world_frame(state):
    position = mathutils.Vector(state["position"])
    corrected_angle = float(state["angle"])
    if PLAYER_SYNC_ARMATURE is not None:
        corrected_angle += 180.0
    heading = mathutils.Matrix.Rotation(
        math.radians(corrected_angle),
        4,
        "Z",
    )
    return mathutils.Matrix.Translation(position) @ heading


def apply_player_transform_to_target(target, state):
    if target is None or PLAYER_SYNC_MODEL_FRAME_WORLD is None:
        return

    desired_frame = make_player_world_frame(state)
    world_delta = desired_frame @ PLAYER_SYNC_MODEL_FRAME_WORLD.inverted_safe()

    roots = PLAYER_SYNC_TRANSFORM_ROOTS or [target]
    for root in roots:
        base_matrix = PLAYER_SYNC_TRANSFORM_BASE_MATRICES.get(root)
        if base_matrix is None:
            continue
        try:
            root.matrix_world = world_delta @ base_matrix
        except (ReferenceError, RuntimeError, AttributeError, TypeError):
            continue


def estimate_player_world_velocity(previous_state, state):
    if previous_state is None:
        return (0.0, 0.0, 0.0)

    previous_tick = int(previous_state.get("tick", 0))
    current_tick = int(state.get("tick", 0))
    tick_delta = current_tick - previous_tick
    if tick_delta <= 0 or tick_delta > 1000:
        return (0.0, 0.0, 0.0)

    seconds = tick_delta / 1000.0
    previous_position = mathutils.Vector(previous_state["position"])
    current_position = mathutils.Vector(state["position"])
    velocity = (current_position - previous_position) / seconds

    if velocity.length > 100.0:
        return (0.0, 0.0, 0.0)

    return (float(velocity.x), float(velocity.y), float(velocity.z))


def update_player_state_metadata(target, state):
    global PLAYER_SYNC_PREVIOUS_STATE
    global PLAYER_SYNC_LAST_STATE
    global PLAYER_SYNC_STATE_RECEIVED_TIME

    motion_name, horizontal_speed = classify_player_motion(state)
    previous_motion = None
    if PLAYER_SYNC_LAST_STATE is not None:
        previous_motion = PLAYER_SYNC_LAST_STATE.get("motion")

    state["estimated_world_velocity"] = estimate_player_world_velocity(
        PLAYER_SYNC_LAST_STATE,
        state,
    )
    PLAYER_SYNC_STATE_RECEIVED_TIME = time.perf_counter()
    state["received_time"] = PLAYER_SYNC_STATE_RECEIVED_TIME

    try:
        target["DemonFF_Player_Motion"] = motion_name
        target["DemonFF_Player_Speed"] = float(horizontal_speed)
        target["DemonFF_Player_Animation"] = int(state["animation_index"])
        target["DemonFF_Player_Animation_Library"] = str(
            state.get("animation_library", "")
        )
        target["DemonFF_Player_Animation_Name"] = str(
            state.get("animation_name", "")
        )
        effective_library, effective_name = choose_effective_player_animation(
            state,
            motion_name,
        )
        target["DemonFF_Player_Effective_Animation_Library"] = effective_library
        target["DemonFF_Player_Effective_Animation_Name"] = effective_name
        target["DemonFF_Player_Special_Action"] = int(state["special_action"])
        target["DemonFF_Player_Keys"] = int(state["keys"])
        target["DemonFF_Player_UpDown"] = int(state["up_down"])
        target["DemonFF_Player_LeftRight"] = int(state["left_right"])
        target["DemonFF_Player_Skin"] = int(state["skin"])
        target["DemonFF_Player_In_Vehicle"] = bool(state["in_vehicle"])
        target["DemonFF_Player_Vehicle_Model"] = int(state["vehicle_model"])
        target["DemonFF_Player_Server_Tick"] = int(state["tick"])
    except (ReferenceError, RuntimeError):
        pass

    configure_runtime_player_animation(PLAYER_SYNC_ARMATURE, state, motion_name)

    effective_library, effective_name = choose_effective_player_animation(
        state,
        motion_name,
    )
    state["effective_animation_library"] = effective_library
    state["effective_animation_name"] = effective_name
    state["motion"] = motion_name
    state["motion_changed"] = previous_motion != motion_name

    PLAYER_SYNC_PREVIOUS_STATE = PLAYER_SYNC_LAST_STATE
    PLAYER_SYNC_LAST_STATE = state


def apply_player_state_to_target(target, state):
    if target is None:
        return

    update_player_state_metadata(target, state)
    apply_player_transform_to_target(target, state)

def player_sync_timer():
    global PLAYER_SYNC_LAST_REVISION

    if not PLAYER_SYNC_ACTIVE:
        return None

    if SERVER_PROCESS is None or SERVER_PROCESS.poll() is not None:
        stop_player_sync()
        return None

    target = PLAYER_SYNC_TARGET
    try:
        if target is None or target.name not in bpy.data.objects:
            stop_player_sync()
            return None
    except (ReferenceError, RuntimeError):
        stop_player_sync()
        return None

    state = read_player_state()
    if state is not None and state["revision"] != PLAYER_SYNC_LAST_REVISION:
        PLAYER_SYNC_LAST_REVISION = state["revision"]
        apply_player_state_to_target(target, state)
    elif PLAYER_SYNC_LAST_STATE is not None:
        apply_player_transform_to_target(target, PLAYER_SYNC_LAST_STATE)

    apply_runtime_player_animation_pose()
    return PLAYER_STATE_INTERVAL


def start_player_sync(context, target=None, follow_view=False):
    global PLAYER_SYNC_TARGET
    global PLAYER_SYNC_ARMATURE
    global PLAYER_SYNC_ACTIVE
    global PLAYER_SYNC_FOLLOW_VIEW
    global PLAYER_SYNC_LAST_REVISION
    global PLAYER_SYNC_BASIS_OFFSET
    global PLAYER_SYNC_ALIGNMENT_LOCAL
    global PLAYER_SYNC_POSITION_OFFSET
    global PLAYER_SYNC_HEADING_OFFSET
    global PLAYER_SYNC_AUTO_ALIGN_PED
    global PLAYER_SYNC_PREVIOUS_STATE
    global PLAYER_SYNC_LAST_STATE
    global PLAYER_SYNC_STATE_RECEIVED_TIME
    global PLAYER_SYNC_ORIGINAL_ACTION
    global PLAYER_SYNC_ORIGINAL_FRAME
    global PLAYER_SYNC_ACTION
    global PLAYER_SYNC_ACTION_TOKEN
    global PLAYER_SYNC_RUNTIME_ANIMATION
    global PLAYER_SYNC_RUNTIME_TRACKS
    global PLAYER_SYNC_RUNTIME_MISSING_TRACKS
    global PLAYER_SYNC_RUNTIME_FIRST_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_FRAME
    global PLAYER_SYNC_RUNTIME_SOURCE_FPS
    global PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_LOG_TIME
    global PLAYER_SYNC_MUTED_NLA_TRACKS
    global PLAYER_SYNC_ORIGINAL_POSE_POSITION
    global PLAYER_SYNC_ANIMATION_ENABLED
    global PLAYER_SYNC_AUTO_LOAD_IFP
    global PLAYER_SYNC_GAME_ROOT
    global PLAYER_SYNC_ANIMATION_STATUS
    global PLAYER_SYNC_TRANSFORM_ROOTS
    global PLAYER_SYNC_TRANSFORM_BASE_MATRICES
    global PLAYER_SYNC_MODEL_FRAME_WORLD
    global PLAYER_SYNC_MODEL_FRAME_DESCRIPTION

    stop_player_sync()

    if target is None:
        target = resolve_player_sync_target(context)
    else:
        set_configured_player_sync_target(context, target)

    set_live_player_export_exclusion(target, True)
    motion_target, armature = resolve_player_sync_components(target)
    transform_roots, model_collection = collect_player_transform_roots(
        target,
        armature,
    )
    if transform_roots:
        motion_target = transform_roots[0]

    PLAYER_SYNC_TARGET = motion_target
    PLAYER_SYNC_ARMATURE = armature
    PLAYER_SYNC_ACTIVE = True
    PLAYER_SYNC_FOLLOW_VIEW = bool(follow_view)
    PLAYER_SYNC_LAST_REVISION = -1
    PLAYER_SYNC_AUTO_ALIGN_PED = True
    PLAYER_SYNC_BASIS_OFFSET = None
    PLAYER_SYNC_ALIGNMENT_LOCAL = None
    PLAYER_SYNC_POSITION_OFFSET = None
    PLAYER_SYNC_HEADING_OFFSET = 0.0
    PLAYER_SYNC_TRANSFORM_ROOTS = list(transform_roots)
    PLAYER_SYNC_TRANSFORM_BASE_MATRICES = {
        root: root.matrix_world.copy()
        for root in PLAYER_SYNC_TRANSFORM_ROOTS
    }
    (
        PLAYER_SYNC_MODEL_FRAME_WORLD,
        PLAYER_SYNC_MODEL_FRAME_DESCRIPTION,
    ) = calculate_player_model_frame_world(armature, motion_target)
    PLAYER_SYNC_PREVIOUS_STATE = None
    PLAYER_SYNC_LAST_STATE = None
    PLAYER_SYNC_STATE_RECEIVED_TIME = 0.0
    PLAYER_SYNC_ACTION = None
    PLAYER_SYNC_ACTION_TOKEN = None
    PLAYER_SYNC_RUNTIME_ANIMATION = None
    PLAYER_SYNC_RUNTIME_TRACKS = []
    PLAYER_SYNC_RUNTIME_MISSING_TRACKS = []
    PLAYER_SYNC_RUNTIME_FIRST_FRAME = 0.0
    PLAYER_SYNC_RUNTIME_LAST_FRAME = 0.0
    PLAYER_SYNC_RUNTIME_SOURCE_FPS = 30.0
    PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME = None
    PLAYER_SYNC_RUNTIME_LAST_LOG_TIME = 0.0
    PLAYER_SYNC_MUTED_NLA_TRACKS = []
    PLAYER_SYNC_ORIGINAL_POSE_POSITION = None
    PLAYER_SYNC_ANIMATION_ENABLED = True
    PLAYER_SYNC_AUTO_LOAD_IFP = True
    PLAYER_SYNC_GAME_ROOT = normalize_directory_path(
        getattr(context.scene.dff, "samp_game_root", "")
    )
    PLAYER_SYNC_ANIMATION_STATUS = ""
    PLAYER_SYNC_ORIGINAL_FRAME = float(context.scene.frame_current)

    if armature is not None:
        try:
            PLAYER_SYNC_ORIGINAL_POSE_POSITION = armature.data.pose_position
            armature.data.pose_position = "POSE"
        except (ReferenceError, RuntimeError, AttributeError):
            PLAYER_SYNC_ORIGINAL_POSE_POSITION = None

        animation_data = armature.animation_data
        PLAYER_SYNC_ORIGINAL_ACTION = (
            animation_data.action if animation_data is not None else None
        )
        if animation_data is not None:
            animation_data.action = None
            for nla_track in animation_data.nla_tracks:
                PLAYER_SYNC_MUTED_NLA_TRACKS.append((nla_track, bool(nla_track.mute)))
                nla_track.mute = True
        reset_runtime_pose_bones(armature)
    else:
        PLAYER_SYNC_ORIGINAL_ACTION = None
        PLAYER_SYNC_ANIMATION_STATUS = "No armature found in the selected ped hierarchy"

    collection_name = (
        str(model_collection.name)
        if model_collection is not None
        else "no dedicated model collection"
    )
    print(
        "[DemonFF Ped Track] %d transform root(s), %s, %s"
        % (
            len(PLAYER_SYNC_TRANSFORM_ROOTS),
            collection_name,
            PLAYER_SYNC_MODEL_FRAME_DESCRIPTION,
        )
    )
    print(
        "[DemonFF Ped Track] Exact server position with corrected GTA heading; animation is sampled directly from IFP data onto pose bones"
    )

    if PLAYER_SYNC_FOLLOW_VIEW:
        set_player_follow_view(motion_target, True)

    bpy.app.timers.register(
        player_sync_timer,
        first_interval=PLAYER_STATE_INTERVAL,
        persistent=False,
    )
    return motion_target

def stop_player_sync():
    global PLAYER_SYNC_TARGET
    global PLAYER_SYNC_ARMATURE
    global PLAYER_SYNC_ACTIVE
    global PLAYER_SYNC_FOLLOW_VIEW
    global PLAYER_SYNC_LAST_REVISION
    global PLAYER_SYNC_BASIS_OFFSET
    global PLAYER_SYNC_ALIGNMENT_LOCAL
    global PLAYER_SYNC_POSITION_OFFSET
    global PLAYER_SYNC_HEADING_OFFSET
    global PLAYER_SYNC_AUTO_ALIGN_PED
    global PLAYER_SYNC_PREVIOUS_STATE
    global PLAYER_SYNC_LAST_STATE
    global PLAYER_SYNC_STATE_RECEIVED_TIME
    global PLAYER_SYNC_ORIGINAL_ACTION
    global PLAYER_SYNC_ORIGINAL_FRAME
    global PLAYER_SYNC_ACTION
    global PLAYER_SYNC_ACTION_TOKEN
    global PLAYER_SYNC_RUNTIME_ANIMATION
    global PLAYER_SYNC_RUNTIME_TRACKS
    global PLAYER_SYNC_RUNTIME_MISSING_TRACKS
    global PLAYER_SYNC_RUNTIME_FIRST_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_FRAME
    global PLAYER_SYNC_RUNTIME_SOURCE_FPS
    global PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME
    global PLAYER_SYNC_RUNTIME_LAST_LOG_TIME
    global PLAYER_SYNC_MUTED_NLA_TRACKS
    global PLAYER_SYNC_ORIGINAL_POSE_POSITION
    global PLAYER_SYNC_GAME_ROOT
    global PLAYER_SYNC_ANIMATION_STATUS
    global PLAYER_SYNC_TRANSFORM_ROOTS
    global PLAYER_SYNC_TRANSFORM_BASE_MATRICES
    global PLAYER_SYNC_MODEL_FRAME_WORLD
    global PLAYER_SYNC_MODEL_FRAME_DESCRIPTION

    target = PLAYER_SYNC_TARGET
    armature = PLAYER_SYNC_ARMATURE
    if target is not None and PLAYER_SYNC_FOLLOW_VIEW:
        set_player_follow_view(target, False)

    if armature is not None:
        reset_runtime_pose_bones(armature)
        try:
            animation_data = armature.animation_data
            if animation_data is None and PLAYER_SYNC_ORIGINAL_ACTION is not None:
                animation_data = armature.animation_data_create()
            if animation_data is not None:
                animation_data.action = PLAYER_SYNC_ORIGINAL_ACTION
        except (ReferenceError, RuntimeError, AttributeError):
            pass

        for nla_track, original_mute in PLAYER_SYNC_MUTED_NLA_TRACKS:
            try:
                nla_track.mute = original_mute
            except (ReferenceError, RuntimeError, AttributeError):
                continue

        if PLAYER_SYNC_ORIGINAL_POSE_POSITION is not None:
            try:
                armature.data.pose_position = PLAYER_SYNC_ORIGINAL_POSE_POSITION
            except (ReferenceError, RuntimeError, AttributeError):
                pass

    if PLAYER_SYNC_ORIGINAL_FRAME is not None:
        try:
            bpy.context.scene.frame_set(int(PLAYER_SYNC_ORIGINAL_FRAME))
        except (ReferenceError, RuntimeError, AttributeError):
            pass

    PLAYER_SYNC_ACTIVE = False
    PLAYER_SYNC_FOLLOW_VIEW = False
    PLAYER_SYNC_TARGET = None
    PLAYER_SYNC_ARMATURE = None
    PLAYER_SYNC_LAST_REVISION = -1
    PLAYER_SYNC_BASIS_OFFSET = None
    PLAYER_SYNC_ALIGNMENT_LOCAL = None
    PLAYER_SYNC_POSITION_OFFSET = None
    PLAYER_SYNC_HEADING_OFFSET = 0.0
    PLAYER_SYNC_AUTO_ALIGN_PED = True
    PLAYER_SYNC_PREVIOUS_STATE = None
    PLAYER_SYNC_LAST_STATE = None
    PLAYER_SYNC_STATE_RECEIVED_TIME = 0.0
    PLAYER_SYNC_ORIGINAL_ACTION = None
    PLAYER_SYNC_ORIGINAL_FRAME = None
    PLAYER_SYNC_ACTION = None
    PLAYER_SYNC_ACTION_TOKEN = None
    PLAYER_SYNC_RUNTIME_ANIMATION = None
    PLAYER_SYNC_RUNTIME_TRACKS = []
    PLAYER_SYNC_RUNTIME_MISSING_TRACKS = []
    PLAYER_SYNC_RUNTIME_FIRST_FRAME = 0.0
    PLAYER_SYNC_RUNTIME_LAST_FRAME = 0.0
    PLAYER_SYNC_RUNTIME_SOURCE_FPS = 30.0
    PLAYER_SYNC_RUNTIME_LAST_APPLIED_FRAME = None
    PLAYER_SYNC_RUNTIME_LAST_LOG_TIME = 0.0
    PLAYER_SYNC_MUTED_NLA_TRACKS = []
    PLAYER_SYNC_ORIGINAL_POSE_POSITION = None
    PLAYER_SYNC_GAME_ROOT = None
    PLAYER_SYNC_ANIMATION_STATUS = ""
    PLAYER_SYNC_TRANSFORM_ROOTS = []
    PLAYER_SYNC_TRANSFORM_BASE_MATRICES = {}
    PLAYER_SYNC_MODEL_FRAME_WORLD = None
    PLAYER_SYNC_MODEL_FRAME_DESCRIPTION = ""

    try:
        if bpy.app.timers.is_registered(player_sync_timer):
            bpy.app.timers.unregister(player_sync_timer)
    except Exception:
        pass


def get_player_sync_status_text():
    if not PLAYER_SYNC_ACTIVE:
        return "Player tracking stopped"
    if PLAYER_SYNC_LAST_STATE is None:
        return "Waiting for player movement"

    animation_name = PLAYER_SYNC_LAST_STATE.get(
        "effective_animation_name",
        PLAYER_SYNC_LAST_STATE.get("animation_name", ""),
    )
    motion_name = PLAYER_SYNC_LAST_STATE.get("motion", "UNKNOWN")
    horizontal_speed = math.sqrt(
        PLAYER_SYNC_LAST_STATE["velocity"][0] ** 2
        + PLAYER_SYNC_LAST_STATE["velocity"][1] ** 2
    )
    if animation_name:
        return "Player: %s  Anim: %s  Speed: %.3f" % (
            motion_name,
            animation_name,
            horizontal_speed,
        )
    return "Player: %s  Speed: %.3f" % (motion_name, horizontal_speed)


def get_player_animation_status_text():
    if not PLAYER_SYNC_ANIMATION_ENABLED:
        return "Animation mirroring is disabled"
    return PLAYER_SYNC_ANIMATION_STATUS


def cancel_client_watch():
    global CLIENT_WATCH_TIMER

    timer_function = CLIENT_WATCH_TIMER
    CLIENT_WATCH_TIMER = None

    if timer_function is None:
        return

    try:
        if bpy.app.timers.is_registered(timer_function):
            bpy.app.timers.unregister(timer_function)
    except Exception:
        pass


def stop_server_process():
    global SERVER_PROCESS
    global SERVER_LOG_HANDLE
    global SERVER_ROOT

    cancel_client_watch()
    stop_live_transform_sync()
    stop_player_sync()

    if SERVER_PROCESS is not None and SERVER_PROCESS.poll() is None:
        try:
            SERVER_PROCESS.terminate()
            SERVER_PROCESS.wait(timeout=3.0)
        except Exception:
            try:
                SERVER_PROCESS.kill()
                SERVER_PROCESS.wait(timeout=2.0)
            except Exception:
                pass

    SERVER_PROCESS = None
    SERVER_ROOT = None

    if SERVER_LOG_HANDLE is not None:
        try:
            SERVER_LOG_HANDLE.close()
        except Exception:
            pass
        SERVER_LOG_HANDLE = None

    release_local_test_port()


def backup_managed_file(path):
    if not path.is_file():
        return

    try:
        existing_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        existing_text = ""

    if GENERATED_CONFIG_MARKER in existing_text:
        return

    backup_path = path.with_name(path.name + ".demonff_backup")
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


def write_server_cfg(server_root):
    config_path = server_root / "server.cfg"
    backup_managed_file(config_path)

    config_text = f"""echo Executing {GENERATED_CONFIG_MARKER} configuration...
bind {LOCAL_HOST}
lanmode 1
rcon_password {LOCAL_RCON_PASSWORD}
maxplayers 1
port {LOCAL_PORT}
hostname DemonFF Blender SA-MP 0.3.DL Model Test
gamemode0 {TEST_MODE_NAME} 1
filterscripts
plugins streamer
announce 0
query 1
weburl
mapname DemonFF Model Test
language English
useartwork 1
artpath models
sleep 5
stream_rate 1000
stream_distance 300.0
"""
    config_path.write_text(config_text, encoding="utf-8", newline="\r\n")


def write_openmp_config(server_root):
    config_path = server_root / "config.json"
    backup_managed_file(config_path)

    config_data = {
        "name": f"{GENERATED_CONFIG_MARKER} - open.mp",
        "language": "English",
        "announce": False,
        "enable_query": True,
        "max_players": 1,
        "network": {
            "bind": LOCAL_HOST,
            "port": LOCAL_PORT,
            "stream_rate": 1000,
            "stream_radius": TEST_DRAW_DISTANCE,
        },
        "artwork": {
            "enable": True,
            "models_path": "models",
            "port": LOCAL_PORT,
            "web_server_bind": LOCAL_HOST,
        },
        "pawn": {
            "legacy_plugins": ["streamer"],
            "main_scripts": [f"{TEST_MODE_NAME} 1"],
            "side_scripts": [],
        },
        "rcon": {
            "enable": True,
            "password": LOCAL_RCON_PASSWORD,
        },
        "game": {
            "map": "DemonFF Model Test",
            "mode": "DemonFF Model Test",
            "time": 12,
            "weather": 0,
        },
        "logging": {
            "enable": True,
            "file": "demonff_openmp_server.log",
            "log_chat": False,
            "log_connection_messages": True,
            "use_timestamp": True,
        },
        "sleep": 5.0,
    }

    config_path.write_text(
        json.dumps(config_data, indent=4) + "\n",
        encoding="utf-8",
        newline="\r\n",
    )


def configure_server_file(server_root, server_executable):
    if executable_kind(server_executable, OMP_SERVER_EXECUTABLE_NAMES) == "open.mp":
        write_openmp_config(server_root)
    else:
        write_server_cfg(server_root)


def pawn_float(value):
    text = f"{float(value):.6f}"
    text = text.rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text

def build_test_gamemode(pawn_include_name="a_samp"):
    source = r"""#include <__PAWN_INCLUDE__>
#include <streamer>

#define DEMONFF_MODEL_DEFINITION_FILE "__MODEL_FILE__"
#define DEMONFF_PLACEMENT_FILE "__PLACEMENT_FILE__"
#define DEMONFF_PLAYER_STATE_FILE "__PLAYER_STATE_FILE__"
#define DEMONFF_PIVOT_MODEL_ID (__PIVOT_MODEL_ID__)

new g_DemonFFPivotObject = INVALID_STREAMER_ID;
new g_DemonFFTestObjectCount = 0;
new g_DemonFFStaticObjectCount = 0;
new g_DemonFFAttachedObjectCount = 0;
new File:g_DemonFFPlacementHandle;
new g_DemonFFTransformRevision = -1;
new Float:g_DemonFFPosition[3] = {0.0, 0.0, 0.0};
new Float:g_DemonFFRotation[3] = {0.0, 0.0, 0.0};
new g_DemonFFPlayerRevision = 0;
new g_DemonFFLastPlayerWriteTick = 0;
new bool:g_DemonFFHasPlayerState = false;
new g_DemonFFLastPlayerState[14];
new g_DemonFFLastAnimationIndex = -1;
new g_DemonFFAnimationStartTick = 0;

forward DemonFFCreateTestObject();
forward DemonFFCreateTestObjectBatch();
forward DemonFFPollTransform();
forward DemonFFPollPlayerState();

main()
{
}

stock DemonFFReadToken(const source[], &index, output[], output_size)
{
    while (source[index] == ' ' || source[index] == '\t')
    {
        index++;
    }

    new output_index = 0;
    while (
        source[index] != '\0'
        && source[index] != ' '
        && source[index] != '\t'
        && source[index] != '\r'
        && source[index] != '\n'
        && output_index < output_size - 1
    )
    {
        output[output_index++] = source[index++];
    }
    output[output_index] = '\0';
    return output_index;
}

stock DemonFFRefreshPlayers()
{
    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {
        if (IsPlayerConnected(playerid))
        {
            Streamer_Update(playerid);
        }
    }
    return 1;
}

stock DemonFFDestroyTestObjects()
{
    if (g_DemonFFPlacementHandle)
    {
        fclose(g_DemonFFPlacementHandle);
        g_DemonFFPlacementHandle = File:0;
    }

    DestroyAllDynamicObjects();
    g_DemonFFPivotObject = INVALID_STREAMER_ID;
    g_DemonFFTestObjectCount = 0;
    g_DemonFFStaticObjectCount = 0;
    g_DemonFFAttachedObjectCount = 0;
    return 1;
}

stock DemonFFApplyTransform()
{
    if (IsValidDynamicObject(g_DemonFFPivotObject))
    {
        SetDynamicObjectPos(
            g_DemonFFPivotObject,
            g_DemonFFPosition[0],
            g_DemonFFPosition[1],
            g_DemonFFPosition[2]
        );
        SetDynamicObjectRot(
            g_DemonFFPivotObject,
            g_DemonFFRotation[0],
            g_DemonFFRotation[1],
            g_DemonFFRotation[2]
        );
        DemonFFRefreshPlayers();
    }
    return 1;
}

stock DemonFFReadLiveTransform()
{
    new File:handle = fopen("__LIVE_TRANSFORM_FILE__", io_read);
    if (!handle)
    {
        return 0;
    }

    new line[256];
    fread(handle, line);
    fclose(handle);

    new index = 0;
    new token[48];
    if (!DemonFFReadToken(line, index, token, sizeof token))
    {
        return 0;
    }

    new revision = strval(token);
    if (revision == g_DemonFFTransformRevision)
    {
        return 0;
    }

    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFPosition[0] = floatstr(token);
    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFPosition[1] = floatstr(token);
    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFPosition[2] = floatstr(token);
    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFRotation[0] = floatstr(token);
    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFRotation[1] = floatstr(token);
    if (!DemonFFReadToken(line, index, token, sizeof token)) return 0;
    g_DemonFFRotation[2] = floatstr(token);

    g_DemonFFTransformRevision = revision;
    DemonFFApplyTransform();
    return 1;
}

stock DemonFFLoadModelDefinitions()
{
    new File:handle = fopen(DEMONFF_MODEL_DEFINITION_FILE, io_read);
    if (!handle)
    {
        print("DemonFF: model definition file could not be opened.");
        return 0;
    }

    new line[256];
    new loaded_count = 0;
    while (fread(handle, line))
    {
        new index = 0;
        new token[96];
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new custom_model_id = strval(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new base_model_id = strval(token);

        new dff_name[64];
        if (!DemonFFReadToken(line, index, dff_name, sizeof dff_name)) continue;
        new txd_name[64];
        if (!DemonFFReadToken(line, index, txd_name, sizeof txd_name)) continue;

        if (AddSimpleModel(
            -1,
            base_model_id,
            custom_model_id,
            dff_name,
            txd_name
        ))
        {
            loaded_count++;
        }
        else
        {
            printf(
                "DemonFF: AddSimpleModel failed for %d using %s / %s.",
                custom_model_id,
                dff_name,
                txd_name
            );
        }
    }

    fclose(handle);
    printf("DemonFF: registered %d source model(s).", loaded_count);
    return loaded_count;
}

stock DemonFFGetAnimationNames(animation_index, library[], library_size, animation[], animation_size)
{
    library[0] = '\0';
    animation[0] = '\0';

    if (animation_index <= 0)
    {
        return 0;
    }

    return GetAnimationName(
        animation_index,
        library,
        library_size,
        animation,
        animation_size
    );
}

stock DemonFFWritePlayerState(playerid, bool:force_write)
{
    if (!IsPlayerConnected(playerid))
    {
        return 0;
    }

    new Float:x;
    new Float:y;
    new Float:z;
    new Float:angle;
    new Float:velocity_x;
    new Float:velocity_y;
    new Float:velocity_z;
    new keys;
    new up_down;
    new left_right;
    new special_action = GetPlayerSpecialAction(playerid);
    new animation_index = GetPlayerAnimationIndex(playerid);
    new current_tick = GetTickCount();
    new bool:animation_changed = animation_index != g_DemonFFLastAnimationIndex;
    if (animation_changed)
    {
        g_DemonFFLastAnimationIndex = animation_index;
        g_DemonFFAnimationStartTick = current_tick;
    }
    new skin = GetPlayerSkin(playerid);
    new in_vehicle = IsPlayerInAnyVehicle(playerid);
    new vehicle_model = 0;
    new animation_library[32];
    new animation_name[32];

    GetPlayerPos(playerid, x, y, z);
    GetPlayerFacingAngle(playerid, angle);
    GetPlayerKeys(playerid, keys, up_down, left_right);

    if (in_vehicle)
    {
        new vehicleid = GetPlayerVehicleID(playerid);
        vehicle_model = GetVehicleModel(vehicleid);
        GetVehicleVelocity(vehicleid, velocity_x, velocity_y, velocity_z);
    }
    else
    {
        GetPlayerVelocity(playerid, velocity_x, velocity_y, velocity_z);
    }

    DemonFFGetAnimationNames(
        animation_index,
        animation_library,
        sizeof animation_library,
        animation_name,
        sizeof animation_name
    );

    if (animation_library[0] == '\0')
    {
        format(animation_library, sizeof animation_library, "-");
    }
    if (animation_name[0] == '\0')
    {
        format(animation_name, sizeof animation_name, "-");
    }

    if (animation_changed)
    {
        printf(
            "DemonFF player animation: index %d, %s:%s",
            animation_index,
            animation_library,
            animation_name
        );
    }

    new current_state[14];
    current_state[0] = floatround(x * 100.0, floatround_round);
    current_state[1] = floatround(y * 100.0, floatround_round);
    current_state[2] = floatround(z * 100.0, floatround_round);
    current_state[3] = floatround(angle * 10.0, floatround_round);
    current_state[4] = keys;
    current_state[5] = up_down;
    current_state[6] = left_right;
    current_state[7] = special_action;
    current_state[8] = animation_index;
    current_state[9] = in_vehicle;
    current_state[10] = vehicle_model;
    current_state[11] = floatround(velocity_x * 1000.0, floatround_round);
    current_state[12] = floatround(velocity_y * 1000.0, floatround_round);
    current_state[13] = floatround(velocity_z * 1000.0, floatround_round);

    new bool:changed = !g_DemonFFHasPlayerState;
    for (new index = 0; index < sizeof current_state; index++)
    {
        if (current_state[index] != g_DemonFFLastPlayerState[index])
        {
            changed = true;
            break;
        }
    }

    if (
        !force_write
        && !changed
        && current_tick - g_DemonFFLastPlayerWriteTick < 500
    )
    {
        return 0;
    }

    for (new index = 0; index < sizeof current_state; index++)
    {
        g_DemonFFLastPlayerState[index] = current_state[index];
    }

    g_DemonFFHasPlayerState = true;
    g_DemonFFLastPlayerWriteTick = current_tick;
    g_DemonFFPlayerRevision++;

    new line[512];
    format(
        line,
        sizeof line,
        "%d %d %d %f %f %f %f %d %d %d %d %d %d %d %d %f %f %f %d %s %s\r\n",
        g_DemonFFPlayerRevision,
        current_tick,
        playerid,
        x,
        y,
        z,
        angle,
        skin,
        keys,
        up_down,
        left_right,
        special_action,
        animation_index,
        in_vehicle,
        vehicle_model,
        velocity_x,
        velocity_y,
        velocity_z,
        g_DemonFFAnimationStartTick,
        animation_library,
        animation_name
    );

    new File:handle = fopen(DEMONFF_PLAYER_STATE_FILE, io_write);
    if (!handle)
    {
        return 0;
    }

    fwrite(handle, line);
    fclose(handle);
    return 1;
}

public OnGameModeInit()
{
    SetGameModeText("DemonFF Model Test");
    ShowPlayerMarkers(PLAYER_MARKERS_MODE_OFF);
    ShowNameTags(false);
    UsePlayerPedAnims();
    SetWorldTime(12);
    SetWeather(0);

    DemonFFReadLiveTransform();

    AddPlayerClass(
        0,
        g_DemonFFPosition[0],
        g_DemonFFPosition[1] - 8.0,
        g_DemonFFPosition[2] + 2.0,
        0.0,
        0,
        0,
        0,
        0,
        0,
        0
    );

    DemonFFLoadModelDefinitions();
    SetTimer("DemonFFPollTransform", 100, true);
    SetTimer("DemonFFPollPlayerState", 250, true);
    return 1;
}

public OnGameModeExit()
{
    DemonFFDestroyTestObjects();
    return 1;
}

public OnPlayerRequestClass(playerid, classid)
{
    SetSpawnInfo(
        playerid,
        0,
        0,
        g_DemonFFPosition[0],
        g_DemonFFPosition[1] - 8.0,
        g_DemonFFPosition[2] + 2.0,
        0.0,
        0,
        0,
        0,
        0,
        0,
        0
    );
    SpawnPlayer(playerid);
    return 1;
}

public OnPlayerSpawn(playerid)
{
    SetPlayerPos(
        playerid,
        g_DemonFFPosition[0],
        g_DemonFFPosition[1] - 8.0,
        g_DemonFFPosition[2] + 2.0
    );
    SetPlayerFacingAngle(playerid, 0.0);
    SetPlayerInterior(playerid, 0);
    SetPlayerVirtualWorld(playerid, 0);
    SetCameraBehindPlayer(playerid);
    Streamer_Update(playerid);
    DemonFFWritePlayerState(playerid, true);
    SendClientMessage(
        playerid,
        0xFFFFFFFF,
        "Connected to DemonFF. Waiting for custom model downloads to finish..."
    );
    return 1;
}

public OnPlayerFinishedDownloading(playerid, virtualworld)
{
    if (virtualworld == 0)
    {
        SetTimer("DemonFFCreateTestObject", 250, false);
        SendClientMessage(
            playerid,
            0xFFFFFFFF,
            "Custom model downloads finished. Loading selected Blender objects..."
        );
    }
    return 1;
}

public DemonFFPollTransform()
{
    DemonFFReadLiveTransform();
    return 1;
}

public DemonFFPollPlayerState()
{
    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {
        if (IsPlayerConnected(playerid))
        {
            DemonFFWritePlayerState(playerid, false);
            break;
        }
    }
    return 1;
}

public OnPlayerUpdate(playerid)
{
    DemonFFWritePlayerState(playerid, false);
    return 1;
}

stock DemonFFSetTimeForAllPlayers(hour)
{
    SetWorldTime(hour);

    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {
        if (IsPlayerConnected(playerid))
        {
            SetPlayerTime(playerid, hour, 0);
        }
    }
    return 1;
}

public OnPlayerCommandText(playerid, cmdtext[])
{
    if (!strcmp(cmdtext, "/day", true))
    {
        DemonFFSetTimeForAllPlayers(12);
        SendClientMessage(playerid, 0xFFFFFFFF, "Time set to day.");
        return 1;
    }

    if (!strcmp(cmdtext, "/night", true))
    {
        DemonFFSetTimeForAllPlayers(0);
        SendClientMessage(playerid, 0xFFFFFFFF, "Time set to night.");
        return 1;
    }

    return 0;
}

public OnRconCommand(cmd[])
{
    if (strfind(cmd, "demonff_transform ", true) != 0)
    {
        return 0;
    }

    new index = 18;
    new token[48];

    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFPosition[0] = floatstr(token);
    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFPosition[1] = floatstr(token);
    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFPosition[2] = floatstr(token);
    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFRotation[0] = floatstr(token);
    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFRotation[1] = floatstr(token);
    DemonFFReadToken(cmd, index, token, sizeof token);
    g_DemonFFRotation[2] = floatstr(token);

    DemonFFApplyTransform();
    return 1;
}

public DemonFFCreateTestObject()
{
    DemonFFDestroyTestObjects();

    g_DemonFFPlacementHandle = fopen(DEMONFF_PLACEMENT_FILE, io_read);
    if (!g_DemonFFPlacementHandle)
    {
        print("DemonFF: placement file could not be opened.");
        return 0;
    }

    print("DemonFF: loading selected placements in background batches...");
    SetTimer("DemonFFCreateTestObjectBatch", 1, false);
    return 1;
}

public DemonFFCreateTestObjectBatch()
{
    if (!g_DemonFFPlacementHandle)
    {
        return 0;
    }

    new line[256];
    new batch_count = 0;
    while (batch_count < 512 && fread(g_DemonFFPlacementHandle, line))
    {
        new index = 0;
        new token[64];
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new attach_to_pivot = strval(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new model_id = strval(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:offset_x = floatstr(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:offset_y = floatstr(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:offset_z = floatstr(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:rotation_x = floatstr(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:rotation_y = floatstr(token);
        if (!DemonFFReadToken(line, index, token, sizeof token)) continue;
        new Float:rotation_z = floatstr(token);

        if (!attach_to_pivot)
        {
            new static_objectid = CreateDynamicObject(
                model_id,
                offset_x,
                offset_y,
                offset_z,
                rotation_x,
                rotation_y,
                rotation_z,
                0,
                0,
                -1,
                __DRAW_DISTANCE__,
                __DRAW_DISTANCE__
            );

            if (IsValidDynamicObject(static_objectid))
            {
                g_DemonFFStaticObjectCount++;
                g_DemonFFTestObjectCount++;
            }
            batch_count++;
            continue;
        }

        if (!IsValidDynamicObject(g_DemonFFPivotObject))
        {
            g_DemonFFPivotObject = CreateDynamicObject(
                DEMONFF_PIVOT_MODEL_ID,
                g_DemonFFPosition[0],
                g_DemonFFPosition[1],
                g_DemonFFPosition[2],
                g_DemonFFRotation[0],
                g_DemonFFRotation[1],
                g_DemonFFRotation[2],
                0,
                0,
                -1,
                __DRAW_DISTANCE__,
                __DRAW_DISTANCE__
            );

            if (!IsValidDynamicObject(g_DemonFFPivotObject))
            {
                print("DemonFF: could not create the invisible transform pivot.");
                fclose(g_DemonFFPlacementHandle);
                g_DemonFFPlacementHandle = File:0;
                return 0;
            }

            SetDynamicObjectMaterial(
                g_DemonFFPivotObject,
                0,
                -1,
                "none",
                "none",
                0x00000000
            );
        }

        new objectid = CreateDynamicObject(
            model_id,
            g_DemonFFPosition[0],
            g_DemonFFPosition[1],
            g_DemonFFPosition[2],
            0.0,
            0.0,
            0.0,
            0,
            0,
            -1,
            __DRAW_DISTANCE__,
            __DRAW_DISTANCE__
        );

        if (IsValidDynamicObject(objectid))
        {
            AttachDynamicObjectToObject(
                objectid,
                g_DemonFFPivotObject,
                offset_x,
                offset_y,
                offset_z,
                rotation_x,
                rotation_y,
                rotation_z,
                true
            );
            g_DemonFFAttachedObjectCount++;
            g_DemonFFTestObjectCount++;
        }
        batch_count++;
    }

    if (batch_count == 512)
    {
        if (g_DemonFFTestObjectCount % 4096 < 512)
        {
            printf(
                "DemonFF: loaded %d placements (%d static, %d attached)...",
                g_DemonFFTestObjectCount,
                g_DemonFFStaticObjectCount,
                g_DemonFFAttachedObjectCount
            );
        }
        SetTimer("DemonFFCreateTestObjectBatch", 1, false);
        return 1;
    }

    fclose(g_DemonFFPlacementHandle);
    g_DemonFFPlacementHandle = File:0;
    printf(
        "DemonFF: finished loading %d placements (%d static, %d attached).",
        g_DemonFFTestObjectCount,
        g_DemonFFStaticObjectCount,
        g_DemonFFAttachedObjectCount
    );
    DemonFFRefreshPlayers();
    return 1;
}
"""

    replacements = {
        "__PAWN_INCLUDE__": pawn_include_name,
        "__MODEL_FILE__": TEST_MODEL_DEFINITION_FILE_NAME,
        "__PLACEMENT_FILE__": TEST_PLACEMENT_FILE_NAME,
        "__PLAYER_STATE_FILE__": PLAYER_STATE_FILE_NAME,
        "__LIVE_TRANSFORM_FILE__": LIVE_TRANSFORM_FILE_NAME,
        "__PIVOT_MODEL_ID__": str(TEST_PIVOT_MODEL_ID),
        "__DRAW_DISTANCE__": pawn_float(TEST_DRAW_DISTANCE),
    }
    for placeholder, value in replacements.items():
        source = source.replace(placeholder, value)
    return source

def write_and_compile_gamemode(server_root, compiler, include_directory, pawn_include_name):
    gamemodes_directory = server_root / "gamemodes"
    gamemodes_directory.mkdir(parents=True, exist_ok=True)

    source_path = gamemodes_directory / f"{TEST_MODE_NAME}.pwn"
    output_path = gamemodes_directory / f"{TEST_MODE_NAME}.amx"
    source_text = build_test_gamemode(pawn_include_name)

    existing_source = None
    try:
        existing_source = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).replace("\r\n", "\n")
    except OSError:
        pass

    source_changed = existing_source != source_text.replace("\r\n", "\n")
    if source_changed:
        source_path.write_text(
            source_text,
            encoding="utf-8",
            newline="\r\n",
        )

    if (
        not source_changed
        and output_path.is_file()
        and output_path.stat().st_size > 0
    ):
        test_progress("Pawn gamemode: unchanged AMX reused; compilation skipped")
        return source_path, output_path

    if output_path.exists():
        output_path.unlink()

    command = [
        str(compiler),
        source_path.name,
        f"-i{include_directory}{os.sep}",
        f"-o{output_path.name}",
    ]

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    test_progress("Pawn gamemode: source changed or AMX missing; compiling now")
    result = subprocess.run(
        command,
        cwd=str(gamemodes_directory),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )

    compiler_output = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part and part.strip()
    )
    if compiler_output:
        print(compiler_output)

    if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        detail = compiler_output.splitlines()[-1] if compiler_output else "Pawn compiler did not create the AMX file."
        raise RuntimeError(f"Pawn compilation failed: {detail}")

    test_progress("Pawn gamemode: compilation complete")
    return source_path, output_path

def get_object_identity(obj):
    try:
        return obj.as_pointer()
    except Exception:
        return id(obj)


def collect_object_subtree(root, maximum_count=None):
    if root is None:
        return []

    collected = []
    seen = set()
    pending = [root]

    while pending:
        obj = pending.pop()
        key = get_object_identity(obj)
        if key in seen:
            continue

        seen.add(key)
        collected.append(obj)

        if maximum_count is not None and len(collected) > maximum_count:
            return collected

        try:
            pending.extend(reversed(list(obj.children)))
        except Exception:
            pass

    return collected


def get_pawn_placement_key(obj):
    if obj is None:
        return None

    try:
        placement_id = str(obj.get("DemonFF_Pawn_Placement_ID", "")).strip()
        model_source = str(obj.get("DemonFF_Pawn_Model_Source", "")).strip()
    except Exception:
        return None

    if not placement_id:
        return None

    source_key = ""
    if model_source:
        source_key = os.path.normcase(os.path.normpath(model_source))

    return placement_id, source_key


def collect_pawn_placement_objects(context, active_object):
    placement_key = get_pawn_placement_key(active_object)
    if placement_key is None:
        return []

    placement_id, source_key = placement_key
    results = []

    for obj in context.scene.objects:
        object_key = get_pawn_placement_key(obj)
        if object_key is None:
            continue

        object_placement_id, object_source_key = object_key
        if object_placement_id != placement_id:
            continue
        if source_key and object_source_key != source_key:
            continue

        results.append(obj)

    return results


def choose_active_model_root(active_object):
    if active_object is None:
        return None

    root = active_object
    current = active_object

    while current.parent is not None:
        parent = current.parent
        parent_subtree = collect_object_subtree(
            parent,
            maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
        )

        if len(parent_subtree) > MAX_ACTIVE_MODEL_OBJECTS:
            break

        root = parent
        current = parent

    return root


def find_player_armature(active_object):
    if active_object is None:
        return None

    current = active_object
    while current is not None:
        if current.type == "ARMATURE":
            return current
        current = current.parent

    objects_to_check = [active_object]
    model_root = choose_active_model_root(active_object)
    if model_root is not None and model_root != active_object:
        objects_to_check.append(model_root)

    for obj in objects_to_check:
        try:
            for modifier in obj.modifiers:
                if modifier.type == "ARMATURE" and modifier.object is not None:
                    return modifier.object
        except (ReferenceError, RuntimeError, AttributeError):
            pass

    if model_root is not None:
        hierarchy = collect_object_subtree(
            model_root,
            maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
        )
        for obj in hierarchy:
            if obj.type == "ARMATURE":
                return obj
        for obj in hierarchy:
            try:
                for modifier in obj.modifiers:
                    if modifier.type == "ARMATURE" and modifier.object is not None:
                        return modifier.object
            except (ReferenceError, RuntimeError, AttributeError):
                pass

    return None


def resolve_player_sync_components(selected_target):
    if selected_target is None:
        return None, None

    armature = find_player_armature(selected_target)
    root_source = armature if armature is not None else selected_target
    motion_target = choose_active_model_root(root_source)
    if motion_target is None:
        motion_target = root_source
    return motion_target, armature


def choose_player_sync_target(active_object):
    motion_target, _armature = resolve_player_sync_components(active_object)
    return motion_target


def object_is_ancestor(ancestor, obj):
    if ancestor is None or obj is None:
        return False

    current = obj
    while current is not None:
        if current == ancestor:
            return True
        current = current.parent
    return False


def objects_share_transform_hierarchy(first_object, second_object):
    return (
        object_is_ancestor(first_object, second_object)
        or object_is_ancestor(second_object, first_object)
    )


def build_pawn_placement_object_index(context):
    placement_index = {}

    for obj in context.scene.objects:
        placement_key = get_pawn_placement_key(obj)
        if placement_key is None:
            continue
        placement_index.setdefault(placement_key, []).append(obj)

    return placement_index


def set_live_player_export_exclusion(root_object, enabled):
    if root_object is None:
        return

    motion_target, armature = resolve_player_sync_components(root_object)
    transform_roots, model_collection = collect_player_transform_roots(
        root_object,
        armature,
    )

    objects = []
    seen = set()

    def add_object(obj):
        if obj is None:
            return
        key = get_object_identity(obj)
        if key in seen:
            return
        seen.add(key)
        objects.append(obj)

    add_object(root_object)
    add_object(motion_target)
    add_object(armature)

    for transform_root in transform_roots:
        for obj in collect_object_subtree(
            transform_root,
            maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
        ):
            add_object(obj)

    if model_collection is not None:
        for obj in get_object_all_collection_objects(model_collection):
            add_object(obj)

    for obj in objects:
        try:
            if enabled:
                obj[LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY] = True
            elif LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY in obj:
                del obj[LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY]
        except Exception:
            pass


def refresh_live_player_export_exclusions(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return

    for obj in getattr(scene, "objects", ()):
        try:
            if LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY in obj:
                del obj[LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY]
        except Exception:
            pass

    scene_dff = getattr(scene, "dff", None)
    target_object = getattr(scene_dff, "samp_player_target", None) if scene_dff is not None else None
    if target_object is not None:
        set_live_player_export_exclusion(target_object, True)


def set_configured_player_sync_target(context, target_object):
    scene_dff = getattr(getattr(context, "scene", None), "dff", None)
    if scene_dff is None:
        return target_object

    previous_target = getattr(scene_dff, "samp_player_target", None)
    if previous_target is not None and previous_target != target_object:
        set_live_player_export_exclusion(previous_target, False)

    scene_dff.samp_player_target = target_object
    if target_object is not None:
        set_live_player_export_exclusion(target_object, True)
    return target_object


def is_live_player_export_excluded(obj):
    current = obj
    while current is not None:
        try:
            if bool(current.get(LIVE_PLAYER_EXPORT_EXCLUDE_PROPERTY, False)):
                return True
        except Exception:
            pass
        current = getattr(current, "parent", None)
    return False


def get_selected_test_seed_objects(context):
    selected_objects = [
        obj for obj in context.selected_objects
        if not is_live_player_export_excluded(obj)
    ]
    active_object = context.view_layer.objects.active
    if is_live_player_export_excluded(active_object):
        active_object = None

    if active_object is not None and active_object in selected_objects:
        selected_objects.remove(active_object)
        selected_objects.insert(0, active_object)
    elif active_object is not None and not selected_objects:
        selected_objects.append(active_object)

    return selected_objects


def collect_selected_model_objects(context):
    seed_objects = get_selected_test_seed_objects(context)
    if not seed_objects:
        return []

    placement_index = build_pawn_placement_object_index(context)
    selected_roots = []
    selected_root_keys = set()
    direct_groups = []

    for seed_object in seed_objects:
        placement_key = get_pawn_placement_key(seed_object)
        placement_objects = placement_index.get(placement_key, []) if placement_key else []

        if placement_objects and len(placement_objects) <= MAX_ACTIVE_MODEL_OBJECTS:
            direct_groups.append(placement_objects)
            continue

        model_root = choose_active_model_root(seed_object)
        if model_root is None:
            model_root = seed_object

        root_key = get_object_identity(model_root)
        if root_key in selected_root_keys:
            continue

        selected_root_keys.add(root_key)
        selected_roots.append((model_root, seed_object))

    collected = []
    collected_keys = set()

    def add_objects(objects):
        for obj in objects:
            if is_live_player_export_excluded(obj):
                continue

            object_key = get_object_identity(obj)
            if object_key in collected_keys:
                continue

            collected_keys.add(object_key)
            collected.append(obj)

            if len(collected) > MAX_PACKED_TEST_OBJECTS:
                raise RuntimeError(
                    "The selection resolves to more than %d Blender objects. "
                    "Select a smaller test chunk or split it into separate tests."
                    % MAX_PACKED_TEST_OBJECTS
                )

    for placement_objects in direct_groups:
        add_objects(placement_objects)

    for model_root, seed_object in selected_roots:
        hierarchy = collect_object_subtree(
            model_root,
            maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
        )

        if len(hierarchy) > MAX_ACTIVE_MODEL_OBJECTS:
            hierarchy = collect_object_subtree(
                seed_object,
                maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
            )

        add_objects(hierarchy)

    return collected

def is_test_collision_object(obj):
    try:
        return getattr(getattr(obj, 'dff', None), 'type', '') in {'COL', 'SHA'}
    except Exception:
        return False


def is_test_render_mesh_object(obj):
    if obj is None or obj.type != "MESH" or obj.data is None:
        return False

    try:
        object_type = getattr(getattr(obj, "dff", None), "type", "")
    except Exception:
        object_type = ""

    return object_type not in {"COL", "SHA", "2DFX"}


def copy_collision_settings(source_object, collision_object):
    try:
        collision_object.dff.type = "COL"
    except Exception:
        return

    for property_name in (
        "col_material",
        "col_flags",
        "col_brightness",
        "col_light",
    ):
        try:
            setattr(
                collision_object.dff,
                property_name,
                getattr(source_object.dff, property_name),
            )
        except Exception:
            pass


def create_temporary_box_collision(context, export_objects, live_anchor):
    collision_collection = bpy.data.collections.new("DemonFF Test Collision")
    context.scene.collection.children.link(collision_collection)

    collision_mesh = None
    collision_object = None

    try:
        anchor_matrix = live_anchor.matrix_world.copy()
        anchor_inverse = anchor_matrix.inverted_safe()
        local_points = []

        for source_object in export_objects:
            if not is_test_render_mesh_object(source_object):
                continue

            bounding_box = source_object.bound_box
            object_matrix = source_object.matrix_world

            for corner in bounding_box:
                world_point = object_matrix @ mathutils.Vector(corner)
                local_points.append(anchor_inverse @ world_point)

        if not local_points:
            raise RuntimeError(
                "The active model does not contain geometry that can form a test collision box."
            )

        minimum = mathutils.Vector((
            min(point.x for point in local_points),
            min(point.y for point in local_points),
            min(point.z for point in local_points),
        ))
        maximum = mathutils.Vector((
            max(point.x for point in local_points),
            max(point.y for point in local_points),
            max(point.z for point in local_points),
        ))

        minimum_size = 0.01
        for axis in range(3):
            if maximum[axis] - minimum[axis] < minimum_size:
                center = (minimum[axis] + maximum[axis]) * 0.5
                minimum[axis] = center - minimum_size * 0.5
                maximum[axis] = center + minimum_size * 0.5

        vertices = [
            (minimum.x, minimum.y, minimum.z),
            (maximum.x, minimum.y, minimum.z),
            (maximum.x, maximum.y, minimum.z),
            (minimum.x, maximum.y, minimum.z),
            (minimum.x, minimum.y, maximum.z),
            (maximum.x, minimum.y, maximum.z),
            (maximum.x, maximum.y, maximum.z),
            (minimum.x, maximum.y, maximum.z),
        ]
        faces = [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ]

        collision_mesh = bpy.data.meshes.new("DemonFF.TestCollisionBoxMesh")
        collision_mesh.from_pydata(vertices, [], faces)
        collision_mesh.update()

        collision_object = bpy.data.objects.new(
            "DemonFF.TestCollisionBox",
            collision_mesh,
        )
        collision_collection.objects.link(collision_object)
        collision_object.matrix_world = anchor_matrix
        collision_object.hide_render = True
        collision_object.hide_set(True)
        collision_object.dff.type = "COL"
        collision_object["demonff_test_generated_collision"] = True
        collision_object["demonff_collision_source_object"] = live_anchor.name

        try:
            copy_collision_settings(live_anchor, collision_object)
        except Exception:
            pass

        return collision_collection, [collision_object], [collision_mesh]
    except Exception:
        remove_temporary_test_collision(
            collision_collection,
            [collision_object] if collision_object is not None else [],
            [collision_mesh] if collision_mesh is not None else [],
        )
        raise


def create_temporary_test_collision(context, export_objects, live_anchor, mode):
    if mode == "FAST_BOX":
        return create_temporary_box_collision(
            context,
            export_objects,
            live_anchor,
        )

    collision_collection = bpy.data.collections.new("DemonFF Test Collision")
    context.scene.collection.children.link(collision_collection)

    collision_objects = []
    collision_meshes = []

    try:
        for source_object in export_objects:
            if not is_test_render_mesh_object(source_object):
                continue

            try:
                depsgraph = context.evaluated_depsgraph_get()
                evaluated_object = source_object.evaluated_get(depsgraph)
                collision_mesh = bpy.data.meshes.new_from_object(
                    evaluated_object,
                    depsgraph=depsgraph,
                )
            except Exception:
                collision_mesh = source_object.data.copy()

            collision_mesh.name = f"{source_object.name}.TestCollisionMesh"

            collision_object = bpy.data.objects.new(
                f"{source_object.name}.TestCollision",
                collision_mesh,
            )
            collision_collection.objects.link(collision_object)
            collision_object.matrix_world = source_object.matrix_world.copy()
            collision_object.hide_render = True
            collision_object.hide_set(True)

            copy_collision_settings(source_object, collision_object)
            collision_object["demonff_test_generated_collision"] = True
            collision_object["demonff_collision_source_object"] = source_object.name

            try:
                collision_object["demonff_collision_source_matrix_world"] = [
                    list(row) for row in source_object.matrix_world
                ]
            except Exception:
                pass

            collision_objects.append(collision_object)
            collision_meshes.append(collision_mesh)

        if not collision_objects:
            raise RuntimeError(
                "The selected model does not contain a mesh that can be used for collision."
            )

        return collision_collection, collision_objects, collision_meshes
    except Exception:
        remove_temporary_test_collision(
            collision_collection,
            collision_objects,
            collision_meshes,
        )
        raise


def remove_temporary_test_collision(collection, objects, meshes):
    for obj in list(objects):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass

    if collection is not None:
        try:
            bpy.data.collections.remove(collection)
        except Exception:
            pass

    for mesh in list(meshes):
        try:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception:
            pass


def collect_exact_test_collision_objects(context, export_objects, live_anchor):
    collisions = []
    seen = set()

    for obj in export_objects:
        if not is_test_collision_object(obj):
            continue
        try:
            key = obj.as_pointer()
        except Exception:
            key = id(obj)
        if key in seen:
            continue
        seen.add(key)
        collisions.append(obj)

    if collisions or live_anchor is None:
        return collisions

    try:
        placement_id = str(live_anchor.get('DemonFF_Pawn_Placement_ID', '')).strip()
        model_source = str(live_anchor.get('DemonFF_Pawn_Model_Source', '')).strip()
    except Exception:
        placement_id = ''
        model_source = ''

    if not placement_id:
        return []

    model_source_key = os.path.normcase(os.path.normpath(model_source)) if model_source else ''

    for obj in context.scene.objects:
        if not is_test_collision_object(obj):
            continue
        try:
            object_placement_id = str(obj.get('DemonFF_Pawn_Placement_ID', '')).strip()
            object_model_source = str(obj.get('DemonFF_Pawn_Model_Source', '')).strip()
        except Exception:
            continue

        if object_placement_id != placement_id:
            continue
        if model_source_key:
            if not object_model_source:
                continue
            object_source_key = os.path.normcase(os.path.normpath(object_model_source))
            if object_source_key != model_source_key:
                continue

        try:
            key = obj.as_pointer()
        except Exception:
            key = id(obj)
        if key in seen:
            continue
        seen.add(key)
        collisions.append(obj)

    return collisions


def set_export_selection(context, export_objects):
    original_selected = list(context.selected_objects)
    original_active = context.view_layer.objects.active

    for obj in original_selected:
        try:
            obj.select_set(False)
        except Exception:
            pass

    selectable_objects = []
    for obj in export_objects:
        try:
            obj.select_set(True)
            selectable_objects.append(obj)
        except Exception:
            pass

    if selectable_objects:
        active_object = next(
            (obj for obj in selectable_objects if obj.type == "MESH"),
            selectable_objects[0],
        )
        context.view_layer.objects.active = active_object

    return original_selected, original_active

def restore_selection(context, original_selected, original_active):
    for obj in list(context.selected_objects):
        try:
            obj.select_set(False)
        except Exception:
            pass

    for obj in original_selected:
        try:
            obj.select_set(True)
        except Exception:
            pass

    try:
        context.view_layer.objects.active = original_active
    except Exception:
        pass


def write_text_if_changed(path, text):
    path = Path(path)
    try:
        existing = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        existing = None

    if existing == text:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".demonff_tmp")
    temporary_path.write_text(text, encoding="utf-8", newline="\r\n")
    os.replace(temporary_path, path)
    return True


def remove_generated_fast_model_files(models_directory, keep_names=None):
    keep_names = set(keep_names or ())
    if not models_directory.is_dir():
        return

    for pattern in GENERATED_TEST_MODEL_PATTERNS:
        for path in models_directory.glob(pattern):
            if path.name in keep_names:
                continue
            try:
                path.unlink()
            except OSError:
                pass


def stable_test_asset_name(source_path, extension):
    normalized = os.path.normcase(os.path.normpath(str(Path(source_path).absolute())))
    digest = hashlib.blake2s(
        normalized.encode("utf-8", errors="surrogatepass"),
        digest_size=6,
    ).hexdigest()
    suffix = str(extension).lower().lstrip(".")
    type_prefix = "d" if suffix == "dff" else "t"
    return f"{type_prefix}{digest}.{suffix}"


def install_test_asset(source_path, target_path):
    source_path = Path(source_path)
    target_path = Path(target_path)

    if not source_path.is_file():
        raise RuntimeError(f"The selected model source file is missing: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if target_path.exists() and os.path.samefile(source_path, target_path):
            return "linked"
    except OSError:
        pass

    try:
        if target_path.is_file():
            source_stat = source_path.stat()
            target_stat = target_path.stat()
            if (
                source_stat.st_size == target_stat.st_size
                and source_stat.st_mtime_ns == target_stat.st_mtime_ns
            ):
                return "reused"
    except OSError:
        pass

    try:
        if target_path.exists():
            target_path.unlink()
    except OSError as error:
        raise RuntimeError(f"Could not replace the generated test asset {target_path}: {error}") from error

    try:
        os.link(str(source_path), str(target_path))
        return "linked"
    except OSError:
        pass

    try:
        os.symlink(str(source_path), str(target_path))
        return "symlinked"
    except OSError:
        temporary_path = target_path.with_name(target_path.name + ".demonff_tmp")
        try:
            if temporary_path.exists():
                temporary_path.unlink()
            shutil.copy2(str(source_path), str(temporary_path))
            os.replace(str(temporary_path), str(target_path))
        except OSError as error:
            try:
                if temporary_path.exists():
                    temporary_path.unlink()
            except OSError:
                pass
            raise RuntimeError(f"Could not prepare the generated test asset {target_path}: {error}") from error
        return "copied"


def get_scene_test_asset_roots(extension):
    roots = []
    extension = str(extension or "").lower()

    try:
        settings = bpy.context.scene.dff
    except Exception:
        settings = None

    if settings is not None:
        property_names = (
            ("pawn_txd_root", "pawn_dff_root")
            if extension == ".txd"
            else ("pawn_dff_root", "pawn_txd_root")
        )
        for property_name in property_names:
            try:
                root_text = str(getattr(settings, property_name, "") or "").strip()
            except Exception:
                root_text = ""
            if not root_text:
                continue
            try:
                root_text = bpy.path.abspath(root_text)
            except Exception:
                pass
            root = Path(os.path.expandvars(os.path.expanduser(root_text)))
            if root.is_dir():
                roots.append(root)

    try:
        last_pwn_file = str(
            bpy.context.scene.get("DemonFF_Last_PWN_File", "") or ""
        ).strip()
    except Exception:
        last_pwn_file = ""
    if last_pwn_file:
        pwn_directory = Path(last_pwn_file).parent
        if pwn_directory.is_dir():
            roots.append(pwn_directory)
            models_directory = pwn_directory / "models"
            if models_directory.is_dir():
                roots.append(models_directory)

    if bpy.data.filepath:
        roots.append(Path(bpy.data.filepath).parent)

    unique_roots = []
    seen = set()
    for root in roots:
        key = os.path.normcase(os.path.normpath(str(root)))
        if key in seen:
            continue
        seen.add(key)
        unique_roots.append(root)
    return unique_roots


def get_test_asset_index(root, extension):
    root = Path(root)
    extension = str(extension or "").lower()
    cache_key = (
        os.path.normcase(os.path.normpath(str(root))),
        extension,
    )
    cached = TEST_ASSET_INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached

    basename_index = {}
    relative_index = {}
    test_progress(
        "Source recovery: indexing %s files below %s"
        % (extension or "asset", root)
    )
    scanned = 0
    try:
        for directory, _directory_names, file_names in os.walk(str(root)):
            for file_name in file_names:
                if extension and not file_name.lower().endswith(extension):
                    continue
                path = Path(directory) / file_name
                try:
                    relative = path.relative_to(root).as_posix().lower()
                except ValueError:
                    relative = file_name.lower()
                relative_index.setdefault(relative, path)
                basename_index.setdefault(file_name.lower(), path)
                scanned += 1
    except OSError:
        pass

    cached = {
        "relative": relative_index,
        "basename": basename_index,
    }
    TEST_ASSET_INDEX_CACHE[cache_key] = cached
    test_progress(
        "Source recovery: indexed %d %s file(s) below %s"
        % (scanned, extension or "asset", root)
    )
    return cached


def resolve_test_asset_path(value, expected_extension=""):
    text = str(value or "").strip().strip('"')
    if not text:
        return None

    normalized_text = normalize_test_asset_relative_path(text)
    extension = str(expected_extension or Path(normalized_text).suffix).lower()
    if extension and not extension.startswith("."):
        extension = "." + extension

    try:
        expanded = bpy.path.abspath(text)
    except Exception:
        expanded = text

    path = Path(os.path.expandvars(os.path.expanduser(expanded)))
    if path.is_file():
        return path

    candidate_relative = normalized_text
    candidate_name = Path(candidate_relative).name
    roots = get_scene_test_asset_roots(extension)

    for root in roots:
        direct_candidates = [
            root / Path(candidate_relative.replace('/', os.sep)),
            root / candidate_name,
            root.parent / Path(candidate_relative.replace('/', os.sep)),
        ]

        relative_parts = PurePosixPath(candidate_relative).parts
        if relative_parts and relative_parts[0].lower() == root.name.lower():
            direct_candidates.append(root / Path(*relative_parts[1:]))
        if relative_parts and relative_parts[0].lower() == "models" and root.name.lower() == "models":
            direct_candidates.append(root / Path(*relative_parts[1:]))

        for candidate in direct_candidates:
            if candidate.is_file():
                return candidate

    relative_key = candidate_relative.lower()
    basename_key = candidate_name.lower()
    for root in roots:
        index = get_test_asset_index(root, extension)
        indexed_path = index["relative"].get(relative_key)
        if indexed_path is None:
            indexed_path = index["basename"].get(basename_key)
        if indexed_path is not None and indexed_path.is_file():
            return indexed_path

    return None


def normalize_test_asset_relative_path(value):
    text = str(value or "").strip().strip('"').replace('\\', '/')
    while text.startswith('./'):
        text = text[2:]
    return text.lstrip('/')


def get_object_txd_name(obj):
    value = get_object_string_property(
        obj,
        (
            "TXD_Name",
            "Pawn_TXD_Name",
        ),
    )
    if value:
        return value

    try:
        dff_map = getattr(obj, "dff_map", None)
        for property_name in ("pawn_txd_name", "ide_txd_name"):
            value = str(getattr(dff_map, property_name, "") or "").strip()
            if value:
                return value
    except Exception:
        pass

    return ""


def get_object_dff_name(obj):
    value = get_object_string_property(
        obj,
        (
            "DFF_Name",
            "Pawn_DFF_Name",
            "DemonFF_Pawn_Model_Key",
        ),
    )
    if value:
        return value

    try:
        dff_map = getattr(obj, "dff_map", None)
        for property_name in (
            "pawn_model_name",
            "ide_model_name",
            "model_name",
        ):
            value = str(getattr(dff_map, property_name, "") or "").strip()
            if value:
                return value
    except Exception:
        pass

    return ""


def resolve_test_txd_path(obj, dff_path):
    direct_values = (
        get_object_string_property(obj, ("DemonFF_Pawn_TXD_Source",)),
        get_object_string_property(obj, ("Pawn_TXD_Path",)),
    )

    for value in direct_values:
        resolved = resolve_test_asset_path(value, ".txd")
        if resolved is not None:
            return resolved

    candidate_relative_paths = []
    candidate_basenames = []

    for value in direct_values:
        normalized = normalize_test_asset_relative_path(value)
        if not normalized:
            continue
        if not normalized.lower().endswith('.txd'):
            normalized += '.txd'
        candidate_relative_paths.append(normalized)
        candidate_basenames.append(Path(normalized).name)

    txd_name = get_object_txd_name(obj)
    if txd_name:
        txd_filename = txd_name if txd_name.lower().endswith('.txd') else txd_name + '.txd'
        candidate_basenames.append(Path(txd_filename).name)
        resolved = resolve_test_asset_path(txd_filename, ".txd")
        if resolved is not None:
            return resolved

    if dff_path is not None:
        candidate_basenames.append(Path(dff_path).with_suffix('.txd').name)

    candidate_basenames = list(dict.fromkeys(
        name for name in candidate_basenames if name
    ))
    candidate_relative_paths = list(dict.fromkeys(
        path for path in candidate_relative_paths if path
    ))

    search_roots = []
    if dff_path is not None:
        current = Path(dff_path).parent
        for _level in range(6):
            if current not in search_roots:
                search_roots.append(current)
            if current.parent == current:
                break
            current = current.parent

    if bpy.data.filepath:
        blend_root = Path(bpy.data.filepath).parent
        if blend_root not in search_roots:
            search_roots.append(blend_root)

    for search_root in search_roots:
        for basename in candidate_basenames:
            candidate = search_root / basename
            if candidate.is_file():
                return candidate

        for relative_path in candidate_relative_paths:
            candidate = search_root / Path(relative_path.replace('/', os.sep))
            if candidate.is_file():
                return candidate

    return None


def get_object_string_property(obj, names):
    for name in names:
        try:
            value = str(obj.get(name, "")).strip()
        except Exception:
            value = ""
        if value:
            return value
    return ""


def get_fast_test_asset_paths(obj):
    dff_values = (
        get_object_string_property(obj, ("DemonFF_Pawn_Model_Source",)),
        get_object_string_property(obj, ("Pawn_DFF_Path",)),
    )

    dff_path = None
    for value in dff_values:
        dff_path = resolve_test_asset_path(value, ".dff")
        if dff_path is not None:
            break

    if dff_path is None:
        dff_name = get_object_dff_name(obj)
        if dff_name:
            if not dff_name.lower().endswith(".dff"):
                dff_name += ".dff"
            dff_path = resolve_test_asset_path(dff_name, ".dff")

    if dff_path is None:
        return None, None

    txd_path = resolve_test_txd_path(obj, dff_path)
    return dff_path, txd_path


def get_fast_test_base_model_id(obj):
    for property_name in ("IDE_ID", "Pawn_Base_Model_ID"):
        try:
            value = int(obj.get(property_name, 0))
        except Exception:
            value = 0
        if value > 0:
            return value

    try:
        value = int(getattr(getattr(obj, "dff_map", None), "ide_object_id", 0))
    except Exception:
        value = 0
    if value > 0:
        return value

    return TEST_BASE_MODEL_ID


def find_fast_test_placement_anchor(seed_object):
    current = seed_object

    while current is not None:
        placement_key = get_pawn_placement_key(current)
        if placement_key is not None:
            anchor = current
            while anchor.parent is not None:
                parent = anchor.parent
                if get_pawn_placement_key(parent) != placement_key:
                    break
                anchor = parent
            return anchor
        current = current.parent

    return None


def get_legacy_pawn_model_descriptor(obj):
    if obj is None:
        return None

    dff_source = get_object_string_property(
        obj,
        ("DemonFF_Pawn_Model_Source", "Pawn_DFF_Path"),
    )
    model_name = get_object_string_property(
        obj,
        ("DemonFF_Pawn_Model_Key", "DFF_Name"),
    )

    try:
        pawn_instance = bool(obj.get("DemonFF_Pawn_Instance", False))
    except Exception:
        pawn_instance = False

    model_id = None
    for property_name in (
        "DemonFF_Pawn_Model_ID",
        "Pawn_Model_ID",
        "SAMP_ID",
    ):
        try:
            value = int(obj.get(property_name, 0))
        except Exception:
            value = 0
        if value:
            model_id = value
            break

    if not dff_source and not model_name and model_id is None and not pawn_instance:
        return None

    normalized_source = normalize_test_asset_relative_path(dff_source).lower()
    return (
        normalized_source,
        str(model_name or "").lower(),
        model_id,
    )


def find_legacy_pawn_placement_anchor(seed_object):
    descriptor = get_legacy_pawn_model_descriptor(seed_object)
    if descriptor is None:
        return None

    anchor = seed_object
    current = seed_object
    while current.parent is not None:
        parent = current.parent
        if get_legacy_pawn_model_descriptor(parent) != descriptor:
            break
        anchor = parent
        current = parent
    return anchor


def find_reusable_test_placement_anchor(seed_object):
    anchor = find_fast_test_placement_anchor(seed_object)
    if anchor is not None:
        return anchor, False

    anchor = find_legacy_pawn_placement_anchor(seed_object)
    if anchor is not None:
        return anchor, True
    return None, False


def get_reusable_test_placement_key(anchor, legacy):
    if anchor is None:
        return None

    if not legacy:
        placement_key = get_pawn_placement_key(anchor)
        if placement_key is not None:
            return ("metadata",) + tuple(placement_key)

    return ("legacy", get_object_identity(anchor))


def matrix_has_unit_scale(matrix, tolerance=1.0e-4):
    try:
        scale = matrix.decompose()[2]
    except Exception:
        return False

    return all(abs(abs(float(component)) - 1.0) <= tolerance for component in scale)


def collect_fast_test_placements(context):
    set_fast_test_rejection("")
    seed_objects = get_selected_test_seed_objects(context)
    if not seed_objects:
        set_fast_test_rejection("nothing is selected")
        return None

    total_seed_count = len(seed_objects)
    test_progress(f"Selection scan: {total_seed_count} selected Blender object(s)")

    active_object = context.view_layer.objects.active
    active_anchor, active_legacy = find_reusable_test_placement_anchor(active_object)
    active_key = get_reusable_test_placement_key(active_anchor, active_legacy)

    placements_by_key = {}
    asset_path_cache = {}
    unsupported_count = 0
    unsupported_render_count = 0
    missing_dff_count = 0
    missing_txd_count = 0
    scaled_count = 0
    duplicate_component_count = 0
    legacy_placement_count = 0

    for index, seed_object in enumerate(seed_objects, 1):
        placement_anchor, legacy = find_reusable_test_placement_anchor(seed_object)
        placement_key = get_reusable_test_placement_key(placement_anchor, legacy)
        if placement_anchor is None or placement_key is None:
            unsupported_count += 1
            if is_test_render_mesh_object(seed_object):
                unsupported_render_count += 1
            continue

        if placement_key in placements_by_key:
            duplicate_component_count += 1
            continue

        dff_source_text = get_object_string_property(
            placement_anchor,
            ("DemonFF_Pawn_Model_Source", "Pawn_DFF_Path"),
        )
        txd_source_text = get_object_string_property(
            placement_anchor,
            ("DemonFF_Pawn_TXD_Source", "Pawn_TXD_Path", "TXD_Name"),
        )
        asset_cache_key = (
            dff_source_text or get_object_dff_name(placement_anchor),
            txd_source_text or get_object_txd_name(placement_anchor),
        )
        if asset_cache_key not in asset_path_cache:
            asset_path_cache[asset_cache_key] = get_fast_test_asset_paths(
                placement_anchor
            )

        dff_path, txd_path = asset_path_cache[asset_cache_key]
        if dff_path is None:
            missing_dff_count += 1
            continue
        if txd_path is None:
            missing_txd_count += 1

        if not matrix_has_unit_scale(placement_anchor.matrix_world):
            scaled_count += 1
            continue

        placements_by_key[placement_key] = {
            "key": placement_key,
            "object": placement_anchor,
            "dff_path": dff_path,
            "txd_path": txd_path,
            "base_model_id": get_fast_test_base_model_id(placement_anchor),
        }
        if legacy:
            legacy_placement_count += 1

        if progress_checkpoint(index, total_seed_count, maximum_messages=30):
            test_progress(
                f"Selection scan: found {len(placements_by_key)} reusable placement(s)",
                index,
                total_seed_count,
            )

    placements = list(placements_by_key.values())
    incomplete_selection = (
        unsupported_render_count > 0
        or missing_dff_count > 0
        or scaled_count > 0
    )
    if len(placements) < FAST_TEST_PLACEMENT_THRESHOLD or incomplete_selection:
        reason_parts = [f"only {len(placements)} reusable map placement(s) were found"]
        if unsupported_count:
            reason_parts.append(f"{unsupported_count} selected object(s) had no Pawn placement metadata")
        if unsupported_render_count:
            reason_parts.append(
                f"{unsupported_render_count} selected render object(s) require Blender export"
            )
        if missing_dff_count:
            reason_parts.append(f"{missing_dff_count} placement(s) had no reusable source DFF")
        if scaled_count:
            reason_parts.append(f"{scaled_count} placement(s) used unapplied scale")
        set_fast_test_rejection("; ".join(reason_parts))
        return None

    placements.sort(
        key=lambda item: (
            0 if item["key"] == active_key else 1,
            str(item["key"][1]).lower(),
            str(item["key"][0]),
        )
    )

    skipped_count = unsupported_count + missing_dff_count + scaled_count
    test_progress(
        "Fast placement path accepted: %d placement(s), %d cached source record(s), "
        "%d duplicate hierarchy component(s) collapsed"
        % (len(placements), len(asset_path_cache), duplicate_component_count)
    )
    if legacy_placement_count:
        test_progress(
            "Fast placement path: recovered %d placement(s) from the existing Blender scene; reimport is not required"
            % legacy_placement_count
        )
    if missing_txd_count:
        test_progress(
            "Fast placement path: %d placement(s) have no reusable source TXD; "
            "Blender material packs or one shared empty fallback TXD will be used"
            % missing_txd_count
        )
    if skipped_count:
        test_progress(
            "WARNING: skipped %d selected item(s) that were not valid reusable map placements "
            "(%d without metadata, %d missing DFFs, %d scaled)"
            % (skipped_count, unsupported_count, missing_dff_count, scaled_count)
        )

    return placements


def get_object_pointer(value):
    if value is None:
        return 0
    try:
        return int(value.as_pointer())
    except Exception:
        return id(value)


def get_fast_root_for_seed(seed_object, parent_size_state):
    root = seed_object
    current = seed_object

    while current.parent is not None:
        parent = current.parent
        parent_key = get_object_identity(parent)
        parent_is_small = parent_size_state.get(parent_key)

        if parent_is_small is None:
            parent_hierarchy = collect_object_subtree(
                parent,
                maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
            )
            parent_is_small = len(parent_hierarchy) <= MAX_ACTIVE_MODEL_OBJECTS
            parent_size_state[parent_key] = parent_is_small

        if not parent_is_small:
            break

        root = parent
        current = parent

    return root


def get_linked_instance_signature(root, hierarchy):
    hierarchy_set = set(hierarchy)
    object_indices = {obj: index for index, obj in enumerate(hierarchy)}
    signature = []

    for obj in hierarchy:
        parent_index = object_indices.get(obj.parent, -1)
        if obj == root:
            local_matrix_values = ()
        else:
            local_matrix_values = tuple(
                round(float(value), 6)
                for row in obj.matrix_local
                for value in row
            )

        materials = []
        try:
            for material_slot in obj.material_slots:
                materials.append(get_object_pointer(material_slot.material))
        except Exception:
            pass

        modifiers = []
        try:
            for modifier in obj.modifiers:
                target = getattr(modifier, "object", None)
                if target in hierarchy_set:
                    target_key = object_indices[target]
                else:
                    target_key = get_object_pointer(target)
                modifiers.append((modifier.type, target_key, bool(modifier.show_viewport)))
        except Exception:
            pass

        try:
            dff_type = str(getattr(getattr(obj, "dff", None), "type", ""))
        except Exception:
            dff_type = ""

        signature.append((
            obj.type,
            get_object_pointer(obj.data),
            dff_type,
            parent_index,
            local_matrix_values,
            tuple(materials),
            tuple(modifiers),
        ))

    return tuple(signature)


def collect_linked_instance_test_placements(context):
    seed_objects = get_selected_test_seed_objects(context)
    if not seed_objects:
        return None

    test_progress(
        "Linked-instance fallback: checking whether selected objects share Blender mesh data"
    )

    parent_size_state = {}
    roots = []
    seen_roots = set()
    active_object = context.view_layer.objects.active
    active_root = None

    for seed_index, seed_object in enumerate(seed_objects, 1):
        root = get_fast_root_for_seed(seed_object, parent_size_state)
        root_key = get_object_identity(root)
        if root_key not in seen_roots:
            seen_roots.add(root_key)
            roots.append(root)
        if seed_object == active_object:
            active_root = root

        if progress_checkpoint(seed_index, len(seed_objects)):
            test_progress(
                f"Linked-instance root scan: {len(roots)} root placement(s)",
                seed_index,
                len(seed_objects),
            )

    if len(roots) < FAST_TEST_PLACEMENT_THRESHOLD:
        return None

    if active_root is None:
        active_root = roots[0]

    models_by_signature = {}
    placements = []
    skipped_scaled = 0
    skipped_empty = 0
    skipped_large = 0

    for root_index, root in enumerate(roots, 1):
        if not matrix_has_unit_scale(root.matrix_world):
            skipped_scaled += 1
            continue

        hierarchy = collect_object_subtree(
            root,
            maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
        )
        if not hierarchy:
            skipped_empty += 1
            continue
        if len(hierarchy) > MAX_ACTIVE_MODEL_OBJECTS:
            skipped_large += 1
            continue
        if not any(is_test_render_mesh_object(obj) for obj in hierarchy):
            skipped_empty += 1
            continue

        signature = get_linked_instance_signature(root, hierarchy)
        model = models_by_signature.get(signature)
        if model is None:
            model = {
                "signature": signature,
                "root": root,
                "hierarchy": hierarchy,
                "base_model_id": get_fast_test_base_model_id(root),
            }
            models_by_signature[signature] = model

        placements.append({
            "object": root,
            "model": model,
        })

        if progress_checkpoint(root_index, len(roots)):
            test_progress(
                f"Linked-instance signature scan: {len(models_by_signature)} unique model(s)",
                root_index,
                len(roots),
            )

    if skipped_scaled or skipped_empty or skipped_large:
        test_progress(
            "Linked-instance scan skipped %d scaled, %d non-render and %d oversized root(s)"
            % (skipped_scaled, skipped_empty, skipped_large)
        )

    if not placements:
        return None

    placements.sort(
        key=lambda placement: (
            0 if placement["object"] == active_root else 1,
            placement["object"].name.lower(),
            get_object_identity(placement["object"]),
        )
    )
    return placements, list(models_by_signature.values())


def get_linked_model_digest(model):
    signature_text = repr(model["signature"])
    hierarchy_bits = []

    for obj in model["hierarchy"]:
        data = getattr(obj, "data", None)
        vertex_count = 0
        polygon_count = 0
        try:
            vertex_count = len(data.vertices)
            polygon_count = len(data.polygons)
        except Exception:
            pass

        bounds = []
        try:
            for corner in obj.bound_box:
                bounds.extend(round(float(value), 5) for value in corner)
        except Exception:
            pass

        hierarchy_bits.append((
            str(getattr(obj, "name", "")),
            str(getattr(data, "name", "")),
            vertex_count,
            polygon_count,
            tuple(bounds),
        ))

    digest = hashlib.blake2s(
        (signature_text + repr(hierarchy_bits)).encode(
            "utf-8",
            errors="surrogatepass",
        ),
        digest_size=6,
    ).hexdigest()
    return digest


def linked_model_data_is_dirty(model):
    for obj in model["hierarchy"]:
        data = getattr(obj, "data", None)
        try:
            if bool(getattr(data, "is_updated_data", False)):
                return True
        except Exception:
            pass

        try:
            material_slots = obj.material_slots
        except Exception:
            material_slots = ()

        for material_slot in material_slots:
            material = material_slot.material
            if material is None:
                continue
            node_tree = getattr(material, "node_tree", None)
            if node_tree is None:
                continue
            for node in node_tree.nodes:
                image = getattr(node, "image", None)
                if image is not None and bool(getattr(image, "is_dirty", False)):
                    return True
    return False


def export_linked_instance_models(context, server_root, placements, models):
    global LAST_TEST_EXPORT_MODE
    global LAST_TEST_PLACEMENT_COUNT
    global LAST_TEST_SOURCE_MODEL_COUNT

    live_anchor = placements[0]["object"]
    set_test_transform_from_object(live_anchor)

    models_directory = server_root / "models"
    models_directory.mkdir(parents=True, exist_ok=True)
    keep_names = set()
    model_definitions = []
    model_id_by_signature = {}

    linked_model_records = {
        model["signature"]: {
            "object": model["root"],
            "txd_path": None,
        }
        for model in models
    }
    material_txd_names, material_keep_names, fallback_model_keys = (
        export_material_txd_packs(linked_model_records, models_directory)
    )
    keep_names.update(material_keep_names)

    for model_index, model in enumerate(models):
        custom_model_id = TEST_CUSTOM_MODEL_ID + model_index
        model_digest = get_linked_model_digest(model)
        dff_name = f"g{model_digest}.dff"
        txd_name = material_txd_names.get(model["signature"])
        export_individual_txd = txd_name is None
        if export_individual_txd:
            txd_name = f"x{model_digest}.txd"
        dff_path = models_directory / dff_name
        txd_path = models_directory / txd_name
        keep_names.add(dff_name)
        keep_names.add(txd_name)

        hierarchy = model["hierarchy"]
        export_objects = [
            obj for obj in hierarchy
            if not is_test_collision_object(obj)
        ]
        collision_objects = [
            obj for obj in hierarchy
            if is_test_collision_object(obj)
        ]

        dirty = linked_model_data_is_dirty(model)
        needs_dff_export = (
            dirty
            or not dff_path.is_file()
            or dff_path.stat().st_size == 0
            or not dff_has_embedded_collision(dff_path)
        )
        needs_txd_export = (
            export_individual_txd
            and (
                dirty
                or not txd_path.is_file()
                or txd_path.stat().st_size == 0
            )
        )

        temporary_collision_collection = None
        temporary_collision_objects = []
        temporary_collision_meshes = []
        if needs_dff_export and not collision_objects:
            (
                temporary_collision_collection,
                temporary_collision_objects,
                temporary_collision_meshes,
            ) = create_temporary_box_collision(
                context,
                export_objects,
                model["root"],
            )
            collision_objects = temporary_collision_objects

        export_options = {
            "file_name": str(dff_path),
            "directory": str(models_directory),
            "selected": True,
            "mass_export": False,
            "preserve_positions": False,
            "force_collision_to_dff_transform": True,
            "version": 0x36003,
            "export_coll": True,
            "preserve_collision_positions": False,
            "coll_ext_type": 39056127,
            "export_frame_names": True,
            "export_tristrips": False,
            "objects": export_objects,
            "collision_objects": collision_objects,
            "export_origin_matrix_world": model["root"].matrix_world.copy(),
            "truncate_frame_names": False,
        }

        try:
            if needs_dff_export:
                test_progress(
                    "Linked-instance export: writing model %d/%d (%s)"
                    % (model_index + 1, len(models), model["root"].name)
                )
                try:
                    if dff_path.exists():
                        dff_path.unlink()
                except OSError as error:
                    raise RuntimeError(
                        f"Could not replace {dff_path}: {error}"
                    ) from error

                dff_samp_exporter.export_dff(export_options)
                if not dff_path.is_file() or dff_path.stat().st_size == 0:
                    raise RuntimeError(
                        "DemonFF did not write a valid DFF for linked selected model %s."
                        % model["root"].name
                    )
                if not dff_has_embedded_collision(dff_path):
                    raise RuntimeError(
                        "DemonFF could not embed collision for linked selected model %s."
                        % model["root"].name
                    )
            else:
                test_progress(
                    "Linked-instance export: reused cached model %d/%d (%s)"
                    % (model_index + 1, len(models), model["root"].name)
                )

            if needs_txd_export:
                try:
                    if txd_path.exists():
                        txd_path.unlink()
                except OSError as error:
                    raise RuntimeError(
                        f"Could not replace {txd_path}: {error}"
                    ) from error

                txd_exporter.txd_exporter.version = 0x36003
                txd_exporter.txd_exporter.export_textures(
                    export_objects,
                    str(txd_path),
                )
                if not txd_path.is_file() or txd_path.stat().st_size == 0:
                    raise RuntimeError(
                        "DemonFF did not write a valid TXD for linked selected model %s."
                        % model["root"].name
                    )
        finally:
            remove_temporary_test_collision(
                temporary_collision_collection,
                temporary_collision_objects,
                temporary_collision_meshes,
            )

        model_id_by_signature[model["signature"]] = custom_model_id
        model_definitions.append({
            "custom_model_id": custom_model_id,
            "base_model_id": model["base_model_id"],
            "dff_name": dff_name,
            "txd_name": txd_name,
        })

    remove_generated_fast_model_files(models_directory, keep_names)
    for packed_name in (
        f"{TEST_MODEL_NAME}.dff",
        f"{TEST_MODEL_NAME}.txd",
    ):
        packed_path = models_directory / packed_name
        try:
            if packed_path.exists():
                packed_path.unlink()
        except OSError:
            pass

    global LAST_TEST_SUPPORTS_LIVE_TRANSFORM

    attached_mode = len(placements) == 1
    LAST_TEST_SUPPORTS_LIVE_TRANSFORM = attached_mode
    anchor_inverse = live_anchor.matrix_world.inverted_safe() if attached_mode else None
    runtime_placements = []
    placement_total = len(placements)
    for placement_index, placement in enumerate(placements, 1):
        if attached_mode:
            placement_matrix = anchor_inverse @ placement["object"].matrix_world
        else:
            placement_matrix = placement["object"].matrix_world

        location, rotation, scale = placement_matrix.decompose()
        if not all(abs(abs(float(component)) - 1.0) <= 1.0e-4 for component in scale):
            raise RuntimeError(
                "Fast selected-model testing cannot preserve scaled object instances."
            )
        runtime_placements.append({
            "attached": attached_mode,
            "custom_model_id": model_id_by_signature[placement["model"]["signature"]],
            "position": (float(location.x), float(location.y), float(location.z)),
            "rotation": quaternion_to_gta_euler_degrees(rotation),
        })

        if progress_checkpoint(placement_index, placement_total, maximum_messages=40):
            test_progress(
                "Linked placement transform conversion",
                placement_index,
                placement_total,
            )

    write_test_runtime_data(server_root, model_definitions, runtime_placements)

    LAST_TEST_EXPORT_MODE = "LINKED_INSTANCES" if attached_mode else "LINKED_STATIC_MAP"
    LAST_TEST_PLACEMENT_COUNT = len(runtime_placements)
    LAST_TEST_SOURCE_MODEL_COUNT = len(model_definitions)
    print(
        "DemonFF model test: exported %d unique linked model(s) once and reused them for %d selected placements."
        % (len(model_definitions), len(runtime_placements))
    )
    return None, None, live_anchor


def get_normalized_path_key(path_value):
    return os.path.normcase(os.path.normpath(str(path_value)))


def get_material_image_identity(image):
    try:
        pointer = int(image.as_pointer())
    except Exception:
        pointer = id(image)

    try:
        filepath = bpy.path.abspath(image.filepath_raw or image.filepath or "")
    except Exception:
        filepath = str(getattr(image, "filepath", "") or "")

    filepath_key = get_normalized_path_key(filepath) if filepath else ""
    try:
        width, height = int(image.size[0]), int(image.size[1])
    except Exception:
        width, height = 0, 0

    return (
        pointer,
        str(getattr(image, "name_full", image.name)),
        filepath_key,
        width,
        height,
    )


def get_material_image_signature(image):
    identity = get_material_image_identity(image)
    filepath_key = identity[2]
    file_size = 0
    modified_time = 0
    if filepath_key:
        try:
            image_path = Path(filepath_key)
            stat_result = image_path.stat()
            file_size = int(stat_result.st_size)
            modified_time = int(stat_result.st_mtime_ns)
        except OSError:
            pass

    packed_size = 0
    try:
        packed_file = image.packed_file
        if packed_file is not None:
            packed_size = len(packed_file.data)
    except Exception:
        pass

    return identity[1:] + (
        str(getattr(image, "source", "")),
        file_size,
        modified_time,
        packed_size,
    )


def collect_model_material_textures(model_root):
    hierarchy = collect_object_subtree(
        model_root,
        maximum_count=MAX_ACTIVE_MODEL_OBJECTS,
    )
    textures = {}
    identities = {}
    invalid_names = []
    conflicting_names = []
    seen_materials = set()
    image_node_count = 0

    for obj in hierarchy:
        try:
            material_slots = obj.material_slots
        except Exception:
            continue

        for material_slot in material_slots:
            material = material_slot.material
            if material is None:
                continue

            material_key = get_object_pointer(material)
            if material_key in seen_materials:
                continue
            seen_materials.add(material_key)

            node_tree = getattr(material, "node_tree", None)
            if node_tree is None:
                continue

            for node in node_tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None:
                    continue

                image_node_count += 1
                image = node.image
                texture_name = txd_exporter.clear_extension(
                    node.label or image.name
                )
                texture_name = txd_exporter.txd_exporter.normalize_texture_name(
                    texture_name
                )
                name_key = texture_name.lower()

                try:
                    width, height = int(image.size[0]), int(image.size[1])
                    has_data = bool(getattr(image, "has_data", True))
                except Exception:
                    width, height, has_data = 0, 0, False

                if width <= 0 or height <= 0 or not has_data:
                    invalid_names.append(texture_name)
                    continue

                identity = get_material_image_identity(image)
                existing_identity = identities.get(name_key)
                if existing_identity is not None and existing_identity != identity:
                    conflicting_names.append(texture_name)
                    continue

                identities[name_key] = identity
                textures[name_key] = (texture_name, image)

    return {
        "textures": textures,
        "identities": identities,
        "invalid_names": sorted(set(invalid_names), key=str.lower),
        "conflicting_names": sorted(set(conflicting_names), key=str.lower),
        "image_node_count": image_node_count,
    }


def pack_model_material_textures(model_texture_records):
    packs = []
    assignment = {}

    ordered_records = sorted(
        model_texture_records,
        key=lambda record: (
            -len(record["textures"]),
            repr(record["model_key"]),
        ),
    )

    for record in ordered_records:
        model_key = record["model_key"]
        textures = record["textures"]
        identities = record["identities"]

        best_pack_index = None
        best_score = None
        for pack_index, pack in enumerate(packs):
            conflict = False
            for name_key, identity in identities.items():
                existing_identity = pack["identities"].get(name_key)
                if existing_identity is not None and existing_identity != identity:
                    conflict = True
                    break
            if conflict:
                continue

            added_count = sum(
                1 for name_key in textures
                if name_key not in pack["textures"]
            )
            resulting_count = len(pack["textures"]) + added_count
            if resulting_count > MAX_TEXTURES_PER_TEST_TXD:
                continue

            score = (
                added_count,
                MAX_TEXTURES_PER_TEST_TXD - resulting_count,
                pack_index,
            )
            if best_score is None or score < best_score:
                best_score = score
                best_pack_index = pack_index

        if best_pack_index is None:
            best_pack_index = len(packs)
            packs.append({
                "textures": {},
                "identities": {},
                "model_keys": [],
            })

        pack = packs[best_pack_index]
        pack["textures"].update(textures)
        pack["identities"].update(identities)
        pack["model_keys"].append(model_key)
        assignment[model_key] = best_pack_index

    return packs, assignment


def get_material_txd_pack_name(pack):
    signature_lines = []
    for name_key in sorted(pack["textures"]):
        texture_name, image = pack["textures"][name_key]
        signature_lines.append(
            repr((texture_name.lower(), get_material_image_signature(image)))
        )

    digest = hashlib.blake2s(
        "\n".join(signature_lines).encode("utf-8", errors="surrogatepass"),
        digest_size=6,
    ).hexdigest()
    return f"{MATERIAL_TEST_TXD_PREFIX}{digest}.txd"


def export_material_txd_packs(unique_models, models_directory):
    global LAST_TEST_MATERIAL_TXD_COUNT
    global LAST_TEST_MATERIAL_TEXTURE_COUNT

    LAST_TEST_MATERIAL_TXD_COUNT = 0
    LAST_TEST_MATERIAL_TEXTURE_COUNT = 0

    model_texture_records = []
    source_txd_model_keys = set()
    model_items = sorted(unique_models.items(), key=lambda item: repr(item[0]))
    total_models = len(model_items)

    test_progress(
        "Material TXDs: scanning one Blender hierarchy for each unique source model"
    )

    for index, (model_key, placement) in enumerate(model_items, 1):
        material_data = collect_model_material_textures(placement["object"])
        texture_count = len(material_data["textures"])

        fallback_reason = ""
        if material_data["image_node_count"] == 0:
            fallback_reason = "no Blender image textures"
        elif material_data["invalid_names"]:
            fallback_reason = "%d unloaded image(s)" % len(
                material_data["invalid_names"]
            )
        elif material_data["conflicting_names"]:
            fallback_reason = "%d conflicting texture name(s)" % len(
                material_data["conflicting_names"]
            )
        elif texture_count > MAX_TEXTURES_PER_TEST_TXD:
            fallback_reason = (
                "%d textures in one DFF; one model can reference only one TXD"
                % texture_count
            )
        elif texture_count == 0:
            fallback_reason = "no exportable Blender image textures"

        if fallback_reason:
            source_txd_model_keys.add(model_key)
            if material_data["image_node_count"] > 0:
                test_progress(
                    "Material TXDs: %s uses its source TXD (%s)"
                    % (placement["object"].name, fallback_reason)
                )
        else:
            model_texture_records.append({
                "model_key": model_key,
                "textures": material_data["textures"],
                "identities": material_data["identities"],
            })

        if progress_checkpoint(index, total_models, maximum_messages=30):
            test_progress(
                "Material hierarchy scan: %d model(s) can use Blender materials"
                % len(model_texture_records),
                index,
                total_models,
            )

    if not model_texture_records:
        test_progress(
            "Material TXDs: no complete Blender material sets were found; source TXDs will be reused"
        )
        return {}, set(), source_txd_model_keys

    packs, pack_assignment = pack_model_material_textures(model_texture_records)
    test_progress(
        "Material TXDs: variably split %d model material set(s) into %d TXD pack(s), maximum %d textures each"
        % (
            len(model_texture_records),
            len(packs),
            MAX_TEXTURES_PER_TEST_TXD,
        )
    )

    model_txd_names = {}
    keep_names = set()
    total_unique_textures = 0

    for pack_index, pack in enumerate(packs, 1):
        texture_count = len(pack["textures"])
        if texture_count > MAX_TEXTURES_PER_TEST_TXD:
            raise RuntimeError(
                "Internal material pack exceeded %d textures."
                % MAX_TEXTURES_PER_TEST_TXD
            )

        txd_name = get_material_txd_pack_name(pack)
        txd_path = models_directory / txd_name
        keep_names.add(txd_name)
        total_unique_textures += texture_count

        dirty = any(
            bool(getattr(image, "is_dirty", False))
            for _texture_name, image in pack["textures"].values()
        )
        needs_export = dirty or not txd_path.is_file() or txd_path.stat().st_size == 0

        if needs_export:
            test_progress(
                "Material TXD %d/%d: writing %d texture(s) for %d source model(s)"
                % (
                    pack_index,
                    len(packs),
                    texture_count,
                    len(pack["model_keys"]),
                )
            )

            def report_texture_progress(current, total, texture_name):
                if progress_checkpoint(current, total, maximum_messages=12):
                    test_progress(
                        "Material TXD %d/%d: encoding %s"
                        % (pack_index, len(packs), texture_name),
                        current,
                        total,
                    )

            exported_count = txd_exporter.txd_exporter.export_texture_items(
                [pack["textures"][name_key] for name_key in sorted(pack["textures"])],
                str(txd_path),
                version=0x36003,
                progress_callback=report_texture_progress,
            )
            if exported_count != texture_count:
                raise RuntimeError(
                    "Material TXD %s wrote %d of %d expected textures."
                    % (txd_name, exported_count, texture_count)
                )
        else:
            test_progress(
                "Material TXD %d/%d: reused cached %s with %d texture(s)"
                % (pack_index, len(packs), txd_name, texture_count)
            )

        for model_key in pack["model_keys"]:
            model_txd_names[model_key] = txd_name

    LAST_TEST_MATERIAL_TXD_COUNT = len(packs)
    LAST_TEST_MATERIAL_TEXTURE_COUNT = total_unique_textures
    return model_txd_names, keep_names, source_txd_model_keys

def ensure_empty_test_txd(models_directory):
    txd_path = models_directory / EMPTY_TEST_TXD_NAME
    if txd_path.is_file() and txd_path.stat().st_size > 0:
        return EMPTY_TEST_TXD_NAME

    test_progress("Material TXDs: writing one shared empty fallback TXD")
    txd_exporter.txd_exporter.export_texture_items(
        [],
        str(txd_path),
        version=0x36003,
    )
    if not txd_path.is_file() or txd_path.stat().st_size == 0:
        raise RuntimeError("DemonFF could not write the fallback test TXD.")
    return EMPTY_TEST_TXD_NAME


def write_test_runtime_data(server_root, model_definitions, placements):
    scriptfiles_directory = server_root / "scriptfiles"
    scriptfiles_directory.mkdir(parents=True, exist_ok=True)

    model_text = "".join(
        "%d %d %s %s\n" % (
            int(model["custom_model_id"]),
            int(model["base_model_id"]),
            model["dff_name"],
            model["txd_name"],
        )
        for model in model_definitions
    )

    placement_text = "".join(
        "%d %d %s %s %s %s %s %s\n" % (
            1 if placement.get("attached", True) else 0,
            int(placement["custom_model_id"]),
            pawn_float(placement["position"][0]),
            pawn_float(placement["position"][1]),
            pawn_float(placement["position"][2]),
            pawn_float(placement["rotation"][0]),
            pawn_float(placement["rotation"][1]),
            pawn_float(placement["rotation"][2]),
        )
        for placement in placements
    )

    write_text_if_changed(
        scriptfiles_directory / TEST_MODEL_DEFINITION_FILE_NAME,
        model_text,
    )
    write_text_if_changed(
        scriptfiles_directory / TEST_PLACEMENT_FILE_NAME,
        placement_text,
    )


def export_fast_selected_placements(context, server_root, placements):
    global LAST_TEST_EXPORT_MODE
    global LAST_TEST_PLACEMENT_COUNT
    global LAST_TEST_SOURCE_MODEL_COUNT

    test_progress(f"Fast export: preparing {len(placements)} placement(s)")
    live_anchor = placements[0]["object"]
    set_test_transform_from_object(live_anchor)

    models_directory = server_root / "models"
    models_directory.mkdir(parents=True, exist_ok=True)

    unique_models = {}
    for placement in placements:
        txd_key = ""
        if placement["txd_path"] is not None:
            txd_key = os.path.normcase(
                os.path.normpath(str(placement["txd_path"]))
            )
        model_key = (
            os.path.normcase(os.path.normpath(str(placement["dff_path"]))),
            txd_key,
            int(placement["base_model_id"]),
        )
        placement["model_key"] = model_key
        unique_models.setdefault(model_key, placement)

    if len(unique_models) > 29000:
        raise RuntimeError("The selection uses too many unique custom models for SA-MP 0.3.DL.")

    test_progress(
        f"Fast export: {len(unique_models)} unique model definition(s); duplicate geometry will not be rebuilt"
    )

    dff_names = {}
    txd_names = {}
    keep_names = set()
    install_counts = {"linked": 0, "symlinked": 0, "reused": 0, "copied": 0}

    unique_dff_paths = sorted(
        {Path(placement["dff_path"]) for placement in unique_models.values()},
        key=lambda path: os.path.normcase(os.path.normpath(str(path))),
    )
    for index, source_path in enumerate(unique_dff_paths):
        target_name = stable_test_asset_name(source_path, "dff")
        target_path = models_directory / target_name
        install_result = install_test_asset(source_path, target_path)
        install_counts[install_result] = install_counts.get(install_result, 0) + 1
        dff_names[os.path.normcase(os.path.normpath(str(source_path)))] = target_name
        keep_names.add(target_name)
        if progress_checkpoint(index + 1, len(unique_dff_paths)):
            test_progress(
                f"DFF assets: {install_counts['reused']} reused, {install_counts['linked']} hard-linked, {install_counts['symlinked']} symbolic-linked, {install_counts['copied']} copied",
                index + 1,
                len(unique_dff_paths),
            )

    material_txd_names, material_keep_names, source_txd_model_keys = (
        export_material_txd_packs(unique_models, models_directory)
    )
    keep_names.update(material_keep_names)

    unique_txd_paths = sorted(
        {
            Path(unique_models[model_key]["txd_path"])
            for model_key in source_txd_model_keys
            if unique_models[model_key]["txd_path"] is not None
        },
        key=lambda path: os.path.normcase(os.path.normpath(str(path))),
    )
    for index, source_path in enumerate(unique_txd_paths):
        target_name = stable_test_asset_name(source_path, "txd")
        target_path = models_directory / target_name
        install_result = install_test_asset(source_path, target_path)
        install_counts[install_result] = install_counts.get(install_result, 0) + 1
        txd_names[os.path.normcase(os.path.normpath(str(source_path)))] = target_name
        keep_names.add(target_name)
        if progress_checkpoint(index + 1, len(unique_txd_paths)):
            test_progress(
                f"TXD assets: {install_counts['reused']} total reused, {install_counts['linked']} total hard-linked, {install_counts['symlinked']} total symbolic-linked, {install_counts['copied']} total copied",
                index + 1,
                len(unique_txd_paths),
            )

    missing_source_txd_keys = {
        model_key
        for model_key in source_txd_model_keys
        if unique_models[model_key]["txd_path"] is None
    }
    if missing_source_txd_keys:
        keep_names.add(EMPTY_TEST_TXD_NAME)

    test_progress("Fast export: removing stale generated model links")
    remove_generated_fast_model_files(models_directory, keep_names)

    for packed_name in (
        f"{TEST_MODEL_NAME}.dff",
        f"{TEST_MODEL_NAME}.txd",
    ):
        packed_path = models_directory / packed_name
        try:
            if packed_path.exists():
                packed_path.unlink()
        except OSError:
            pass

    empty_txd_name = None
    if missing_source_txd_keys:
        empty_txd_name = ensure_empty_test_txd(models_directory)
        keep_names.add(empty_txd_name)

    model_id_by_key = {}
    model_definitions = []
    for index, model_key in enumerate(sorted(unique_models)):
        placement = unique_models[model_key]
        custom_model_id = TEST_CUSTOM_MODEL_ID + index
        model_id_by_key[model_key] = custom_model_id
        dff_source_key = os.path.normcase(os.path.normpath(str(placement["dff_path"])))
        txd_name = material_txd_names.get(model_key)
        if txd_name is None and placement["txd_path"] is not None:
            txd_source_key = os.path.normcase(
                os.path.normpath(str(placement["txd_path"]))
            )
            txd_name = txd_names[txd_source_key]
        if txd_name is None:
            txd_name = empty_txd_name or ensure_empty_test_txd(models_directory)
            keep_names.add(txd_name)
        model_definitions.append({
            "custom_model_id": custom_model_id,
            "base_model_id": placement["base_model_id"],
            "dff_name": dff_names[dff_source_key],
            "txd_name": txd_name,
        })

    global LAST_TEST_SUPPORTS_LIVE_TRANSFORM

    attached_mode = len(placements) == 1
    LAST_TEST_SUPPORTS_LIVE_TRANSFORM = attached_mode
    if attached_mode:
        test_progress(
            "Fast export: converting placements relative to the active live pivot"
        )
        anchor_inverse = live_anchor.matrix_world.inverted_safe()
    else:
        test_progress(
            "Fast export: using static world placements for the full map; no pivot attachments"
        )
        anchor_inverse = None

    runtime_placements = []
    placement_total = len(placements)
    for placement_index, placement in enumerate(placements, 1):
        if attached_mode:
            placement_matrix = anchor_inverse @ placement["object"].matrix_world
        else:
            placement_matrix = placement["object"].matrix_world

        location, rotation, scale = placement_matrix.decompose()
        if not all(abs(abs(float(component)) - 1.0) <= 1.0e-4 for component in scale):
            raise RuntimeError(
                "Fast selected-model testing cannot preserve scaled map placements. "
                "Apply the placement scale and run the test again."
            )

        runtime_placements.append({
            "attached": attached_mode,
            "custom_model_id": model_id_by_key[placement["model_key"]],
            "position": (float(location.x), float(location.y), float(location.z)),
            "rotation": quaternion_to_gta_euler_degrees(rotation),
        })

        if progress_checkpoint(placement_index, placement_total, maximum_messages=40):
            test_progress(
                "Placement transform conversion",
                placement_index,
                placement_total,
            )

    test_progress("Fast export: writing model and placement data")
    write_test_runtime_data(server_root, model_definitions, runtime_placements)

    LAST_TEST_EXPORT_MODE = "FAST_PLACEMENTS" if attached_mode else "FAST_STATIC_MAP"
    LAST_TEST_PLACEMENT_COUNT = len(runtime_placements)
    LAST_TEST_SOURCE_MODEL_COUNT = len(model_definitions)

    mode_text = "live-pivot placements" if attached_mode else "static streamed map placements"
    material_summary = ""
    if LAST_TEST_MATERIAL_TXD_COUNT:
        material_summary = ", %d Blender-material TXD pack(s) containing %d texture(s)" % (
            LAST_TEST_MATERIAL_TXD_COUNT,
            LAST_TEST_MATERIAL_TEXTURE_COUNT,
        )
    test_progress(
        "Fast export complete: %d placement(s), %d source model(s), %s%s"
        % (
            len(runtime_placements),
            len(model_definitions),
            mode_text,
            material_summary,
        )
    )
    return None, None, live_anchor


def try_export_fast_selected_models(context, server_root):
    test_progress("Export strategy: trying direct source-DFF/TXD placement reuse")
    placements = collect_fast_test_placements(context)
    if placements is not None:
        return export_fast_selected_placements(context, server_root, placements)

    rejection = FAST_TEST_LAST_REJECTION or "selection is not a Pawn/open.mp map placement set"
    test_progress(f"Direct placement reuse unavailable: {rejection}")

    linked_result = collect_linked_instance_test_placements(context)
    if linked_result is None:
        test_progress("Linked-instance reuse unavailable; a packed export is required")
        return None

    linked_placements, linked_models = linked_result
    return export_linked_instance_models(
        context,
        server_root,
        linked_placements,
        linked_models,
    )

def export_selected_model(context, server_root):
    global LAST_TEST_EXPORT_MODE
    global LAST_TEST_PLACEMENT_COUNT
    global LAST_TEST_SOURCE_MODEL_COUNT
    global LAST_TEST_SUPPORTS_LIVE_TRANSFORM

    fast_result = try_export_fast_selected_models(context, server_root)
    if fast_result is not None:
        return fast_result

    test_progress(
        "WARNING: entering the slow packed-export path. DemonFF must evaluate and rebuild "
        "the selected geometry because reusable source placement metadata was unavailable."
    )
    LAST_TEST_EXPORT_MODE = "PACKED"
    LAST_TEST_SUPPORTS_LIVE_TRANSFORM = True
    LAST_TEST_PLACEMENT_COUNT = 1
    LAST_TEST_SOURCE_MODEL_COUNT = 1

    test_progress("Packed export: resolving complete selected model hierarchies")
    selected_hierarchy = collect_selected_model_objects(context)
    if not selected_hierarchy:
        raise RuntimeError("Select one or more DFF model objects before starting the test.")

    export_objects = [
        obj for obj in selected_hierarchy
        if not is_test_collision_object(obj)
        and not is_live_player_export_excluded(obj)
    ]

    if not any(is_test_render_mesh_object(obj) for obj in export_objects):
        raise RuntimeError("The selected model does not contain a mesh object.")

    live_anchor = choose_live_test_anchor(context, export_objects)
    set_test_transform_from_object(live_anchor)

    collision_objects = collect_exact_test_collision_objects(
        context,
        selected_hierarchy,
        live_anchor,
    )

    temporary_collision_collection = None
    temporary_collision_objects = []
    temporary_collision_meshes = []
    generated_collision = False

    if not collision_objects:
        collision_mode = "FAST_BOX"
        (
            temporary_collision_collection,
            temporary_collision_objects,
            temporary_collision_meshes,
        ) = create_temporary_test_collision(
            context,
            export_objects,
            live_anchor,
            collision_mode,
        )
        collision_objects = temporary_collision_objects
        generated_collision = True

    models_directory = server_root / "models"
    models_directory.mkdir(parents=True, exist_ok=True)
    remove_generated_fast_model_files(models_directory)

    dff_path = models_directory / f"{TEST_MODEL_NAME}.dff"
    txd_path = models_directory / f"{TEST_MODEL_NAME}.txd"

    for output_path in (dff_path, txd_path):
        if output_path.exists():
            output_path.unlink()

    export_options = {
        "file_name": str(dff_path),
        "directory": str(models_directory),
        "selected": True,
        "mass_export": False,
        "preserve_positions": False,
        "force_collision_to_dff_transform": True,
        "version": 0x36003,
        "export_coll": True,
        "preserve_collision_positions": False,
        "coll_ext_type": 39056127,
        "export_frame_names": True,
        "export_tristrips": False,
        "objects": export_objects,
        "collision_objects": collision_objects,
        "export_origin_matrix_world": live_anchor.matrix_world.copy(),
        "truncate_frame_names": False,
    }

    try:
        if generated_collision:
            print(
                "DemonFF model test: embedding a fast bounding-box collision."
            )
        else:
            print(
                "DemonFF model test: embedding %d attached collision object(s)."
                % len(collision_objects)
            )

        test_progress(f"Packed export: writing DFF from {len(export_objects)} Blender object(s)")
        dff_samp_exporter.export_dff(export_options)

        if not dff_path.is_file() or dff_path.stat().st_size == 0:
            raise RuntimeError("DemonFF did not write a valid SA-MP DFF for the selected model.")

        if not dff_has_embedded_collision(dff_path):
            try:
                dff_path.unlink()
            except OSError:
                pass
            raise RuntimeError(
                "DemonFF could not embed collision in the test DFF. "
                "Reduce the collision mesh and test the model again."
            )

        test_progress("Packed export: collecting and writing TXD textures")
        txd_exporter.txd_exporter.version = 0x36003
        txd_exporter.txd_exporter.export_textures(export_objects, str(txd_path))

        if not txd_path.is_file() or txd_path.stat().st_size == 0:
            raise RuntimeError("DemonFF did not write a valid TXD for the selected model.")

        write_test_runtime_data(
            server_root,
            [{
                "custom_model_id": TEST_CUSTOM_MODEL_ID,
                "base_model_id": TEST_BASE_MODEL_ID,
                "dff_name": dff_path.name,
                "txd_name": txd_path.name,
            }],
            [{
                "custom_model_id": TEST_CUSTOM_MODEL_ID,
                "position": (0.0, 0.0, 0.0),
                "rotation": (0.0, 0.0, 0.0),
                "attached": True,
            }],
        )

        print(
            "DemonFF model test: wrote %d selected hierarchy object(s) as one temporary DFF with embedded collision to %s"
            % (len(export_objects), dff_path)
        )
    finally:
        remove_temporary_test_collision(
            temporary_collision_collection,
            temporary_collision_objects,
            temporary_collision_meshes,
        )

    return dff_path, txd_path, live_anchor

def configure_test_server(server_root, server_executable):
    for directory_name in (
        "models",
        "gamemodes",
        "filterscripts",
        "plugins",
        "scriptfiles",
    ):
        (server_root / directory_name).mkdir(parents=True, exist_ok=True)

    configure_server_file(server_root, server_executable)


def start_server(server_executable, server_root, initial_transform=None):
    global SERVER_PROCESS
    global SERVER_LOG_HANDLE
    global SERVER_ROOT

    test_progress(f"Server: stopping any previous local test server and checking UDP port {LOCAL_PORT}")
    stop_server_process()

    if not udp_port_is_available():
        release_local_test_port()

    if not udp_port_is_available():
        raise RuntimeError(
            f"Local test port {LOCAL_PORT} is already in use and could not be released."
        )

    scriptfiles_directory = server_root / "scriptfiles"
    scriptfiles_directory.mkdir(parents=True, exist_ok=True)

    for file_name in (LIVE_TRANSFORM_FILE_NAME, PLAYER_STATE_FILE_NAME):
        state_path = scriptfiles_directory / file_name
        try:
            state_path.unlink()
        except FileNotFoundError:
            pass

    if initial_transform is not None:
        write_live_transform_file_for_root(server_root, initial_transform)

    log_path = server_root / "demonff_server_console.log"
    SERVER_LOG_HANDLE = open(log_path, "w", encoding="utf-8", errors="replace")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    test_progress(f"Server: starting {server_executable.name}")
    try:
        SERVER_PROCESS = subprocess.Popen(
            [str(server_executable)],
            cwd=str(server_root),
            stdin=subprocess.DEVNULL,
            stdout=SERVER_LOG_HANDLE,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
    except OSError as error:
        stop_server_process()
        raise RuntimeError(
            f"Could not start {server_executable.name}: {error}"
        ) from error

    SERVER_ROOT = server_root
    deadline = time.time() + 8.0

    while time.time() < deadline:
        if SERVER_LOG_HANDLE is not None:
            SERVER_LOG_HANDLE.flush()

        failure_detail = server_log_failure_detail(log_path)
        if failure_detail:
            stop_server_process()
            raise RuntimeError(f"Test server failed to start: {failure_detail}")

        if SERVER_PROCESS.poll() is not None:
            detail = read_server_log_tail(log_path, maximum_lines=1)
            if not detail:
                detail = "The server exited immediately."
            stop_server_process()
            raise RuntimeError(f"Test server failed to start: {detail}")

        if not udp_port_is_available():
            test_progress(f"Server: listening on {LOCAL_HOST}:{LOCAL_PORT}")
            return SERVER_PROCESS

        time.sleep(0.25)

    detail = server_log_failure_detail(log_path)
    if not detail:
        detail = f"{server_executable.name} did not bind to {LOCAL_HOST}:{LOCAL_PORT}."
    stop_server_process()
    raise RuntimeError(f"Test server failed to start: {detail}")


def stop_process_by_name(process_name):
    if os.name != "nt":
        return

    subprocess.run(
        ["taskkill", "/F", "/IM", process_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def stop_running_gta():
    for process_name in (
        "gta_sa.exe",
        "samp.exe",
        "omp-launcher.exe",
        "open.mp launcher.exe",
        "openmp-launcher.exe",
    ):
        stop_process_by_name(process_name)


def process_is_running(process_name):
    if os.name != "nt":
        return False

    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        return False

    target = process_name.lower()
    for line in result.stdout.splitlines():
        first_column = line.strip().lstrip('"').split('",', 1)[0].lower()
        if first_column == target:
            return True
    return False


def wait_for_game_process(timeout=25.0):
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        if process_is_running("gta_sa.exe"):
            return True
        time.sleep(0.25)
    return False


def build_openmp_deeplink():
    return f"omp://{LOCAL_HOST}:{LOCAL_PORT}"


def build_client_command(client_executable, gtasa_root):
    client_kind = executable_kind(client_executable, OMP_CLIENT_EXECUTABLE_NAMES)

    if client_kind == "open.mp":
        return [
            str(client_executable),
            "-h",
            LOCAL_HOST,
            "-p",
            str(LOCAL_PORT),
            "-n",
            LOCAL_PLAYER_NAME,
            "-g",
            str(gtasa_root),
        ]

    return [
        str(client_executable),
        f"{LOCAL_HOST}:{LOCAL_PORT}",
        "-n",
        LOCAL_PLAYER_NAME,
        "-c",
    ]

def get_client_launch_log_path():
    return get_test_server_root(get_local_test_root(create=True)) / "demonff_client_launch.log"


def append_client_launch_log(lines):
    log_path = get_client_launch_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as output:
            for line in lines:
                output.write(str(line).rstrip("\r\n") + "\n")
    except OSError:
        pass


def get_client_working_directory(client_executable, gtasa_root):
    if path_is_within(client_executable, gtasa_root):
        return gtasa_root
    return client_executable.parent


def write_client_command_log(client_executable, gtasa_root, command, launch_mode):
    log_path = get_client_launch_log_path()
    working_directory = get_client_working_directory(client_executable, gtasa_root)

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "Executable: " + str(client_executable) + "\n"
            "Game Root: " + str(gtasa_root) + "\n"
            "Working Directory: " + str(working_directory) + "\n"
            "Launch Mode: " + str(launch_mode) + "\n"
            "Command: " + subprocess.list2cmdline(command) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def start_client_process(client_executable, gtasa_root):
    command = build_client_command(client_executable, gtasa_root)
    client_working_directory = get_client_working_directory(
        client_executable,
        gtasa_root,
    )
    client_kind = executable_kind(client_executable, OMP_CLIENT_EXECUTABLE_NAMES)
    launch_mode = "direct open.mp CLI" if client_kind == "open.mp" else "direct SA-MP CLI"

    write_client_command_log(
        client_executable,
        gtasa_root,
        command,
        launch_mode,
    )

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        return subprocess.Popen(
            command,
            cwd=str(client_working_directory),
            creationflags=creation_flags,
        )
    except OSError as error:
        raise RuntimeError(
            f"Could not start {client_executable.name}: {error}"
        ) from error


def start_elevated_openmp_client(client_executable, gtasa_root):
    if os.name != "nt":
        raise RuntimeError(
            "The open.mp launcher needs administrator permission to access gta_sa.exe."
        )

    import ctypes

    command = build_client_command(client_executable, gtasa_root)
    parameters = subprocess.list2cmdline(command[1:])
    working_directory = get_client_working_directory(
        client_executable,
        gtasa_root,
    )

    append_client_launch_log((
        "Retry Mode: elevated open.mp CLI",
        "Elevated Executable: " + str(client_executable),
        "Elevated Parameters: " + parameters,
        "Elevated Working Directory: " + str(working_directory),
    ))

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(client_executable),
        parameters,
        str(working_directory),
        1,
    )

    if int(result) <= 32:
        raise RuntimeError(
            "Windows did not allow open.mp to run with the permission required "
            f"to access gta_sa.exe. ShellExecute error: {int(result)}"
        )

    return None

def stop_client_process(client_process, client_executable):
    if client_process is not None and client_process.poll() is None:
        try:
            client_process.terminate()
            client_process.wait(timeout=2.0)
        except Exception:
            try:
                client_process.kill()
            except Exception:
                pass

    stop_process_by_name(client_executable.name)


def get_client_log_paths(client_executable, gtasa_root):
    return unique_path_candidates(
        (
            client_executable.parent / "omp-launcher.log",
            gtasa_root / "omp-launcher.log",
            client_executable.parent / "samp_debug.log",
        )
    )


def clear_client_logs(client_executable, gtasa_root):
    for log_path in get_client_log_paths(client_executable, gtasa_root):
        if not log_path.is_file():
            continue
        try:
            log_path.unlink()
        except OSError:
            pass


def read_client_failure_detail(client_executable, gtasa_root):
    for log_path in get_client_log_paths(client_executable, gtasa_root):
        if not log_path.is_file():
            continue
        try:
            lines = [
                line.strip()
                for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            ]
        except OSError:
            continue
        if lines:
            return lines[-1]
    return ""


def wait_for_game_or_client_exit(client_process, timeout=25.0):
    deadline = time.time() + float(timeout)
    process_exit_time = None

    while time.time() < deadline:
        if process_is_running("gta_sa.exe"):
            return True

        if client_process is not None and client_process.poll() is not None:
            if process_exit_time is None:
                process_exit_time = time.time()

            if time.time() - process_exit_time >= 8.0:
                return False

        time.sleep(0.25)

    return process_is_running("gta_sa.exe")


def local_test_client_connected():
    if SERVER_ROOT is None:
        return False

    log_paths = (
        Path(SERVER_ROOT) / "demonff_server_console.log",
        Path(SERVER_ROOT) / "demonff_openmp_server.log",
        Path(SERVER_ROOT) / "log.txt",
        Path(SERVER_ROOT) / "server_log.txt",
    )
    connection_phrases = (
        "incoming connection",
        "has joined the server",
        "player connected",
        LOCAL_PLAYER_NAME.lower(),
    )

    for log_path in log_paths:
        if not log_path.is_file():
            continue
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if any(phrase in log_text for phrase in connection_phrases):
            return True

    return False


def wait_for_local_test_connection(timeout=20.0):
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        if local_test_client_connected():
            return True
        time.sleep(0.25)
    return local_test_client_connected()


def launcher_needs_elevation(detail_text):
    lowered = str(detail_text or "").lower()
    return (
        "access is denied" in lowered
        or "access denied" in lowered
        or "administrator privileges required" in lowered
        or "unable to open game process" in lowered
    )


def register_client_watch(client_executable, gtasa_root, client_process):
    global CLIENT_WATCH_TIMER

    cancel_client_watch()

    state = {
        "started_at": time.time(),
        "elevation_attempted": False,
        "client_process": client_process,
    }

    def watch_client_startup():
        global CLIENT_WATCH_TIMER

        if CLIENT_WATCH_TIMER is not watch_client_startup:
            return None

        if local_test_client_connected():
            append_client_launch_log((
                "Result: connected to the DemonFF local server",
            ))
            CLIENT_WATCH_TIMER = None
            return None

        client_detail = read_client_failure_detail(
            client_executable,
            gtasa_root,
        )

        if (
            not state["elevation_attempted"]
            and launcher_needs_elevation(client_detail)
        ):
            state["elevation_attempted"] = True
            append_client_launch_log((
                "The open.mp launcher could not access gta_sa.exe.",
                "Stopping the failed client and retrying once with administrator permission.",
                "Launcher Message: " + client_detail,
            ))

            stop_client_process(
                state["client_process"],
                client_executable,
            )
            stop_process_by_name("gta_sa.exe")
            clear_client_logs(client_executable, gtasa_root)

            try:
                start_elevated_openmp_client(
                    client_executable,
                    gtasa_root,
                )
            except Exception as error:
                append_client_launch_log((
                    "Result: elevated retry failed",
                    "Error: " + str(error),
                ))
                CLIENT_WATCH_TIMER = None
                return None

            state["started_at"] = time.time()
            state["client_process"] = None
            return 0.5

        elapsed = time.time() - state["started_at"]
        timeout = 50.0 if state["elevation_attempted"] else 35.0

        if elapsed >= timeout:
            final_detail = read_client_failure_detail(
                client_executable,
                gtasa_root,
            )
            append_client_launch_log((
                "Result: client did not connect before timeout",
                "Last Launcher Message: " + (final_detail or "none"),
            ))
            CLIENT_WATCH_TIMER = None
            return None

        return 0.5

    CLIENT_WATCH_TIMER = watch_client_startup
    bpy.app.timers.register(
        watch_client_startup,
        first_interval=0.5,
    )


def launch_client(client_executable, gtasa_root, fallback_client_executable=None):
    valid_root, detail = validate_gtasa_game_root(gtasa_root)
    if not valid_root:
        raise RuntimeError(detail)

    stop_running_gta()
    time.sleep(0.5)

    clear_client_logs(client_executable, gtasa_root)
    client_process = start_client_process(client_executable, gtasa_root)

    if executable_kind(client_executable, OMP_CLIENT_EXECUTABLE_NAMES) == "open.mp":
        register_client_watch(
            client_executable,
            gtasa_root,
            client_process,
        )

    return client_executable

