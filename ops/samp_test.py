# DemonFF - Blender scripts for working with Renderware & R*/SA-MP formats in Blender
# 2023 - 2026 spicybung

import json
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

from . import dff_samp_exporter, txd_exporter
from .map_transform import quaternion_to_gta_euler_degrees

SERVER_PROCESS = None
SERVER_LOG_HANDLE = None
SERVER_ROOT = None
CLIENT_WATCH_TIMER = None
LIVE_TEST_OBJECT = None
LIVE_TEST_LAST_TRANSFORM = None
LIVE_TEST_ACTIVE = False
LIVE_TEST_BASE_ROTATION = None
LIVE_TEST_REVISION = 0

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 7777
LOCAL_PLAYER_NAME = "DemonFF_Tester"
TEST_MODE_NAME = "demonff_blender_test"
TEST_MODEL_NAME = "demonff_test_model"
TEST_BASE_MODEL_ID = 18631
TEST_CUSTOM_MODEL_ID = -29999
TEST_DRAW_DISTANCE = 300.0
COLLISION_PLUGIN_ID = 0x0253F2FF


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
DOWNLOAD_USER_AGENT = "DemonFF/0.5.8 Blender SA-MP model tester"

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


def download_to_file(url, destination):
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



def ensure_local_runtime(
    package_root,
    source_game_root,
    configured_client_executable=None,
):
    package_root = create_local_test_scaffold(package_root)
    source_game_root = resolve_gtasa_game_root(source_game_root)

    server_executable, server_root = ensure_server_and_pawn_runtime(package_root)
    pawn_compiler, include_directory = find_pawn_compiler(server_root)
    ensure_streamer_runtime(package_root, server_root, include_directory)

    return validate_local_runtime(
        package_root,
        source_game_root,
        server_executable,
        configured_client_executable,
    )


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


def choose_live_test_anchor(context, export_objects):
    export_set = set(export_objects)
    active_object = context.view_layer.objects.active

    if active_object in export_set:
        return active_object

    selected = [obj for obj in context.selected_objects if obj in export_set]
    if selected:
        return selected[0]

    mesh_objects = [obj for obj in export_objects if obj.type == "MESH"]
    return mesh_objects[0] if mesh_objects else export_objects[0]


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


