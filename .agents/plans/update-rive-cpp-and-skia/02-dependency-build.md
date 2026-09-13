# 02 – Dependency build: Skia, rive runtime, Skia renderer, and `build.py`

Gates G1 and G2 live here. Prerequisite: G0 (`01`).

All paths are repository-relative. `<cfg>` is `debug` or `release`. `<platform>` is `linux` or `macos` (Godot naming).

## Target layout after this file's work

```
build/
├── build.py                 (rewritten)
├── SConstruct               (changed in 04)
├── SConscript.common        (unchanged)
├── rive/                    (new)
│   ├── premake5.lua         (new) composes upstream premake scripts
│   └── out/<cfg>/           (generated, git-ignored) librive.a librive_skia_renderer.a
│                            librive_harfbuzz.a librive_sheenbidi.a librive_yoga.a libminiaudio.a
├── skia/                    (new)
│   └── build_skia.py        (new) fetch + gn + ninja
└── deps/                    (generated, git-ignored; $DEPENDENCIES for premake)
    ├── skia/                rive-app/skia checkout (name fixed by skia/renderer/premake5_v2.lua)
    │   └── out/<cfg>/libskia.a
    └── rive-app_*_<tag>/    harfbuzz, sheenbidi, yoga, miniaudio clones made by build/dependency.lua
```

Skia lives under `build/deps/skia` because upstream `skia/renderer/premake5_v2.lua:3-12` resolves Skia as `$DEPENDENCIES/skia` when `SKIA_DIR` is unset, and treats `SKIA_DIR`, when set, as a directory *name* under `thirdparty/rive-cpp/skia/dependencies/` (it prepends `../dependencies/`). Never export `SKIA_DIR`.

## WP3: Skia fetch and build script

### Goal and prerequisite state

`python3 build/skia/build_skia.py --target=<cfg>` produces `build/deps/skia/out/<cfg>/libskia.a` from `rive-app/skia@bae2881014cb5c3216184cbb0b639045b8804931` on Linux (clang) and macOS (Xcode clang). Prerequisite: G0.

### Repository evidence

- Upstream `skia/dependencies/get_skia2.sh` clones `$SKIA_REPO` and checks out `$SKIA_BRANCH`, then strips `piet` lines from `DEPS` before `python3 tools/git-sync-deps` ("Remove piet-gpu from dependencies because repository does not exist anymore"). The same `sed` is required here.
- Upstream `skia/dependencies/make_skia_recorder.sh` and `dependencies/macosx/make_viewer_skia.sh` carry the `extra_cflags` set that the Rive Skia renderer expects: `-fno-rtti -DSK_DISABLE_SKPICTURE -DSK_DISABLE_TEXT -DRIVE_OPTIMIZED -DSK_DISABLE_LEGACY_SHADERCONTEXT -DSK_DISABLE_LOWP_RASTER_PIPELINE -DSK_FORCE_RASTER_PIPELINE_BLITTER -DSK_DISABLE_AAA -DSK_DISABLE_EFFECT_DESERIALIZATION`. Release adds `-flto=full` upstream; this plan omits it (constraint in `00`).
- `make_skia_recorder.sh` additionally patches libpng with `skia/pngprefix/pngprefix.h` to avoid clashing with a separately linked libpng. This repo does not link a second libpng, so the patch is not applied.
- The chosen commit ships `bin/fetch-gn` (HTTP 200) and `tools/git-sync-deps` (HTTP 200) but no `bin/gn` (HTTP 404). `fetch-gn` must run before `gn gen`.
- `gn/BUILDCONFIG.gn` at the chosen commit: line 44 `assert(!(is_debug && is_official_build))`, line 41 `is_trivial_abi = !is_official_build`, lines 191-192 add the `trivial_abi` config, and `gn/skia/BUILD.gn:694-698` defines `SK_TRIVIAL_ABI=[[clang::trivial_abi]]` for Skia's own objects only. `include/core/SkRefCnt.h:220` declares `class SK_TRIVIAL_ABI sk_sp`, and `include/private/base/SkAttributes.h:85-86` defines the macro empty for consumers. A debug Skia built with the default `is_trivial_abi=true` therefore returns `sk_sp<SkSurface>` from `SkSurface::MakeRaster` with a different calling convention than the extension expects.
- `gn/skia.gni` at the chosen commit declares `skia_enable_gpu`, `skia_enable_ganesh` (defaults to `skia_enable_gpu`), `skia_enable_graphite`, `skia_use_fonthost_mac = is_mac || is_ios`, `skia_use_perfetto = is_linux || is_mac || is_android`, `skia_use_x11 = is_linux`. It does **not** declare `skia_enable_skgpu_v1`, `skia_enable_skgpu_v2`, or `skia_skip_codesign` (those appear in upstream rive scripts written for older Skia).
- `src/skia_instance.hpp` uses only `SkSurface::MakeRaster`, `SkCanvas::clear`, `SkPixmap`, `SkImageInfo::Make(kRGBA_8888, kUnpremul)`. Upstream `skia/renderer/src/skia_factory.cpp` uses `SkImage::MakeFromEncoded`, `SkImage::MakeRasterCopy`, `SkGradientShader`, `SkImageFilters`, `SkColorFilter`, `SkVertices`, `SkPath::Make`. All exist at milestone 113 (verified `SkSurface.h:160-181`, `SkImage.h:216`).

