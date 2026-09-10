# 05 – Verification: smoke test, editor check, macOS pass, README

Gates G4 (Linux) and G5 (macOS) live here. Prerequisite: G3.

## WP9: Headless smoke test script

### Goal and prerequisite state

A repeatable, non-interactive check that the built extension loads and works in Godot on the current platform. Prerequisite: the platform's `demo/bin/` binary exists (G3 on Linux; WP11 on macOS).

### Repository evidence

- `demo/project.godot`: `config/features=PackedStringArray("4.2", "Mobile")`, `renderer/rendering_method="mobile"`, main scene `res://main.tscn`.
- `demo/examples/` holds 50 `.riv` files (verified with `find demo/examples -name "*.riv" | wc -l`), including text-bearing ones (`new_text.riv`, `long_name.riv`) and out-of-band asset example `out_of_band/walle.riv`.
- Public API available to a script (verified in `src/rive_viewer_base.h` `RIVE_VIEWER_BIND` and `src/api/*.hpp`): `RiveViewer.file_path`, `get_file()`, `get_artboard()`, `get_scene()`, `get_animation()`, `get_elapsed_time()`, `go_to_artboard/scene/animation`, `press_mouse/release_mouse/move_mouse`; `RiveFile.get_artboard_count()/get_artboards()/get_artboard(i)`; `RiveArtboard.get_scene_count()/get_animation_count()/get_scene(i)/get_bounds()`; `RiveScene.get_input_count()/get_input(i)/get_listener_count()/get_listener(i)`; `RiveInput.get_value()/set_value()/is_bool()/is_number()`; `RiveListener.get_type()` and (new in `03`) `has_type()`.
- `RiveViewerBase::on_process` runs only when `owner->is_node_ready()` and not paused, and creates the `Image`/`ImageTexture` lazily; in headless mode `ImageTexture::create_from_image` and `update` succeed against the dummy rendering server, but that server's `texture_2d_update` is a no-op, so only the extension-owned `Image` (exposed by the new `get_image()` accessor from `03` §7.10) reflects the last raster.
- `RiveViewer` (a `Control`) forwards its size to the extension only on `NOTIFICATION_RESIZED` (`src/rive_viewer.hpp:27-29`), and the Skia surface is (re)created only from the resulting `transform_changed` event (`src/skia_instance.hpp:67-70`); `RiveViewer2D` exposes `size` as a plain property (`src/rive_viewer_2d.hpp:36`) that sets `props.size` directly. The raster check therefore uses `RiveViewer2D`, and nodes are added to the tree **before** their size is set.
- Count/find methods answer from the runtime after `03` §7.11; before that change they returned the size of a cache that only the inspector fills.
- Godot only loads extensions listed in `res://.godot/extension_list.cfg`, which the editor's import scan writes; `demo/.godot/` is git-ignored (`.gitignore:2`) and absent on a clean checkout. `godot --headless --path demo --import` performs that scan without opening the editor.
- `elapsed` accumulates the real frame delta (`src/rive_viewer_base.cpp:215`); headless frames are throttled by the low-processor-usage sleep, so wall-clock delta is not deterministic. `--fixed-fps 60` makes every frame report `delta = 1/60`.
- `RiveViewer` is a `Control` and processes on `NOTIFICATION_INTERNAL_PROCESS`; the scene tree must run frames, so the script must be a `SceneTree`-derived script (`godot --headless --script`) that adds the node, awaits `process_frame` N times, then quits.

### Change surface

`demo/smoke_test.gd` (new, `extends SceneTree`). Steps:

