# 04 – SCons, `.gdextension`, ignore rules, editor config

Completes gate G3 with `03`. Prerequisite: G2 outputs exist.

## WP8: `build/SConstruct`, `demo/rive.gdextension`, `.gitignore`, VS Code

### Goal and prerequisite state

`scons -C build platform=<linux|macos> target=<template_debug|template_release> arch=<x86_64|arm64> rive_out=<dir> skia_out=<dir> [use_llvm=yes]` compiles `src/**/*.cpp` and links one shared library into `demo/bin/`, and Godot finds it on both platforms.

### Repository evidence

- `build/SConstruct` (verified): `SConscript("SConscript.common")`, `env = SConscript("../godot-cpp/SConstruct")`, `env.RequireFile(...)` guards, `env.Prepend(LIBS=…, LIBPATH=…, CPPPATH=…)`, `GlobRecursive("../src", "*.cpp")`, macOS output `../demo/bin/librive.{platform}.{target}.framework/librive.{platform}.{target}`, other platforms `../demo/bin/librive{suffix}{SHLIBSUFFIX}`.
- `godot-cpp/SConstruct:302-311`: `suffix = ".{platform}.{target}" [+ ".dev"] [+ ".double"] + ".{arch}"`. So Linux debug output is `librive.linux.template_debug.x86_64.so`.
- `godot-cpp/tools/linux.py`: `use_llvm` option; `-fPIC`; `-Wl,-R,'$$ORIGIN'`.
- `godot-cpp/tools/macos.py:49-54`: `arch=universal` adds both `-arch` flags; `arm64` adds only `-arch arm64`.
- `build/SConscript.common` (verified): `GlobRecursive`, `RequireFile`, `FailBuild` helpers. Reused unchanged.
- `demo/rive.gdextension` (verified): `entry_symbol = "rive_library_init"`, `compatibility_minimum = 4.1`, `[libraries] macos.debug / macos.release`, `[icons]`.
- `.gitignore` (verified): `.godot/`, `.DS_Store`, `*.os`, `*.o`, `.sconsign.dblite`.
- Upstream `tests/rive_tools_project.lua` uses `linkgroups("On")` on Linux with the comment "Solves link order issue on linux".
- Upstream root `premake5_v2.lua` project `rive` sets `defines({'YOGA_EXPORT=', '_RIVE_INTERNAL_'})`; `_RIVE_INTERNAL_` appears in one public header (`include/rive/internal/assert_internal_only.hpp`) whose purpose is to reject inclusion from outside the library. Do **not** define `_RIVE_INTERNAL_` in the extension.

### Change surface: `build/SConstruct`

Add two `ARGUMENTS`:

| Variable | Meaning | Default |
| --- | --- | --- |
| `rive_out` | directory under `build/rive/` holding the six rive archives | `out/debug` |
| `skia_out` | directory under `build/deps/skia/` holding `libskia.a` | `out/debug` |

Include paths (`CPPPATH`), all repository-relative from `build/`:

```
../src
../thirdparty/rive-cpp                     (for <skia/renderer/include/...>)
../thirdparty/rive-cpp/include
../thirdparty/rive-cpp/skia/renderer/include
../build/deps/skia                         (for <include/core/Sk*.h>)
```

The transitive include closure of every upstream header `src/` includes (computed over `origin/main:include/` without preprocessing, so it is a superset) reaches none of `yoga/*.h`, `miniaudio.h`, or `hb.h`: `include/rive/artboard.hpp:19` includes `audio_engine.hpp`, which only forward-declares `ma_*`. So the yoga and miniaudio clone directories are **not** on `CPPPATH`. If a later `src/` change includes a header that needs them, the directory names `dependency.lua` derives are `build/deps/rive-app_yoga_rive_changes_v2_0_1_3_grid` and `build/deps/rive-app_miniaudio_rive_changes_5` (`<owner>_<repo>_<tag>` with `/` replaced by `_`).