### Change surface

`build/skia/build_skia.py` (new). Behavior:

1. Constants: `SKIA_REPO = "https://github.com/rive-app/skia.git"`, `SKIA_COMMIT = "bae2881014cb5c3216184cbb0b639045b8804931"`, `SKIA_DIR = build/deps/skia` (create `build/deps/` if absent).
2. Clone if `SKIA_DIR/.git` is absent; otherwise `git fetch`. Always `git checkout --detach <SKIA_COMMIT>`. Refuse to proceed if the checkout's HEAD differs from `SKIA_COMMIT`.
3. Apply the `DEPS` fix: remove every line containing `piet` (same as upstream `get_skia2.sh`), then run `python3 tools/git-sync-deps`.
4. Run `python3 bin/fetch-gn` if `bin/gn` is absent.
5. `bin/gn gen out/<cfg> --args="<args>"` then `ninja -C out/<cfg> skia` (the `skia` target only; do not build tools).
6. Print the path and size of `out/<cfg>/libskia.a`.
7. Flags: `--target=debug|release` (default `debug`), `--clean` (delete `out/<cfg>`), `--platform=linux|macos` (default: host), `--arch=arm64|x86_64` (default: host; used only to set `target_cpu`).

`gn` args (raster-only; record verbatim in the script). Per-config lines first, then the shared block:

```
# release:
is_official_build=true  is_debug=false  is_trivial_abi=false
# debug:
is_official_build=false is_debug=true   is_trivial_abi=false
# shared:
target_os="<linux|mac>"  target_cpu="<x64|arm64>"
cc="clang" cxx="clang++"
extra_cflags=["-fno-rtti","-fPIC","-DSK_DISABLE_SKPICTURE","-DSK_DISABLE_TEXT","-DRIVE_OPTIMIZED",
              "-DSK_DISABLE_LEGACY_SHADERCONTEXT","-DSK_DISABLE_LOWP_RASTER_PIPELINE",
              "-DSK_FORCE_RASTER_PIPELINE_BLITTER","-DSK_DISABLE_AAA","-DSK_DISABLE_EFFECT_DESERIALIZATION"]
skia_enable_gpu=false skia_enable_ganesh=false skia_enable_graphite=false
skia_use_gl=false skia_use_metal=false skia_use_vulkan=false skia_use_angle=false skia_use_egl=false
skia_use_x11=false skia_use_perfetto=false skia_use_fonthost_mac=false
skia_use_zlib=true skia_use_system_zlib=false
skia_use_libpng_decode=true skia_use_libpng_encode=true skia_use_system_libpng=false
skia_use_libjpeg_turbo_decode=true skia_use_libjpeg_turbo_encode=false skia_use_system_libjpeg_turbo=false
skia_use_libwebp_decode=true skia_use_libwebp_encode=false skia_use_system_libwebp=false
skia_use_freetype=false skia_use_fontconfig=false skia_use_icu=false skia_use_harfbuzz=false
skia_use_expat=false skia_use_dng_sdk=false skia_use_libheif=false skia_use_lua=false skia_use_piex=false
skia_enable_fontmgr_empty=true skia_enable_pdf=false skia_enable_skottie=false skia_enable_svg=false
skia_enable_tools=false skia_enable_spirv_validation=false
```