1. Assert `ClassDB.class_exists("RiveViewer")`, `"RiveViewer2D"`, `"RiveFile"`, `"RiveScene"`, `"RiveInput"`, `"RiveListener"`, `"RiveAnimation"`, `"RiveArtboard"`; otherwise print `extension not loaded: run 'godot --headless --path demo --import' first and check demo/.godot/extension_list.cfg and demo/bin/` and `quit(1)`.
2. For every `*.riv` under `res://examples/` (recursive): create a `RiveViewer2D`, add it to the root, set `size = Vector2(256, 256)`, set `file_path`, await one `process_frame`, and require `get_file() != null and get_file().get_artboard_count() > 0` and `get_file().get_artboard(0) != null`. Collect failures; do not stop at the first. Free the node afterwards.
3. For one example with a state machine that has inputs (candidates from a string scan of the files: `res://examples/on_off.riv`, `res://examples/rocket.riv`, `res://examples/rating-animation.riv`; `demo/demo_control.gd` drives an input named `Rooms` on the viewer in `demo_control.tscn`, so that scene's file is a known-good choice; confirm `get_scene().get_input_count() > 0` at implementation time): select artboard 0 and scene 0 via `go_to_artboard`/`go_to_scene`, await 60 `process_frame`s, require `abs(get_elapsed_time() - 1.0) < 0.05` (valid only under `--fixed-fps 60`), require `get_image() != null` with `get_width() == 256 and get_height() == 256`, and require that at least 1 % of its pixels have alpha > 0 (count with `Image.get_pixel` over a 16×16 sample grid, or `get_data()` stride 4); this proves the Skia raster path drew something into the extension's buffer. Also require no engine errors captured (see step 6).
4. Input round-trip: for the first `RiveInput` that `is_number()`, `set_value(0.75)` then require `get_value()` within `1e-5` of `0.75`; for the first `is_bool()`, toggle and read back.
5. Listener API: for every listener of that scene, if `get_type() != -1` require `has_type(get_type())` is `true`; if `get_type() == -1` log the listener name (its types are ones the extension does not bind).
6. Error capture: connect to nothing (Godot has no error signal); instead run with `--quiet` off and have the outer shell grep the log for `ERROR:`/`SCRIPT ERROR:` and `[Rive]` error lines. Document the exact command in the README.
7. Print a summary table (file, artboards, scenes, animations) and `quit(0)`; `quit(1)` on any failure.

Invocation (from the repository root):

```bash
godot --headless --path demo --import                      # writes demo/.godot/extension_list.cfg; exits 0
godot --headless --fixed-fps 60 --path demo --script smoke_test.gd 2>&1 | tee /tmp/rive-smoke.log
test ${PIPESTATUS[0]} -eq 0 && ! grep -E "ERROR:|SCRIPT ERROR:|\[Rive\] .*(Failed|Unable)" /tmp/rive-smoke.log
git diff --stat demo/project.godot                         # Godot 4.6 may rewrite config/features; see below
```

`godot --import` (and the editor) may rewrite `demo/project.godot` (`config/features` is `"4.2"` today). If the only change is the features array, commit it once in WP12; otherwise `git checkout -- demo/project.godot` before committing.

(Use the scratch directory of the executing session instead of `/tmp` when one is configured.)

### Acceptance criteria (gate G4 on Linux, together with WP10)

- The three commands above exit 0 for the debug and the release `.so` (Godot picks `linux.debug.*` when run from the editor/debug build and `linux.release.*` for exported/`--release` runs; test debug via the editor binary and release by temporarily pointing `linux.debug.x86_64` at the release file, or by running a release export template; record which method was used).
- The summary lists 50 files with `artboards > 0` each. If any file fails to import, record its name; a failure is a G4 blocker unless the file is shown to be corrupt at the old pin too (check by building the old pin is out of scope; treat as blocker and investigate).

## WP10: Editor visual check (manual gate)

### Goal

Confirm rendering, not just API plumbing, on Linux.

### Procedure

1. `godot --path demo --editor`. Open `main.tscn` and `demo_2d.tscn`. The `RiveViewer`/`RiveViewer2D` previews animate in the editor (the extension renders in the editor when `is_editor_hint()`; see `src/rive_viewer_base.cpp:37` for the input gate and `on_process` for the redraw).
2. Press Play. `demo/main.gd` prints artboard, scene, listener, and animation info at `_ready` and prints `Property … changed!` lines from the `scene_property_changed` signal; expect those prints in the Output panel with no `[Rive]` errors. Open `demo_control.tscn` and move the slider: `demo/demo_control.gd` sets the `Rooms` input via `get_scene().find_input("Rooms").set_value(value)`; expect the animation to react and a `Property Rooms changed!` line if that viewer has the signal connected (it does not by default; the reaction is visual). Hover and click a viewer and expect no errors.
3. Take a screenshot with the editor's built-in capture or `Viewport.get_texture().get_image().save_png()` from a temporary script and compare by eye with `screenshots/screenshot_1.png`. No pixel diff is required.

### Acceptance criteria (part of G4 on Linux and G5 on macOS)

- Animations play in editor and at runtime; no `[Rive]` errors in the Output panel; no crash on scene switch or on changing `file_path` in the inspector (regression area of resolved issues #1 and #12 in git history).
- A screenshot of the running demo is attached to the PR for each platform.

## WP11: macOS arm64 pass

### Goal and prerequisite state

The full pipeline runs on an Apple Silicon Mac and regenerates the committed framework binaries. Prerequisite: G4 on Linux (so remaining failures are macOS-specific).

### Repository evidence

- Current README states builds were only tested on M1 macOS and provides universal binaries. This plan produces arm64-only binaries (decision 5 in `00`).
- `godot-cpp/tools/macos.py` honours `arch=arm64`, `macos_deployment_target`, `macos_sdk_path`.
- Upstream `build_rive.sh` maps `arm64` to `--arch=arm64` and output dir `out/arm64_<cfg>`; root `premake5_v2.lua` reads `MACOS_SYSROOT` only for `variant=runtime`.

### Procedure

1. Toolchain: Xcode Command Line Tools (`clang`), `brew install scons ninja python@3`. Godot 4.6 app or CLI on PATH as `godot`.
2. `python3 build/build.py --platform=macos --arch=arm64 --target=debug` then `--target=release`.
3. Run the WP9 smoke test and the WP10 visual check.
4. Commit the regenerated `demo/bin/librive.macos.template_{debug,release}.framework/` binaries.

### Acceptance criteria (gate G5)

```bash
DYLIB=demo/bin/librive.macos.template_release.framework/librive.macos.template_release
file "$DYLIB"                                     # Mach-O 64-bit dynamically linked shared library arm64 (or universal per N2)
# godot-cpp links with -Wl,-undefined,dynamic_lookup, so undefined symbols surface only at dlopen.
# Demangle before filtering: Itanium names on macOS start with __ZN…, so raw-prefix greps are vacuous.
! nm -u "$DYLIB" | c++filt | grep -qE 'rive::|\bSk[A-Z]|\bYG|\bhb_|\bma_'   # no unresolved rive/Skia/yoga/harfbuzz/miniaudio symbols
python3 -c "import ctypes,sys; ctypes.CDLL(sys.argv[1], ctypes.RTLD_NOW)" "$DYLIB"   # dlopen probe exits 0 (fails on any missing framework symbol)
otool -L "$DYLIB"                                 # review: CoreText, CoreGraphics, CoreFoundation, CoreAudio, AudioToolbox present
codesign --verify --deep demo/bin/librive.macos.template_release.framework 2>/dev/null || true   # informational; ad-hoc signing is acceptable for local runs
```

Plus the WP9 commands (including `--import`) exiting 0 and the WP10 checklist with screenshot. Decision N2 in `00` (arm64-only vs universal) must already be resolved before WP3 ran on the Mac; the default is arm64-only.

## WP12: README and repository docs

### Change surface: `README.md`

- Third-party section: `rive-cpp` link -> `https://github.com/rive-app/rive-runtime` (name the tag `runtime-v0.1.384`); `skia` -> `https://github.com/rive-app/skia` at `bae2881` (state that it is fetched by `build/skia/build_skia.py`, not included in the submodule).
- Building: prerequisites become Python 3, git, SCons, Ninja, clang (Linux: distro package; macOS: Xcode CLT). Commands: `python3 build/build.py --platform=linux --target=debug` etc. State that the first run clones Skia and its dependencies (large download) and bootstraps premake.
- Installation: binaries provided for macOS arm64 (debug/release) unless decision N2 in `00` selects universal; Linux x86_64 must be built (or, if the user later decides to commit `.so` files, update this line). Update the copy list (`demo/bin/`, `demo/icons/`, `demo/rive.gdextension`).
- Add a "Verifying" subsection with the WP9 commands (`--import` first, then the `--fixed-fps 60` smoke test).
- Roadmap: tick nothing new; change "Other platform support" to note Linux x86_64 is supported.
- Contributing: remove Linux from the "help wanted" list; keep Windows, Android, iOS, Web.

### Acceptance criteria

- Every command in the README was executed verbatim during WP9–WP11 and exits 0.
- No README statement claims universal macOS binaries.