def write_live_transform_file(transform):
    global LIVE_TEST_REVISION

    if SERVER_ROOT is None:
        return False

    scriptfiles_directory = Path(SERVER_ROOT) / "scriptfiles"
    scriptfiles_directory.mkdir(parents=True, exist_ok=True)

    LIVE_TEST_REVISION += 1
    values = " ".join(pawn_float(value) for value in transform)
    contents = f"{LIVE_TEST_REVISION} {values}\n"

    destination = scriptfiles_directory / LIVE_TRANSFORM_FILE_NAME
    destination.write_text(contents, encoding="ascii", newline="\n")
    return True


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
    position = TEST_MODEL_POSITION
    rotation = TEST_MODEL_ROTATION
    spawn_position = (
        position[0],
        position[1] - 8.0,
        position[2] + 2.0,
    )

    return f"""#include <{pawn_include_name}>
#include <streamer>

#define DEMONFF_TEST_MODEL_ID ({TEST_CUSTOM_MODEL_ID})
#define DEMONFF_TEST_BASE_MODEL_ID ({TEST_BASE_MODEL_ID})
#define DEMONFF_TEST_DFF \"{TEST_MODEL_NAME}.dff\"
#define DEMONFF_TEST_TXD \"{TEST_MODEL_NAME}.txd\"

new g_DemonFFTestObject = INVALID_STREAMER_ID;
new g_DemonFFTransformRevision = -1;
new Float:g_DemonFFPosition[3] = {{
    {pawn_float(position[0])},
    {pawn_float(position[1])},
    {pawn_float(position[2])}
}};
new Float:g_DemonFFRotation[3] = {{
    {pawn_float(rotation[0])},
    {pawn_float(rotation[1])},
    {pawn_float(rotation[2])}
}};

forward DemonFFCreateTestObject();
forward DemonFFPollTransform();

main()
{{
}}

stock DemonFFReadToken(const source[], &index, output[], output_size)
{{
    while (source[index] == ' ')
    {{
        index++;
    }}

    new output_index = 0;
    while (
        source[index] != '\\0'
        && source[index] != ' '
        && output_index < output_size - 1
    )
    {{
        output[output_index++] = source[index++];
    }}
    output[output_index] = '\\0';
    return output_index;
}}

stock DemonFFRefreshPlayers()
{{
    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {{
        if (IsPlayerConnected(playerid))
        {{
            Streamer_Update(playerid);
        }}
    }}
    return 1;
}}

stock DemonFFApplyTransform()
{{
    if (IsValidDynamicObject(g_DemonFFTestObject))
    {{
        SetDynamicObjectPos(
            g_DemonFFTestObject,
            g_DemonFFPosition[0],
            g_DemonFFPosition[1],
            g_DemonFFPosition[2]
        );
        SetDynamicObjectRot(
            g_DemonFFTestObject,
            g_DemonFFRotation[0],
            g_DemonFFRotation[1],
            g_DemonFFRotation[2]
        );
        DemonFFRefreshPlayers();
    }}
    return 1;
}}

stock DemonFFReadLiveTransform()
{{
    new File:handle = fopen("demonff_live_transform.txt", io_read);
    if (!handle)
    {{
        return 0;
    }}

    new line[256];
    fread(handle, line);
    fclose(handle);

    new index = 0;
    new token[48];
    if (!DemonFFReadToken(line, index, token, sizeof token))
    {{
        return 0;
    }}

    new revision = strval(token);
    if (revision == g_DemonFFTransformRevision)
    {{
        return 0;
    }}

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
}}

public OnGameModeInit()
{{
    SetGameModeText(\"DemonFF Model Test\");
    ShowPlayerMarkers(PLAYER_MARKERS_MODE_OFF);
    ShowNameTags(false);
    UsePlayerPedAnims();
    SetWorldTime(12);
    SetWeather(0);

    AddPlayerClass(
        0,
        {pawn_float(spawn_position[0])},
        {pawn_float(spawn_position[1])},
        {pawn_float(spawn_position[2])},
        0.0,
        0,
        0,
        0,
        0,
        0,
        0
    );
    AddSimpleModel(
        -1,
        DEMONFF_TEST_BASE_MODEL_ID,
        DEMONFF_TEST_MODEL_ID,
        DEMONFF_TEST_DFF,
        DEMONFF_TEST_TXD
    );


    SetTimer(\"DemonFFCreateTestObject\", 1000, false);
    SetTimer(\"DemonFFPollTransform\", 100, true);
    return 1;
}}

public OnGameModeExit()
{{
    if (IsValidDynamicObject(g_DemonFFTestObject))
    {{
        DestroyDynamicObject(g_DemonFFTestObject);
    }}

    return 1;
}}

public OnPlayerRequestClass(playerid, classid)
{{
    SetSpawnInfo(
        playerid,
        0,
        0,
        {pawn_float(spawn_position[0])},
        {pawn_float(spawn_position[1])},
        {pawn_float(spawn_position[2])},
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
}}

public OnPlayerSpawn(playerid)
{{
    SetPlayerPos(
        playerid,
        {pawn_float(spawn_position[0])},
        {pawn_float(spawn_position[1])},
        {pawn_float(spawn_position[2])}
    );
    SetPlayerFacingAngle(playerid, 0.0);
    SetPlayerInterior(playerid, 0);
    SetPlayerVirtualWorld(playerid, 0);
    SetCameraBehindPlayer(playerid);
    Streamer_Update(playerid);
    SendClientMessage(
        playerid,
        0xFFFFFFFF,
        \"Model loaded. Live Updates are on.\"
    );
    return 1;
}}

public OnPlayerFinishedDownloading(playerid, virtualworld)
{{
    if (virtualworld == 0)
    {{
        SetTimer(\"DemonFFCreateTestObject\", 250, false);
        Streamer_Update(playerid);
    }}
    return 1;
}}

public DemonFFPollTransform()
{{
    DemonFFReadLiveTransform();
    return 1;
}}

stock DemonFFSetTimeForAllPlayers(hour)
{{
    SetWorldTime(hour);

    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {{
        if (IsPlayerConnected(playerid))
        {{
            SetPlayerTime(playerid, hour, 0);
        }}
    }}
    return 1;
}}

public OnPlayerCommandText(playerid, cmdtext[])
{{
    if (!strcmp(cmdtext, "/day", true))
    {{
        DemonFFSetTimeForAllPlayers(12);
        SendClientMessage(playerid, 0xFFFFFFFF, "Time set to day.");
        return 1;
    }}

    if (!strcmp(cmdtext, "/night", true))
    {{
        DemonFFSetTimeForAllPlayers(0);
        SendClientMessage(playerid, 0xFFFFFFFF, "Time set to night.");
        return 1;
    }}

    return 0;
}}

public OnRconCommand(cmd[])
{{
    if (strfind(cmd, \"demonff_transform \", true) != 0)
    {{
        return 0;
    }}

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
}}

public DemonFFCreateTestObject()
{{
    if (IsValidDynamicObject(g_DemonFFTestObject))
    {{
        DestroyDynamicObject(g_DemonFFTestObject);
    }}

    g_DemonFFTestObject = CreateDynamicObject(
        DEMONFF_TEST_MODEL_ID,
        g_DemonFFPosition[0],
        g_DemonFFPosition[1],
        g_DemonFFPosition[2],
        g_DemonFFRotation[0],
        g_DemonFFRotation[1],
        g_DemonFFRotation[2],
        0,
        0,
        -1,
        {pawn_float(TEST_DRAW_DISTANCE)},
        {pawn_float(TEST_DRAW_DISTANCE)}
    );

    DemonFFRefreshPlayers();
    return 1;
}}
"""