`is_trivial_abi=false` is mandatory in both configs (evidence above). `is_official_build=true` cannot be combined with `is_debug=true`, hence the split.

On macOS add `extra_cflags += ["-mmacosx-version-min=11.0"]` (matching `rive_build_config.lua:787,797`, which compiles rive with `-mmacosx-version-min=11.0`; 11.0 is also the arm64 floor) and `target_cpu="arm64"`. On Linux, `-fPIC` in `extra_cflags` is required because `libskia.a` is linked into a shared object. Resolve decision N2 (`00`) before running this step on macOS; a universal answer means two `gn` trees (`arm64`, `x64`) and a `lipo` step.

`.gitignore` additions are listed in `04` (WP8).

### Intended behavior, invariants, error paths

- Idempotent: a second run with the same `--target` reuses the checkout and `ninja` no-ops.
- Never contacts `cdn.rive.app` or S3.
- Fails fast with a clear message when `clang`, `ninja`, or `python3` is missing (check with `shutil.which`).
- Skia's `git-sync-deps` clones ~15 third-party repos; the script prints a one-line notice that this is network-heavy.

### Acceptance criteria (gate G1)

Convention for every acceptance block in this plan: a comment `# 0` after a `grep -c` means the printed count must be 0; because `grep -c` exits 1 when the count is 0, script such checks as `! grep -q …` rather than relying on the exit status.

```bash
python3 build/skia/build_skia.py --target=debug      # first line of output after gn: "gn gen" exit 0, no "Build argument has no effect" warning
python3 build/skia/build_skia.py --target=release
test -s build/deps/skia/out/debug/libskia.a && test -s build/deps/skia/out/release/libskia.a
git -C build/deps/skia rev-parse HEAD   # bae2881014cb5c3216184cbb0b639045b8804931
for c in debug release; do build/deps/skia/bin/gn args build/deps/skia/out/$c --list=is_trivial_abi --short; done   # both print is_trivial_abi = false
build/deps/skia/bin/gn args build/deps/skia/out/release --list --short > "$SCRATCH/skia-gn-args.txt"   # attach to the PR
nm -C build/deps/skia/out/release/libskia.a | grep -c "SkSurface::MakeRaster"   # > 0
nm build/deps/skia/out/release/libskia.a | grep -c " U gl[A-Z]"                 # 0 (no GL references)
```

### Risks, edge cases, exclusions

- If `skia_enable_gpu=false` breaks the `rive_skia_renderer` compile in WP5 (for example an unconditional `#include "include/gpu/..."`), flip `skia_enable_gpu=true skia_enable_ganesh=true skia_use_gl=true` here, add `GL` (Linux) / `Cocoa.framework` (macOS) to the link list in `04`, add `SK_GANESH` and `SK_GL` to the extension's `CPPDEFINES` and to the VS Code defines (Skia's `BUILD.gn` puts them in its public config, and `SkCanvas.h`/`SkSurface.h`/`SkImage.h` declarations change under them), and record the reason in the PR. This is the R1/decision-3 fallback in `00`.
- Do not use `git-sync-deps` output for anything except building `libskia.a`; the extension includes Skia headers from `build/deps/skia/include/...` only.

## WP4: premake wrapper for rive + Skia renderer

### Goal and prerequisite state

`build/rive/premake5.lua` (new) declares a workspace containing upstream's `rive`, `rive_harfbuzz`, `rive_sheenbidi`, `rive_yoga`, `miniaudio`, and `rive_skia_renderer` projects, with outputs in `build/rive/out/<cfg>/`. Prerequisite: WP2 (submodule moved), G0.

