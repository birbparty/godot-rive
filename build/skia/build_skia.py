#!/usr/bin/env python3
"""Fetch and build the pinned CPU-only Skia used by the Rive renderer."""

from __future__ import annotations

import argparse
import platform as host_platform
import shutil
import subprocess
import sys
from pathlib import Path


SKIA_REPO = "https://github.com/rive-app/skia.git"
SKIA_COMMIT = "bae2881014cb5c3216184cbb0b639045b8804931"
REPO_ROOT = Path(__file__).resolve().parents[2]
SKIA_DIR = REPO_ROOT / "build" / "deps" / "skia"


def run(args: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def detect_platform() -> str:
    value = sys.platform
    if value.startswith("linux"):
        return "linux"
    if value == "darwin":
        return "macos"
    raise SystemExit(f"unsupported host platform: {value}")


def detect_arch() -> str:
    value = host_platform.machine().lower()
    if value in ("x86_64", "amd64"):
        return "x86_64"
    if value in ("arm64", "aarch64"):
        return "arm64"
    raise SystemExit(f"unsupported host architecture: {value}")


def require_tools() -> None:
    missing = [tool for tool in ("clang", "clang++", "git", "ninja", "python3") if not shutil.which(tool)]
    if missing:
        raise SystemExit("missing required tool(s): " + ", ".join(missing))


def prepare_checkout() -> None:
    SKIA_DIR.parent.mkdir(parents=True, exist_ok=True)
    if not (SKIA_DIR / ".git").is_dir():
        print("Cloning Skia and its dependencies; the first run is network-heavy.", flush=True)
        run(["git", "clone", SKIA_REPO, str(SKIA_DIR)])
    else:
        run(["git", "fetch", "origin", SKIA_COMMIT], cwd=SKIA_DIR)
    run(["git", "checkout", "--detach", SKIA_COMMIT], cwd=SKIA_DIR)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SKIA_DIR, text=True).strip()
    if head != SKIA_COMMIT:
        raise SystemExit(f"Skia checkout mismatch: expected {SKIA_COMMIT}, got {head}")

    deps_file = SKIA_DIR / "DEPS"
    deps = deps_file.read_text()
    filtered = "".join(line for line in deps.splitlines(keepends=True) if "piet" not in line)
    if filtered != deps:
        deps_file.write_text(filtered)
    run([sys.executable, "tools/git-sync-deps"], cwd=SKIA_DIR)
    if not (SKIA_DIR / "bin" / "gn").exists():
        run([sys.executable, "bin/fetch-gn"], cwd=SKIA_DIR)


def gn_args(target: str, platform: str, arch: str) -> list[str]:
    target_os = "mac" if platform == "macos" else "linux"
    target_cpu = "arm64" if arch == "arm64" else "x64"
    cflags = [
        "-fno-rtti", "-fPIC", "-DSK_DISABLE_SKPICTURE", "-DSK_DISABLE_TEXT",
        "-DRIVE_OPTIMIZED", "-DSK_DISABLE_LEGACY_SHADERCONTEXT",
        "-DSK_DISABLE_LOWP_RASTER_PIPELINE", "-DSK_FORCE_RASTER_PIPELINE_BLITTER",
        "-DSK_DISABLE_AAA", "-DSK_DISABLE_EFFECT_DESERIALIZATION",
    ]
    if platform == "macos":
        cflags.append("-mmacosx-version-min=11.0")
    quoted_flags = ",".join(f'"{flag}"' for flag in cflags)
    return [
        f"is_official_build={'true' if target == 'release' else 'false'}",
        f"is_debug={'false' if target == 'release' else 'true'}",
        "is_trivial_abi=false",
        f'target_os="{target_os}"', f'target_cpu="{target_cpu}"',
        'cc="clang"', 'cxx="clang++"', f"extra_cflags=[{quoted_flags}]",
        "skia_enable_gpu=false", "skia_enable_ganesh=false", "skia_enable_graphite=false",
        "skia_use_gl=false", "skia_use_metal=false", "skia_use_vulkan=false",
        "skia_use_angle=false", "skia_use_egl=false", "skia_use_x11=false",
        "skia_use_perfetto=false", "skia_use_fonthost_mac=false",
        "skia_use_zlib=true", "skia_use_system_zlib=false",
        "skia_use_libpng_decode=true", "skia_use_libpng_encode=true", "skia_use_system_libpng=false",
        "skia_use_libjpeg_turbo_decode=true", "skia_use_libjpeg_turbo_encode=false",
        "skia_use_system_libjpeg_turbo=false", "skia_use_libwebp_decode=true",
        "skia_use_libwebp_encode=false", "skia_use_system_libwebp=false",
        "skia_use_freetype=false", "skia_use_fontconfig=false", "skia_use_icu=false",
        "skia_use_harfbuzz=false", "skia_use_expat=false", "skia_use_dng_sdk=false",
        "skia_use_libheif=false", "skia_use_lua=false", "skia_use_piex=false",
        "skia_enable_fontmgr_empty=true", "skia_enable_pdf=false", "skia_enable_skottie=false",
        "skia_enable_svg=false", "skia_enable_tools=false", "skia_enable_spirv_validation=false",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("debug", "release"), default="debug")
    parser.add_argument("--platform", choices=("linux", "macos"), default=detect_platform())
    parser.add_argument("--arch", choices=("x86_64", "arm64"), default=detect_arch())
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    require_tools()
    prepare_checkout()
    output = SKIA_DIR / "out" / args.target
    if args.clean and output.exists():
        shutil.rmtree(output)
    arg_string = " ".join(gn_args(args.target, args.platform, args.arch))
    run([str(SKIA_DIR / "bin" / "gn"), "gen", str(output), f"--args={arg_string}"], cwd=SKIA_DIR)
    run(["ninja", "-C", str(output), "skia"], cwd=SKIA_DIR)
    archive = output / "libskia.a"
    if not archive.is_file() or archive.stat().st_size == 0:
        raise SystemExit(f"Skia build did not produce {archive}")
    print(f"Built {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