def write_and_compile_gamemode(server_root, compiler, include_directory, pawn_include_name):
    gamemodes_directory = server_root / "gamemodes"
    gamemodes_directory.mkdir(parents=True, exist_ok=True)

    source_path = gamemodes_directory / f"{TEST_MODE_NAME}.pwn"
    output_path = gamemodes_directory / f"{TEST_MODE_NAME}.amx"
    source_path.write_text(
        build_test_gamemode(pawn_include_name),
        encoding="utf-8",
        newline="\r\n",
    )

    if output_path.exists():
        output_path.unlink()

    command = [
        str(compiler),
        source_path.name,
        f"-i{include_directory}{os.sep}",
        f"-o{output_path.name}",
    ]

    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
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

    return source_path, output_path

def collect_selected_model_objects(context):
    selected_objects = list(context.selected_objects)
    if not selected_objects:
        return []

    roots = set()
    for selected_object in selected_objects:
        root = selected_object
        while root.parent is not None:
            root = root.parent
        roots.add(root)

    collected = set()
    pending = list(roots)
    while pending:
        obj = pending.pop()
        if obj in collected:
            continue
        collected.add(obj)
        pending.extend(list(obj.children))

    return list(collected)

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


def create_temporary_test_collision(context, export_objects):
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

def export_selected_model(context, server_root):
    selected_hierarchy = collect_selected_model_objects(context)
    if not selected_hierarchy:
        raise RuntimeError("Select the DFF model before pressing Test Selected Model.")

    export_objects = [
        obj for obj in selected_hierarchy
        if not is_test_collision_object(obj)
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
        (
            temporary_collision_collection,
            temporary_collision_objects,
            temporary_collision_meshes,
        ) = create_temporary_test_collision(context, export_objects)
        collision_objects = temporary_collision_objects
        generated_collision = True

    models_directory = server_root / "models"
    models_directory.mkdir(parents=True, exist_ok=True)

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
        "truncate_frame_names": False,
    }

    original_selected, original_active = set_export_selection(context, export_objects)
    try:
        if generated_collision:
            print(
                "DemonFF model test: embedding collision made from the selected model mesh."
            )
        else:
            print(
                "DemonFF model test: embedding %d attached collision object(s)."
                % len(collision_objects)
            )

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

        txd_exporter.txd_exporter.version = 0x36003
        txd_exporter.txd_exporter.export_textures(export_objects, str(txd_path))

        if not txd_path.is_file() or txd_path.stat().st_size == 0:
            raise RuntimeError("DemonFF did not write a valid TXD for the selected model.")

        print(
            "DemonFF model test: wrote the DFF with embedded collision to %s"
            % dff_path
        )
    finally:
        restore_selection(context, original_selected, original_active)
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


def start_server(server_executable, server_root):
    global SERVER_PROCESS
    global SERVER_LOG_HANDLE
    global SERVER_ROOT

    stop_server_process()

    if not udp_port_is_available():
        release_local_test_port()

    if not udp_port_is_available():
        raise RuntimeError(
            f"Local test port {LOCAL_PORT} is already in use and could not be released."
        )

    live_transform_path = server_root / "scriptfiles" / LIVE_TRANSFORM_FILE_NAME
    try:
        live_transform_path.unlink()
    except FileNotFoundError:
        pass

    log_path = server_root / "demonff_server_console.log"
    SERVER_LOG_HANDLE = open(log_path, "w", encoding="utf-8", errors="replace")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

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