No forced includes. Upstream compiles project `rive` with `forceincludes({'rive_yoga_renames.h'})` and, under `with_rive_text`, `forceincludes({'rive_harfbuzz_renames.h'})` (`premake5_v2.lua:186-202`), but the extension's include closure never reaches a yoga or harfbuzz declaration, and `build/SConstruct` mutates the environment that `godot-cpp/SConstruct` also uses to compile its own generated sources (`godot-cpp/SConstruct:318` builds the static library from the returned `env`, and SCons expands `CCFLAGS` at build time), so a force-include would inject ~1,400 short macros (`OT`, `CFF`, `AAT`, …) into godot-cpp's translation units. The `nm` check below proves the renames are not needed; if a future `src/` change includes `rive/layout/*.hpp` or `rive/text/font_hb.hpp`, add the force-includes and `../thirdparty/rive-cpp/dependencies` (the rename headers' directory) to an `env.Clone()` used only for `src/**/*.cpp`.

Defines (`CPPDEFINES`): `WITH_RIVE_TEXT`, `WITH_RIVE_LAYOUT`, `WITH_RIVE_AUDIO`, `MA_NO_RESOURCE_MANAGER`, `YOGA_EXPORT=`. These mirror the workspace-scope defines that `RIVE_PREMAKE_ARGS` in `02` WP4 produces (`premake5_v2.lua`: `with_rive_text` -> `WITH_RIVE_TEXT`; `with_rive_layout` -> `WITH_RIVE_LAYOUT`; `with_rive_audio=system` -> `WITH_RIVE_AUDIO`, `MA_NO_RESOURCE_MANAGER`). Keep the two lists adjacent in `build.py` and `SConstruct` with a comment cross-referencing each other.

`DEBUG`/`NDEBUG` need no extra handling: `rive_build_config.lua` defines `DEBUG` for `config=debug`; godot-cpp defines `NDEBUG` only for `template_release` (`godot-cpp/tools/targets.py:98`); and `include/rive/rive_types.hpp:19-36` defines `DEBUG` whenever `NDEBUG` is absent. So `template_debug` matches the debug archives and `template_release` matches the release archives as long as `build.py` never pairs a debug `rive_out` with a release scons target (WP6 derives both from one `--target`).

Libraries (`LIBS`, order matters for static archives; Linux wraps them in a group):

```
rive_skia_renderer  rive  skia  rive_harfbuzz  rive_sheenbidi  rive_yoga  miniaudio
```

`LIBPATH`: `../build/rive/<rive_out>` and `../build/deps/skia/<skia_out>`. `RequireFile` each of the seven archives.

Platform-specific link flags:

| Platform | Additions |
| --- | --- |
| linux | `env["_LIBFLAGS"] = "-Wl,--start-group " + env["_LIBFLAGS"] + " -Wl,--end-group"` (SCons expands `$_LIBFLAGS` after `$SOURCES` in `$LINKCOM`, so markers in `LINKFLAGS` would precede every object and library and fail with "--end-group without --start-group"); the listed order has no back-references, so the group is belt-and-braces; system libs `pthread`, `dl`, `m` |
| macos | frameworks `CoreText`, `CoreGraphics`, `CoreFoundation` (always: upstream compiles `hb-coretext*.cc` with `HAVE_CORETEXT` on macOS, `dependencies/premake5_harfbuzz_v2.lua:327-333`, and `src/text/font_hb_apple.mm` into `librive.a`), `CoreAudio`, `AudioToolbox` (miniaudio system backend); `Cocoa` only if the G1 fallback re-enabled Skia GPU. Pass `macos_deployment_target=11.0` to scons to match rive's `-mmacosx-version-min=11.0` (`rive_build_config.lua:787,797`) and the Skia build in `02`. godot-cpp appends `-Wl,-undefined,dynamic_lookup` (`godot-cpp/tools/macos.py:64-70`), so a missing framework is invisible at link time; G5 in `05` therefore runs a `dlopen` probe and a demangled `nm -u` check |

Output names (unchanged scheme):

- linux: `../demo/bin/librive.linux.template_{debug,release}.x86_64.so`
- macos: `../demo/bin/librive.macos.template_{debug,release}.framework/librive.macos.template_{debug,release}` (arm64-only Mach-O now, not universal)

Remove the `GetRiveBin` helper and its `platform_map`/`target_map` (upstream layout no longer encodes platform/target in paths). Keep `env["STATIC_AND_SHARED_OBJECTS_ARE_THE_SAME"] = True`.

### Change surface: `demo/rive.gdextension`

```ini
[libraries]
macos.debug = "bin/librive.macos.template_debug.framework"
macos.release = "bin/librive.macos.template_release.framework"
linux.debug.x86_64 = "bin/librive.linux.template_debug.x86_64.so"
linux.release.x86_64 = "bin/librive.linux.template_release.x86_64.so"
```

`compatibility_minimum` stays `4.1` (godot-cpp pin is 4.1.1; assumption A2 in `00` is verified by the smoke test on Godot 4.6.3).

### Change surface: `.gitignore`

Append:

```
# Dependency build outputs (see build/build.py)
build/deps/
build/rive/out/
demo/bin/*.so
```

(`build/rive/out/` also holds the generated makefiles because `rive_build_config.lua` sets `location` to the out directory.)

Do **not** ignore `demo/bin/*.framework` (the macOS binaries stay committed per non-blocking decision N1 in `00`).

### Change surface: `.vscode/c_cpp_properties.json`

Add a `Linux` configuration (`compilerPath` `/usr/bin/clang`, `intelliSenseMode` `linux-clang-x64`) and update both configurations' `includePath`:

- replace `${workspaceFolder}/thirdparty/rive-cpp/skia/dependencies/skia` with `${workspaceFolder}/build/deps/skia`
- add `${workspaceFolder}/thirdparty/rive-cpp/skia/renderer/include`
- add `"defines": ["WITH_RIVE_TEXT", "WITH_RIVE_LAYOUT", "WITH_RIVE_AUDIO", "MA_NO_RESOURCE_MANAGER", "YOGA_EXPORT="]`

### Intended behavior and invariants

- A missing archive fails at configure time with the existing `RequireFile` message rather than at link time.
- `use_llvm=yes` is passed by `build.py` on Linux so the extension objects and the clang-built archives share a compiler family. It is not strictly required (no LTO, C++ ABI is libstdc++ either way), but it removes a variable when debugging link errors.
- Godot loads the Linux `.so` with `RTLD_NOW` semantics, so every referenced symbol must resolve at load. The `ldd -r` gate in `05` proves this before opening the editor.

### Acceptance criteria (gate G3 with `03`)

```bash
scons -C build platform=linux target=template_debug arch=x86_64 use_llvm=yes rive_out=out/debug skia_out=out/debug
scons -C build platform=linux target=template_release arch=x86_64 use_llvm=yes rive_out=out/release skia_out=out/release
ls demo/bin/librive.linux.template_debug.x86_64.so demo/bin/librive.linux.template_release.x86_64.so
ldd -r demo/bin/librive.linux.template_release.x86_64.so | grep -c "undefined symbol"   # 0
nm -D demo/bin/librive.linux.template_release.x86_64.so | grep -c " T rive_library_init"   # 1
! nm -D demo/bin/librive.linux.template_release.x86_64.so | c++filt | grep -qE ' U (YG|hb_|ma_|rive::|Sk[A-Z])'   # no unresolved rive/Skia/yoga/harfbuzz/miniaudio symbols
python3 -c "import ctypes,sys; ctypes.CDLL(sys.argv[1], ctypes.RTLD_NOW)" demo/bin/librive.linux.template_release.x86_64.so   # dlopen probe exits 0
git status --porcelain | grep -v '^??' | grep -c 'build/rive/out\|build/deps'   # 0 (all ignored)
```

### Risks, edge cases, exclusions

- **R3 check:** `nm build/rive/out/release/librive_harfbuzz.a | grep " T hb_" | head` must show renamed symbols (upstream force-includes `rive_harfbuzz_renames.h`), and `nm build/deps/skia/out/release/libskia.a | grep -c " T hb_"` must be `0` (Skia built with `skia_use_harfbuzz=false`). If either fails, stop and report; do not work around with `--allow-multiple-definition`.
- `png_`/`z_` symbols exist only inside `libskia.a` (rive is not linked with libpng/zlib in this workspace). If a duplicate appears, the cause is an unexpected extra archive, not a config to paper over.
- Windows/Android/iOS entries are intentionally absent from `rive.gdextension`.
