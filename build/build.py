#!/usr/bin/env python3
"""Build Skia, the Rive runtime, and the Godot extension."""

from __future__ import annotations

import argparse
import os
import platform as host_platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build"
RIVE_DIR = BUILD_DIR / "rive"
RUNTIME_DIR = REPO_ROOT / "thirdparty" / "rive-cpp"
GODOT_CPP_DIR = REPO_ROOT / "godot-cpp"
DEPS_DIR = BUILD_DIR / "deps"
PREMAKE_ARGS = "--with_rive_text --with_rive_layout --with_rive_audio=system --with-pic --no-lto"
RIVE_TARGETS = ("rive", "rive_skia_renderer", "rive_harfbuzz", "rive_sheenbidi", "rive_yoga", "miniaudio")


def run(args: list[str], *, cwd: Path = REPO_ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def detect_platform() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    raise SystemExit(f"unsupported host platform: {sys.platform}")


def detect_arch() -> str:
    value = host_platform.machine().lower()
    if value in ("x86_64", "amd64"):
        return "x86_64"
    if value in ("arm64", "aarch64"):
        return "arm64"
    raise SystemExit(f"unsupported host architecture: {value}")


def apply_patches(checkout: Path, patch_dir: Path) -> None:
    for patch in sorted(patch_dir.glob("*.patch")) if patch_dir.exists() else ():
        check = subprocess.run(
            ["git", "apply", "--check", str(patch)], cwd=checkout, capture_output=True
        )
        if check.returncode == 0:
            run(["git", "apply", str(patch)], cwd=checkout)
            continue
        reverse = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch)], cwd=checkout, capture_output=True
        )
        if reverse.returncode != 0:
            raise SystemExit(f"patch cannot be applied cleanly to {checkout}: {patch}")


def build_skia(args: argparse.Namespace) -> None:
    run([sys.executable, str(BUILD_DIR / "skia" / "build_skia.py"),
         f"--platform={args.platform}", f"--arch={args.arch}", f"--target={args.target}"])


def build_rive(args: argparse.Namespace) -> str:
    DEPS_DIR.mkdir(parents=True, exist_ok=True)
    apply_patches(RUNTIME_DIR, BUILD_DIR / "patches" / "rive-cpp")
    env = os.environ.copy()
    env["DEPENDENCIES"] = str(DEPS_DIR)
    env["RIVE_PREMAKE_ARGS"] = PREMAKE_ARGS
    env.pop("SKIA_DIR", None)
    if args.platform == "macos":
        env["MACOS_SYSROOT"] = subprocess.check_output(
            ["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True
        ).strip()
    rive_output = f"out/{'arm64_' if args.platform == 'macos' else ''}{args.target}"
    command = [str(RUNTIME_DIR / "build" / "build_rive.sh"), args.target]
    if args.platform == "macos":
        command.append("arm64")
    command.extend(("--", *RIVE_TARGETS))
    run(command, cwd=RIVE_DIR, env=env)
    (RIVE_DIR / rive_output / ".rive_premake_args").write_text(PREMAKE_ARGS + "\n")
    return rive_output


def build_extension(args: argparse.Namespace, rive_output: str) -> None:
    apply_patches(GODOT_CPP_DIR, BUILD_DIR / "patches" / "godot-cpp")
    command = ["scons", "-C", str(BUILD_DIR), f"platform={args.platform}",
               f"target=template_{args.target}", f"arch={args.arch}",
               f"rive_out={rive_output}", f"skia_out=out/{args.target}"]
    command.append("use_llvm=yes" if args.platform == "linux" else "macos_deployment_target=11.0")
    command.extend(args.scons_args)
    run(command)


def clean(args: argparse.Namespace) -> None:
    outputs = [
        DEPS_DIR / "skia" / "out" / args.target,
        RIVE_DIR / "out" / (f"arm64_{args.target}" if args.platform == "macos" else args.target),
    ]
    for output in outputs:
        if output.exists():
            print(f"Removing {output}")
            shutil.rmtree(output)
    command = ["scons", "-C", str(BUILD_DIR), "--clean", f"platform={args.platform}",
               f"target=template_{args.target}", f"arch={args.arch}"]
    if args.platform == "linux":
        command.append("use_llvm=yes")
    command.extend(args.scons_args)
    run(command)
    run(["git", "checkout", "--", "."], cwd=RUNTIME_DIR)
    run(["git", "clean", "-fd", "-e", "build/dependencies"], cwd=RUNTIME_DIR)
    run(["git", "checkout", "--", "."], cwd=GODOT_CPP_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--platform", choices=("linux", "macos"), default=detect_platform())
    parser.add_argument("-a", "--arch", choices=("x86_64", "arm64"), default=detect_arch())
    parser.add_argument("-t", "--target", choices=("debug", "release"), default="debug")
    parser.add_argument("-c", "--clean", action="store_true")
    parser.add_argument("--skip-skia", action="store_true")
    parser.add_argument("--skip-rive", action="store_true")
    args, args.scons_args = parser.parse_known_args()
    if args.platform == "linux" and args.arch != detect_arch():
        parser.error("Linux cross-compilation is not supported; choose the host architecture")
    if args.platform == "macos" and args.arch != "arm64":
        parser.error("macOS builds are arm64-only; universal builds are deferred")
    if args.clean:
        clean(args)
        return
    if not args.skip_skia:
        build_skia(args)
    rive_output = f"out/{'arm64_' if args.platform == 'macos' else ''}{args.target}"
    if not args.skip_rive:
        rive_output = build_rive(args)
    build_extension(args, rive_output)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
