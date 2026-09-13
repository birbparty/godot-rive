# Update rive-cpp and Skia, then re-align the extension

**Status: Ready.** This is a plan only. No implementation work has occurred. No file outside `.agents/plans/update-rive-cpp-and-skia/` has been changed by planning.

## Application context

```json
{
  "application_context": {
    "has_active_users": false,
    "backward_compatibility_required": false,
    "feature_flags": "not-applicable",
    "confirmation_digest": "5fec620c2bbfca4ed1ad7cd6931965820faa9ced1f42f1b7c9079a0f2ede853c",
    "confirmed_at": "2026-09-10T19:22:04Z"
  }
}
```

The user answered "No" to active users and "No" to backward compatibility, so feature flags are recorded as `not-applicable` (the user selected "not appropriate", which the skill maps to `not-applicable` when both booleans are false). Consequences used throughout this plan:

- The GDScript-facing API (`RiveViewer`, `RiveViewer2D`, `RiveFile`, `RiveArtboard`, `RiveScene`, `RiveInput`, `RiveListener`, `RiveAnimation`) may change where the new runtime forces it. The plan still keeps names and signatures unchanged wherever the port does not require a change, because that is the cheapest path, not because compatibility is promised.
- The build workflow (`build/build.py`, `build/SConstruct`) may be replaced. No migration shim for the old flow is required.
- The committed macOS binaries under `demo/bin/` are treated as stale artifacts of the old pin. They are regenerated in the macOS work package, not preserved.
- No rollout, flag, or data-migration work exists. Rollback is `git revert <merge>` followed by `git submodule sync thirdparty/rive-cpp && git submodule update --init` (the revert restores `.gitmodules`, but the URL cached in `.git/config` only changes on `sync`). Generated trees (`build/deps/`, `build/rive/out/`, `thirdparty/rive-cpp/build/dependencies/`, `demo/.godot/`) are untracked and must be deleted by hand, and any working-tree patch applied to the submodule is undone with `git -C thirdparty/rive-cpp checkout -- . && git -C thirdparty/rive-cpp clean -fd`.

Additional user decisions recorded during planning (not part of the structured block):

| Decision | Answer |
| --- | --- |
| Platforms that must be verified | Linux (this machine, x86_64, Godot 4.6.3) **and** macOS (arm64) |
| Skia target | `rive-app/skia` at commit `bae2881014cb5c3216184cbb0b639045b8804931` (branch `recorder`, Skia milestone 113) |

## Change type and affected areas

Change type (inferred): **dependency upgrade with build-system replacement and source port**.

Affected areas (inferred from the repository):

| Area | Files |
| --- | --- |
| Submodule pins | `.gitmodules` (URL and `ignore = untracked`), `thirdparty/rive-cpp` (gitlink) |
| Dependency build | `build/build.py`, `build/SConstruct`, `build/SConscript.common`, new premake wrapper and Skia script under `build/` |
| Extension source | `src/skia_instance.hpp`, `src/utils/read_rive_file.hpp`, `src/api/rive_file.hpp`, `src/api/rive_artboard.hpp`, `src/api/rive_scene.hpp`, `src/api/rive_listener.hpp`, `src/rive_exceptions.hpp`, `src/rive_viewer_base.h` (Skia includes, new `get_image`), `src/rive_instance.hpp` (Skia includes) |
| Godot packaging | `demo/rive.gdextension`, `demo/bin/`, `.gitignore` |
| Docs and editor config | `README.md`, `.vscode/c_cpp_properties.json` |

## Requested outcome

The user's request, verbatim: "make a plan to update rive-cpp and skia in this repo and then update this repo to match."

Measurable success criteria:

1. `thirdparty/rive-cpp` points at upstream commit `45d4d01dfd1fe70d3f9e73764538c16f63a04d07` (tag `runtime-v0.1.384`, 2026-09-10) and `.gitmodules` points at `https://github.com/rive-app/rive-runtime.git`.
2. Skia is fetched from `https://github.com/rive-app/skia` at commit `bae2881014cb5c3216184cbb0b639045b8804931` into `build/deps/skia` by a script in this repository, with no dependence on Rive's CDN cache or on the stale upstream `skia/renderer/build.sh`.
3. `python build/build.py --platform=linux --target=debug` and `--target=release` produce `demo/bin/librive.linux.template_debug.x86_64.so` and `demo/bin/librive.linux.template_release.x86_64.so` on this machine.
4. `python build/build.py --platform=macos --arch=arm64 --target=debug` and `--target=release` produce the two `demo/bin/librive.macos.<target>.framework/` binaries on an Apple Silicon Mac (arm64-only per decision N2's default; universal if N2 resolves otherwise).
5. `godot --headless --path demo --import` followed by `godot --headless --fixed-fps 60 --path demo --script smoke_test.gd` (new script) exits 0 on Linux and macOS, proving: the extension loads, every `.riv` in `demo/examples/` imports, artboards and state machines enumerate, 60 frames advance elapsed time by 1.0 s, a scene input round-trips through `set_value`/`get_value`, and the rendered raster of a known file (read through the new `get_image()` accessor, not through `ImageTexture`, which the headless dummy renderer never updates) contains non-transparent pixels.
6. Opening `demo/main.tscn` and `demo/demo_2d.tscn` in the Godot editor shows the animations playing (manual visual gate on both platforms, part of G4 and G5, recorded in the PR with a screenshot).
7. `README.md` describes the new build steps and prerequisites accurately for Linux and macOS.

## Scope

In scope:

- Move the rive-cpp submodule to upstream `main` (`runtime-v0.1.384`) and fix the submodule URL.
- Replace the dependency build with a premake-based flow driven by upstream `build/build_rive.sh`, plus a repository-owned Skia fetch/build script.
- Port `src/` to the new runtime API.
- Add Linux as a first-class build and packaging target; keep macOS arm64.
- Update README, `.gitignore`, and VS Code include paths.
- Add a headless smoke test script in the demo project.

Non-goals (explicitly excluded):

- Migrating from the Skia renderer to the Rive Renderer (`rive_pls_renderer`). Skia stays the renderer.
- Updating the `godot-cpp` submodule (pinned at `c370f0f`, godot-4.1.1-stable+36). It compiles with C++17 and has no exception-disabling option, which the extension relies on.
- Windows, Android, iOS, or Web builds.
- macOS universal (x86_64 + arm64) binaries. arm64 only; universal is deferred.
- Adding new Rive features (data binding, view models, text runs, audio APIs, events) to the GDScript API.
- Fixing pre-existing bugs unrelated to the port (listed under deferred work in `06-execution-handoff.md`). Two pre-existing defects **are** in scope because the smoke test depends on them: count/find methods that read lazily-filled caches, and the listener cache bounded by `inputCount()` (`03` §7.11).

Constraints:

- The new runtime requires a C++17 clang toolchain (`--toolset` allows only `clang` or `msc`). This machine has gcc 13 only; clang, scons, ninja, and premake are not installed. `01-readiness-and-toolchain.md` gates on installing them.
- Static libraries linked into a Godot `.so` on Linux must be position-independent and must not be LTO bitcode when the final link uses GNU ld. The plan builds rive with `--with-pic --no-lto` and builds Skia without `-flto`.
- The extension must be compiled with the same layout-affecting defines as `librive.a` (`WITH_RIVE_TEXT`, `WITH_RIVE_LAYOUT`, `WITH_RIVE_AUDIO`). See `02-dependency-build.md`.

## Repository findings that drive the design

Verified facts (inspected during planning; commit hashes are exact):

1. **Submodule is 2138 commits behind.** `thirdparty/rive-cpp` is pinned at `7da35c1f319b33e66521ee6f11972c21ddc1fe0a` (2024-02-01). Upstream `origin/main` is `45d4d01dfd1fe70d3f9e73764538c16f63a04d07` (2026-09-10), which is exactly tag `runtime-v0.1.384`. `https://github.com/rive-app/rive-cpp` HTTP-redirects to `https://github.com/rive-app/rive-runtime`.
2. **The upstream build entry points this repo calls no longer exist.** `build/build.py` runs `sh build.sh` in the rive-cpp root; that file is absent on upstream `main`. It then runs `skia/dependencies/make_dependencies.sh` (which calls `make_skia.sh`, an iOS-first script that needs `xcrun`) and `skia/renderer/build.sh` (still present upstream but it calls the removed `../../build.sh`). `skia/renderer/build/macosx/build_skia_renderer.sh` references `skia/renderer/premake5.lua`, which also does not exist. None of the upstream Skia-renderer shell scripts work.
3. **Upstream now builds with premake via `build/build_rive.sh`.** It must be run from a directory containing `premake5.lua`, self-installs premake `v5.0.0-beta7` into `build/dependencies/` (not git-ignored upstream), writes outputs to `out/<config>/` (for example `out/release/librive.a`), defaults premake args to `--with_rive_text --with_rive_layout --with_rive_canvas`, and supports `--with-pic`, `--no-lto`, `--with_rive_audio=<disabled|system|external>`, `--arch=<host|arm64|x64|universal>`, and `-- <targets>` to build selected make targets. Third-party sources (harfbuzz, sheenbidi, yoga, miniaudio) are cloned at premake time by `build/dependency.lua` into `$DEPENDENCIES` or `<working dir>/dependencies`.
4. **The Skia renderer still exists upstream as source only.** `skia/renderer/premake5_v2.lua` defines static-lib project `rive_skia_renderer` (with `fatalwarnings All`). It resolves Skia as `$DEPENDENCIES/skia` when `DEPENDENCIES` is set and `SKIA_DIR` is unset; `SKIA_DIR` is a directory *name* under `skia/dependencies/`, never an absolute path (`skia/renderer/premake5_v2.lua:3-12`). It was last touched 2026-04-17. Upstream CI does not build it. Upstream's `tests/premake5.lua` exposes `--with-skia`, and `skia/thumbnail_generator/build/premake5.lua` shows the canonical composition: `dofile('rive_build_config.lua')`, `dofile(<runtime>/premake5_v2.lua)`, `dofile(<runtime>/skia/renderer/premake5_v2.lua)`, then link `skia rive rive_skia_renderer rive_harfbuzz rive_sheenbidi rive_yoga`.
5. **Upstream's living Skia pin is `rive-app/skia@bae2881`.** `skia/thumbnail_generator/build.sh` sets `SKIA_REPO=https://github.com/rive-app/skia.git` and `SKIA_BRANCH=bae2881014cb5c3216184cbb0b639045b8804931`. That commit is Skia milestone 113 and still provides `SkSurface::MakeRaster` and `SkImage::MakeFromEncoded`, both of which `skia/renderer/src/skia_factory.cpp` and this repo's `src/skia_instance.hpp` call. It has `bin/fetch-gn` and `tools/git-sync-deps` (no committed `bin/gn`). Its `gn/BUILDCONFIG.gn:41-44` sets `is_trivial_abi = !is_official_build` and asserts `!(is_debug && is_official_build)`; with `is_trivial_abi`, `sk_sp` gets `[[clang::trivial_abi]]` inside Skia only (`gn/skia/BUILD.gn:694-698`, `include/core/SkRefCnt.h:220`), which changes how `SkSurface::MakeRaster` returns its `sk_sp` and would silently mismatch the extension. This repo currently uses `google/skia` branch `chrome/m99` (2022).
6. **Upstream's Skia build scripts depend on Rive's cache infrastructure.** `skia/dependencies/make_skia_recorder.sh` sources `cache_helper.sh`, which downloads from `cdn.rive.app` and, after a local build, runs `aws s3 cp` under `set -e`. It also patches Skia's libpng with `pngprefix.h`. This repo must own its Skia build script instead.
7. **Static-library layout the extension links today** (`build/SConstruct`): `build/{platform}/bin/{target}/librive.a`, `skia/renderer/build/{platform}/bin/{target}/librive_skia_renderer.a`, `dependencies/{platform}/cache/bin/{target}/librive_harfbuzz.a` and `librive_sheenbidi.a`, and `skia/dependencies/skia/out/static/libskia.a`. The extension is compiled with **no** `WITH_RIVE_*` defines. Upstream's new output layout is `out/<config>/lib<name>.a`, and `rive_yoga` and `miniaudio` are new required libraries.
8. **Layout-affecting defines.** On upstream `main`, `WITH_RIVE_LAYOUT` appears in 32 public headers, `WITH_RIVE_AUDIO` in 10, `WITH_RIVE_TEXT` in 9 (for example `include/rive/artboard.hpp:851`). Public headers under `include/rive/layout/` include `yoga/Yoga.h`; `include/rive/audio/*.hpp` include `miniaudio.h`. Compiling the extension without the same defines produces silent ODR/layout mismatches.
9. **Core API deltas that touch `src/`** (pin -> main):
   - `rivestd::make_unique` removed with the C++17 bump (upstream `9ea0fb6a`, 2026-03-24). Used at `src/skia_instance.hpp:26` and `:69`.
   - `File::import(...)` now returns `rive::rcp<File>` (was `std::unique_ptr<File>`). Used at `src/utils/read_rive_file.hpp:38` and stored as `Ptr<rive::File>` in `src/api/rive_file.hpp:32`.
   - `StateMachineListener::listenerType()` is removed (commented out in `include/rive/animation/state_machine_listener.hpp:23`). Replacement query is `hasListener(ListenerType)`. Used at `src/api/rive_listener.hpp:82`.
   - `src/rive_exceptions.hpp:35` and `:43` use `_NOEXCEPT`, a libc++-only macro (absent from libstdc++ on this machine). Unrelated to rive, but it blocks the first Linux compile.
   - `RiveFile::get_artboard_count`, `RiveArtboard::get_scene_count`/`get_animation_count`, `RiveScene::get_input_count`/`get_listener_count`, and every `find_*`/`get_*s`/`get_*_names` read `Instances::get_size()` / iterate the instantiated map (`src/api/instances.hpp:71-73`), which is filled only by `RiveInstance::instantiate()` from the inspector path (`src/rive_viewer_base.cpp:114`, `:168`). A script that sets `file_path` and queries counts sees zeros. Unrelated to rive, but it makes any scripted verification vacuous.
   - `ImageTexture::update` is a no-op under Godot's headless dummy renderer; only the extension-owned `Ref<Image>` (`src/rive_viewer_base.h:55`, mutated in place by `set_data` at `src/rive_viewer_base.cpp:65`) reflects rendered pixels headless.
   - `ListenerType` now lives in `include/rive/listener_type.hpp` with 18 values (was 5 at the pin). `src/api/rive_listener.hpp` binds 5 of them as integer constants.
   - Source-compatible signature changes (no edit required, must recompile): `computeAlignment(..., const float scaleFactor = 1.0f)`, `Artboard::advance(float, AdvanceFlags = ...)`, `StateMachineInstance::pointerMove(Vec2D, float timeStamp = 0, int pointerId = 0)` and `pointerDown/pointerUp(Vec2D, int pointerId = 0)` now return `HitResult`, and `Fit` gained a `layout` value.
   - Unchanged and verified present: `artboardAt/artboardNameAt/artboardCount`, `stateMachineAt/animationAt/…NameAt/…Count`, `SMIInput::name()/input()`, `SMIBool/SMINumber::value`, `Scene::bounds/durationSeconds/isTranslucent/loop`, `Mat2D::invertOrIdentity/decompose`, `Component::hasDirt/addDirt(ComponentDirt, bool)`, `ComponentDirt::Components`, `Span(T*, size_t)`, `LinearAnimationInstance::durationSeconds/time/direction/reset`.
10. **godot-cpp pin facts.** `godot-cpp/SConstruct` sets `-std=c++17`, has no `disable_exceptions` option (the extension uses `throw`/`catch`), sets library suffix `.{platform}.{target}.{arch}`, adds `-fPIC` on Linux, defaults macOS `arch` to `universal` (which would fail to link against arm64-only rive/Skia archives), and offers `use_llvm=yes` on Linux.
11. **Local environment.** Linux x86_64, Godot 4.6.3 at `~/.local/bin/godot`, Python 3.12, gcc/g++ 13, cmake, make. Missing: clang, scons, ninja, premake5, gn. The demo project (`demo/project.godot`) targets features `4.2` with the `mobile` renderer.
12. **Committed binaries.** `demo/bin/librive.macos.template_{debug,release}.framework/` contain 18 MB and 13 MB universal Mach-O dylibs tracked as regular git blobs (no LFS).

## Key decisions

1. **Target `runtime-v0.1.384` (= upstream `main` today), not an intermediate commit.** Reason: it is the newest tag, it is identical to `main`, and the Skia renderer source at that commit compiles against milestone-113 Skia APIs per finding 5. Rejected: pinning to the last commit before the C++17 bump (would retain `rivestd` but still lack a working build script and would defer the same port).
2. **Own the dependency build inside this repository.** A new `build/rive/premake5.lua` (mirroring `skia/thumbnail_generator/build/premake5.lua`) composes upstream's `rive_build_config.lua`, root `premake5_v2.lua`, and `skia/renderer/premake5_v2.lua`, and is driven by upstream `build/build_rive.sh`. A new `build/skia/build_skia.py` (or `.sh`) fetches `rive-app/skia@bae2881` and runs `gn`/`ninja` with a raster-only argument set. Rejected: calling upstream shell scripts (all stale or CDN-dependent, finding 2 and 6); vendoring prebuilt archives (no upstream archives exist for this Skia/renderer pair).
3. **Build Skia CPU-raster only (`skia_enable_gpu=false`, `skia_enable_ganesh=false`, `skia_enable_graphite=false`, `skia_use_gl=false`, `skia_use_metal=false`, `skia_use_fonthost_mac=false`), with `is_trivial_abi=false` in both configs.** Reason: the extension draws into `SkSurface::MakeRaster` and copies pixels (`src/skia_instance.hpp`); no GPU context exists. This removes GL/Metal/Cocoa link requirements on both platforms. Fallback if `skia_factory.cpp` fails to compile without GPU headers: re-enable `skia_enable_gpu=true` and add `GL` (Linux) / `Cocoa.framework` (macOS) to the link line; recorded as a gate in `02-dependency-build.md`.
4. **Match upstream's default feature set: `--with_rive_text --with_rive_layout --with_rive_audio=system`.** Reason: `.riv` files in `demo/examples/` include text and fonts; the pinned build already used `--with_rive_text --with_rive_audio=system`; `--with_rive_layout` is upstream's default and newer `.riv` files may contain layouts. `--with_rive_canvas` (also an upstream default) is **dropped** because it defines `RIVE_CANVAS`, which appears in only 2 public headers and pulls in `RenderContext` code the Skia path does not use. The extension compiles with `WITH_RIVE_TEXT`, `WITH_RIVE_LAYOUT`, `WITH_RIVE_AUDIO` defined and with the yoga and miniaudio include directories on its path.
5. **Linux and macOS arm64 only, PIC and no LTO everywhere.** Reason: constraints above and finding 10. Windows, Android, iOS, Web, and macOS universal are non-goals.
6. **Port, do not redesign, the GDScript API.** `RiveListener.get_type()` changes semantics because upstream removed the single listener type; it returns the first matching type in a fixed priority order and a new `has_type(type)` method exposes the real query. Count and find methods switch from cache size to runtime counts so scripts get real answers. A `get_image()` accessor is added for verification. Everything else keeps its current name and signature. Rejected: exposing new runtime features (out of scope).

## Dependency transition model

```
BEFORE (pin 7da35c1f, 2024-02-01)                AFTER (runtime-v0.1.384, 2026-09-10)
----------------------------------               -------------------------------------
rive-cpp/build.sh (premake, make)          ->    rive-cpp/build/build_rive.sh run from
  -> build/macosx/bin/<cfg>/librive.a            godot-rive/build/rive/ (new premake5.lua)
                                                   -> build/rive/out/<cfg>/librive.a
                                                      librive_skia_renderer.a, librive_harfbuzz.a,
                                                      librive_sheenbidi.a, librive_yoga.a, libminiaudio.a

skia/dependencies/make_dependencies.sh     ->    godot-rive/build/skia/build_skia.py (new)
  google/skia chrome/m99 -> out/static            rive-app/skia@bae2881 -> build/deps/skia/out/<cfg>/libskia.a

skia/renderer/build.sh                     ->    (folded into build/rive/premake5.lua target)
  -> skia/renderer/build/macosx/bin/<cfg>/...

build/SConstruct: 5 libs, no defines       ->    build/SConstruct: 7 libs, WITH_RIVE_* defines,
                                                 linux + macos outputs, link groups on Linux

demo/rive.gdextension: macos only          ->    macos.<target> + linux.<target>.x86_64
```

Control flow at runtime is unchanged: `RiveViewerBase` -> `RiveInstance` (file/artboard/scene) -> `SkiaInstance` (raster surface + `SkiaRenderer`) -> `Image`/`ImageTexture` -> `CanvasItem::draw_texture_rect`.

## Risks, assumptions, unresolved decisions, gates

Risks:

- **R1: `rive_skia_renderer` may not compile against milestone-113 Skia with `fatalwarnings All`.** Upstream does not CI-build it. Mitigation: gate G2 in `02-dependency-build.md`; allowed fix is a local patch file applied to the submodule checkout (see `02`), not editing the submodule in place.
- **R2: Skia's `gn` build on Linux may need `clang` at a specific version or `libfreetype`/`fontconfig` dev headers.** Mitigation: `skia_use_freetype=false`, `skia_use_fontconfig=false`, `skia_use_system_*=false`; gate G1 records the exact failing dependency if any.
- **R3: Link-time symbol collisions** between Skia's bundled libpng/zlib/harfbuzz-free build and rive's renamed harfbuzz. Upstream renames harfbuzz symbols (`rive_harfbuzz_renames.h`), and Skia is built with `skia_use_icu=false skia_use_harfbuzz=false`, so no overlap is expected. Mitigation: `nm` check in `04`.
- **R4: Undefined system symbols at `dlopen`** (miniaudio needs `dl`, `pthread`, `m` on Linux; CoreAudio/AudioToolbox on macOS). Mitigation: explicit link list in `04` and the `ldd -r`/`dlopen` gate in `05`.
- **R5: `build_rive.sh` refuses to reuse an `out/` directory configured with different premake args.** Mitigation: `build.py --clean` deletes `build/rive/out/<cfg>`.

Assumptions (labelled, not verified):

- A1: `rive-app/skia@bae2881` builds with `gn`'s default toolchain on Linux when `cc=clang cxx=clang++` is passed. (Upstream builds it only on macOS.)
- A2: Godot 4.6.3 loads a GDExtension built against godot-cpp 4.1.1 headers with `compatibility_minimum = 4.1`. (Godot documents forward compatibility of the GDExtension interface.)
- A3: The `.riv` files in `demo/examples/` (2023 format) import under runtime 0.1.384. Upstream keeps backward file compatibility; the smoke test verifies this per file.

Unresolved decisions: none blocking. Non-blocking:

- N1: Whether to keep committed macOS binaries in git at all after regeneration (they are 31 MB of blobs). Default: keep, regenerate on macOS. Owner: user. Resolution point: before the macOS packaging PR.
- N2: The committed macOS binaries are universal today and `README.md:59` promises universal; this plan ships arm64-only (decision 5), which was inferred from the user's "Linux + macOS" answer, not chosen explicitly. Default: arm64-only. Owner: user. Resolution point: before WP3 starts (the Skia build is single-arch, so a later change forces WP3 and WP4 to be redone). If universal is required, WP3 builds Skia twice (`target_cpu=arm64` and `x64`) and `lipo`s, WP4 passes `universal` to `build_rive.sh`, and `04` passes `arch=universal` to scons.

Stop/go gates (details in the work files):

| Gate | Where | Go condition |
| --- | --- | --- |
| G0 | `01` | clang, scons, ninja, python3, godot present at the required versions |
| G1 | `02` | `libskia.a` builds on Linux with the raster-only args |
| G2 | `02` | `librive.a` and `librive_skia_renderer.a` build with `--with-pic --no-lto` |
| G3 | `03` | extension compiles and links on Linux |
| G4 | `05` | smoke test passes headless on Linux and the editor visual check passes on Linux |
| G5 | `05` | macOS arm64 build, smoke test, undefined-symbol check, and editor visual check pass |

## Document map

| File | Purpose |
| --- | --- |
| `00-overview.md` | This file: context, decisions, model, risks, map |
| `01-readiness-and-toolchain.md` | Toolchain install (gate G0), submodule move, repository hygiene |
| `02-dependency-build.md` | Skia fetch/build script, premake wrapper and bootstrap, rive + Skia renderer build, `build.py` rewrite (gates G1, G2) |
| `03-extension-source-port.md` | Exact `src/` edits for the new runtime API (gate G3) |
| `04-scons-and-packaging.md` | `SConstruct` link/define changes, `rive.gdextension`, `.gitignore`, VS Code paths |
| `05-verification.md` | Headless smoke test, editor visual check, macOS pass, README update (gates G4, G5) |
| `06-execution-handoff.md` | Ordered work packages, commands, definition of done, deferred work |