### Repository evidence

- Upstream `skia/thumbnail_generator/build/premake5.lua` (verified content) is the canonical composition:

  ```lua
  dofile('rive_build_config.lua')
  RIVE_RUNTIME_DIR = os.getenv('RIVE_RUNTIME_DIR') or '../../../'
  dofile(path.join(RIVE_RUNTIME_DIR, 'premake5_v2.lua'))
  BASE_DIR = path.getabsolute(RIVE_RUNTIME_DIR .. '/skia/renderer')
  dofile(path.join(BASE_DIR, 'premake5_v2.lua'))
  ```

- `rive_build_config.lua` is found through `PREMAKE_PATH`, which `build_rive.sh` sets to its own directory (`thirdparty/rive-cpp/build`). It sets `location`/`targetdir` to `RIVE_BUILD_OUT = _WORKING_DIR/out/<cfg>` unless `--out` is given.
- Upstream root `premake5_v2.lua` `dofile`s `dependencies/premake5_{harfbuzz,sheenbidi,miniaudio,yoga}_v2.lua`, each of which calls `dependency.github(...)`, cloning into `$DEPENDENCIES` (if set) or `<_WORKING_DIR>/dependencies`.
- Upstream `skia/renderer/premake5_v2.lua` resolves Skia as `os.getenv('SKIA_DIR')` when set, else `'../dependencies/' .. 'skia'` relative to `skia/renderer/`. It also **reassigns the global `dependencies`** from `os.getenv('DEPENDENCIES')`; the thumbnail generator tolerates this because root `premake5_v2.lua` has already consumed the variable. Keep the same `dofile` order.
- Upstream `premake5_v2.lua` for project `rive` uses `fatalwarnings({'All'})` unless `--for_unreal`; `skia/renderer/premake5_v2.lua` also uses `fatalwarnings`.

### Change surface

`build/rive/premake5.lua` (new):

```lua
dofile('rive_build_config.lua')                       -- resolved via PREMAKE_PATH
RIVE_RUNTIME_DIR = path.getabsolute('../../thirdparty/rive-cpp')
dofile(path.join(RIVE_RUNTIME_DIR, 'premake5_v2.lua'))
dofile(path.join(RIVE_RUNTIME_DIR, 'skia/renderer/premake5_v2.lua'))
```

Environment the caller (WP6 `build.py`) must export before invoking `build_rive.sh` from `build/rive/`:

| Variable | Value | Why |
| --- | --- | --- |
| `DEPENDENCIES` | absolute path of `build/deps` | `build/dependency.lua` clones harfbuzz/sheenbidi/yoga/miniaudio here (keeps them out of the submodule and `build/rive/`), and `skia/renderer/premake5_v2.lua` resolves Skia as `$DEPENDENCIES/skia` |
| `SKIA_DIR` | **must be unset** | if set, the renderer premake prepends `../dependencies/` and treats the value as a directory name under the submodule (`skia/renderer/premake5_v2.lua:3-12`) |
| `RIVE_PREMAKE_ARGS` | `--with_rive_text --with_rive_layout --with_rive_audio=system --with-pic --no-lto` | overrides upstream's default (`--with_rive_text --with_rive_layout --with_rive_canvas`); see decision 4 in `00`. `build_rive.sh` only applies its default when the variable is **unset**, so it must be exported. |
| `MACOS_SYSROOT` (macOS only) | `$(xcrun --sdk macosx --show-sdk-path)` | referenced by root `premake5_v2.lua` for `variant=runtime` builds; harmless when the variant is `system` |

First step (premake bootstrap and generation only, no compile). From `build/rive/` with the environment above exported. `build/dependency.lua` only creates the dependencies directory when `DEPENDENCIES` is unset; with it set, `git clone` fails if the directory does not exist, so create it first:

```bash
mkdir -p ../deps
../../thirdparty/rive-cpp/build/build_rive.sh nobuild <cfg>
ls ../../thirdparty/rive-cpp/build/dependencies/premake-core/bin/v5.0.0-beta7_release/premake5
ls out/<cfg>/Makefile ../deps/rive-app_yoga_rive_changes_v2_0_1_3_grid ../deps/rive-app_miniaudio_rive_changes_5
```

`build_rive.sh` runs premake before honouring `nobuild` (`build/build_rive.sh:386-391`), so this step also performs the dependency clones. It must be run from `build/rive/`, never from `thirdparty/rive-cpp/tests/`.

Full invocation (from `build/rive/`):

```bash
../../thirdparty/rive-cpp/build/build_rive.sh <cfg> -- rive rive_skia_renderer rive_harfbuzz rive_sheenbidi rive_yoga miniaudio
```

`<cfg>` is `debug` or `release`; on macOS append `arm64` before `--` (maps to `--arch=arm64`, output dir `out/arm64_<cfg>`). Note the output directory name difference: Linux host builds land in `out/<cfg>`, macOS arm64 builds in `out/arm64_<cfg>`. `build.py` and `SConstruct` must compute the same path (see WP6 and `04`).

### Intended behavior and invariants

- The premake workspace name is `rive` (set by `rive_build_config.lua`); the targets named after `--` are make targets, so the PLS renderer, decoders, tools, and tests are never built.
- `--with-pic` applies `-fPIC` to every project in the workspace, including `rive_skia_renderer`, because `rive_build_config.lua` sets it at workspace scope with a `filter({'options:with-pic'})`.
- `--no-lto` prevents `-flto` in release on every platform.
- `rtti('Off')` and `exceptionhandling('Off')` remain upstream defaults for these static libs. The extension compiles with RTTI and exceptions on. This is safe because the extension never `dynamic_cast`s or `typeid`s a rive/Skia type and never throws across a rive frame (verified: the only `dynamic_cast`s in `src/rive_viewer_base.cpp:36-50` are on godot-cpp types).

### Acceptance criteria (gate G2)

```bash
ls build/rive/out/debug/librive.a build/rive/out/debug/librive_skia_renderer.a \
   build/rive/out/debug/librive_harfbuzz.a build/rive/out/debug/librive_sheenbidi.a \
   build/rive/out/debug/librive_yoga.a build/rive/out/debug/libminiaudio.a
# same six files under out/release
cat build/rive/out/release/.rive_premake_args   # contains --with-pic --no-lto --with_rive_text --with_rive_layout --with_rive_audio=system, no --with_rive_canvas
# PIC and no bitcode:
readelf -h build/rive/out/release/librive.a >/dev/null 2>&1; \
  ar t build/rive/out/release/librive.a | head -1 | xargs -I{} sh -c 'ar p build/rive/out/release/librive.a {} | file -' | grep -q "ELF 64-bit LSB relocatable"   # not "LLVM IR bitcode"
```

### Risks, edge cases, exclusions

- **R1 concretely:** if `rive_skia_renderer` fails to compile because of a warning promoted by `fatalwarnings` or a Skia API mismatch, do **not** edit files inside `thirdparty/rive-cpp`. Instead add `build/patches/rive-cpp/<NN>-<slug>.patch` (new directory) and have `build.py` apply each patch with `git -C thirdparty/rive-cpp apply --check` then `apply` (idempotent: skip when `--check` fails **and** `apply --reverse --check` succeeds). Record every patch in the PR description. Prefer zero patches.
- `build_rive.sh` errors with "premake5 arguments for current build do not match previous arguments" if `RIVE_PREMAKE_ARGS` changes; `build.py --clean` must delete `build/rive/out/<cfg>` (R5).
- premake `v5.0.0-beta7` bootstrap writes into `thirdparty/rive-cpp/build/dependencies/`, which upstream does not ignore. Accept this untracked content in the submodule; never `git add` inside the submodule.

## WP5: (folded into WP4) Skia renderer static library

`rive_skia_renderer` is built by the same invocation as WP4. Its include roots are provided by upstream's `skia/renderer/premake5_v2.lua`: `include`, `../../cg_renderer/include`, `../../include`, and `$SKIA_DIR`. No separate work package. Gate G2 covers it.

## WP6: Rewrite `build/build.py`

### Goal and prerequisite state

`python build/build.py [--platform] [--arch] [--target] [--clean] [scons args...]` runs, in order: Skia (WP3), rive + renderer (WP4), then `scons` for the extension (`04`). Prerequisite: WP3 and WP4 designs; may be implemented together with them.

### Repository evidence

- Current `build/build.py` (verified) defines `PLATFORM_MAP`, `TARGET_MAP`, `ARCHITECTURES`, argparse flags `-p/--platform`, `-a/--arch`, `-c/--clean`, `-t/--target`, forwards unknown args to `scons`, and calls `build_rive()`, `build_skia()`, `build_extension()`. It `cwd="../"`-relative paths, so it must be run from `build/`. The README documents `cd build && python build.py`.
- `build_extension()` maps `ios_sim` specially; iOS is a non-goal, but keeping the argument surface costs nothing.

### Change surface

`build/build.py` (rewrite in place; keep the CLI flags and colour helpers):

1. Resolve `REPO_ROOT = Path(__file__).resolve().parent.parent`; stop depending on the current working directory. Update the README to allow running from anywhere (`python build/build.py …`).
2. `--platform` choices: `linux`, `macos` (Godot names; drop the `macosx`/`windows`/`ios`/`android` rive-name mapping). Default: host.
3. `--arch` choices: `x86_64`, `arm64`. Default: host (`platform.machine()` mapped `x86_64`->`x86_64`, `arm64`/`aarch64`->`arm64`). On macOS refuse `universal` with a message pointing to the deferred item.
4. `--target`: `debug`|`release` (default `debug`). Map to Godot `template_debug`/`template_release` for scons.
5. `--clean`: delete `build/deps/skia/out/<cfg>`, `build/rive/out/<rive_out>`, run `scons --clean` with the same platform/target/arch, and revert any applied submodule patches (`git -C thirdparty/rive-cpp checkout -- . && git -C thirdparty/rive-cpp clean -fd -e build/dependencies`). Do not delete the Skia checkout or the other `build/deps/*` clones.
6. `--skip-skia`, `--skip-rive` (new): skip steps whose outputs already exist; useful during the source port.
7. Steps:
   - `build_skia()` -> `python3 build/skia/build_skia.py --target=<cfg> --platform=<platform> --arch=<arch>`.
   - `build_rive()` -> `mkdir -p build/deps`; export `DEPENDENCIES` and `RIVE_PREMAKE_ARGS` (values in WP4), remove `SKIA_DIR` from the child environment, and on macOS export `MACOS_SYSROOT`; apply `build/patches/rive-cpp/*.patch` if any; run `build_rive.sh` from `build/rive/` with the six targets. `rive_out = "out/<cfg>"` on Linux, `"out/arm64_<cfg>"` on macOS arm64.
   - `build_extension()` -> `scons -C build platform=<platform> target=<godot_target> arch=<arch> rive_out=<rive_out> skia_out=<skia_out> use_llvm=yes(linux only) <forwarded args>`. The two new scons variables are defined in `04`.
8. Every subprocess uses `check=True`; on failure print the failing step and exit non-zero (the current script prints "Build successful!" even after a failed step because `handle_fail` does not exit; fix that).

### Acceptance criteria

```bash
python build/build.py --help                       # shows linux|macos, x86_64|arm64, --skip-skia, --skip-rive
python build/build.py --platform=linux --target=debug     # exits 0 after G3 (04) is met
python build/build.py --platform=linux --target=release   # exits 0
python build/build.py --clean --platform=linux --target=debug && test ! -d build/rive/out/debug
```

### Risks and exclusions

- `build.py` must not call `git submodule update` (the old script did); the pin is managed by `01`/WP2, and an implicit update could silently move it.
- Windows/iOS/Android branches are removed, not kept as dead code.
