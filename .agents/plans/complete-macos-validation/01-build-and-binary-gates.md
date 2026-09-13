# Build and binary gates

## WP1: Establish a reproducible macOS workspace

### Goal and prerequisite state

Prepare branch `update` at `96dba5a` with exact submodule pins and runnable host tools. No build outputs are trusted yet.

### Evidence and change surface

- `.gitmodules` defines `godot-cpp` and `thirdparty/rive-cpp`.
- `build/build.py` requires Python, SCons, clang, Ninja, Git, and Xcode SDK discovery.
- Machine-local changes only: initialize submodules and provide SCons. Do not edit repository dependency declarations for tool installation.

### Procedure

1. Verify `git status --short --branch` shows `update...origin/update` with only the plan directory as a planning change.
2. Run `git submodule sync --recursive` and `git submodule update --init --recursive`.
3. Verify exact submodule HEADs against the superproject gitlinks.
4. Verify `python3`, `scons`, `ninja`, `xcrun clang++`, and `/Applications/Godot.app/Contents/MacOS/Godot` execute. Add the Godot executable directory to the task-local `PATH`; do not change shell startup files.
5. If `scons` is absent, install it with Homebrew or an isolated Python environment, then record `scons --version` in the validation notes.

### Acceptance criteria (G0)

```bash
test "$(git -C godot-cpp rev-parse HEAD)" = c370f0f24a6e4ce767e21673731838f1affc45fb
test "$(git -C thirdparty/rive-cpp rev-parse HEAD)" = 45d4d01dfd1fe70d3f9e73764538c16f63a04d07
python3 --version
scons --version
ninja --version
xcrun clang++ --version
/Applications/Godot.app/Contents/MacOS/Godot --version
```

Stop if a pin differs. Do not advance or repair a submodule by choosing a newer commit.

## WP2: Produce clean debug and release frameworks

### Goal and prerequisite state

Regenerate target-specific Skia, Rive, and extension outputs on the Apple Silicon host. G0 must pass.

### Exact surface and lifecycle

- Generated and ignored: `build/deps/`, `build/rive/out/`, SCons objects.
- Replaced tracked artifacts after successful builds:
  - `demo/bin/librive.macos.template_debug.framework/librive.macos.template_debug`
  - `demo/bin/librive.macos.template_release.framework/librive.macos.template_release`
- `build/patches/godot-cpp/01-avoid-duplicate-instance-binding.patch` temporarily modifies the `godot-cpp` checkout during builds. Cleanup must restore that submodule after validation.

### Procedure

1. Create `VALIDATION_DIR` with `mktemp -d`, retain its printed path, and enable zsh `pipefail` before the first pipeline.
2. Run `python3 build/build.py --clean --platform=macos --arch=arm64 --target=debug` and the corresponding release clean command, capturing each to its target-specific log. A clean command may fail before initial output exists only if SCons requires initialized generated state; if so, remove only the explicit target directories listed by `build.py`, document the exception, and continue.
3. Run the debug build from repository root and capture `build-macos-debug.log`.
4. Record the debug framework SHA-256 immediately after its successful build.
5. Run the release build from repository root, capture `build-macos-release.log`, and record the release SHA-256 immediately.
6. Do not rerun `--clean` after a successful build because it can restore submodule patches and remove the target output. Perform explicit submodule restoration only after all validation.

### Commands

```bash
VALIDATION_DIR=$(mktemp -d)
set -o pipefail
python3 build/build.py --clean --platform=macos --arch=arm64 --target=debug 2>&1 | tee "$VALIDATION_DIR/clean-macos-debug.log"; test $? -eq 0
python3 build/build.py --platform=macos --arch=arm64 --target=debug 2>&1 | tee "$VALIDATION_DIR/build-macos-debug.log"; test $? -eq 0
shasum -a 256 demo/bin/librive.macos.template_debug.framework/librive.macos.template_debug | tee "$VALIDATION_DIR/sha256-macos-debug.txt"
python3 build/build.py --clean --platform=macos --arch=arm64 --target=release 2>&1 | tee "$VALIDATION_DIR/clean-macos-release.log"; test $? -eq 0
python3 build/build.py --platform=macos --arch=arm64 --target=release 2>&1 | tee "$VALIDATION_DIR/build-macos-release.log"; test $? -eq 0
shasum -a 256 demo/bin/librive.macos.template_release.framework/librive.macos.template_release | tee "$VALIDATION_DIR/sha256-macos-release.txt"
```

### Error handling

- If the build scripts fail, retain the full command and first actionable error.
- A corrective repository edit is allowed only in an existing build/source path implicated by the failure.
- `demo/project.godot` may disable multi-threaded editor imports if the cold-import gate reproduces Godot's confirmed multi-font import race (godotengine/godot#111039).
- After a correction, restart the affected target from its clean command and rerun all downstream gates.
- Never edit either submodule directly. Add a checked-in patch under the existing `build/patches/<submodule>/` parent when a submodule compatibility correction is required.

### Acceptance criteria (G1 and G2)

- All four clean/build commands exit 0, and both builds start from clean target outputs.
- Both framework executables exist, are nonempty, and `file` reports only arm64.
- The debug and release framework executables have different SHA-256 hashes. The two clean build logs identify their respective `template_debug` and `template_release` SCons targets; identical hashes or a target mismatch is a stop condition.

## WP3: Inspect framework linkage and loadability

### Goal

Reject artifacts that build successfully but retain unresolved static-library or platform dependencies.

### Procedure and commands

Run the following for both `debug` and `release`, substituting the exact executable path:

```bash
file "$DYLIB"
nm -gU "$DYLIB" | grep -q 'rive_library_init'
nm -u "$DYLIB" | c++filt | sed -E 's/^[[:space:]]*_//' > "$VALIDATION_DIR/$(basename "$DYLIB").undefined.txt"
! grep -qE 'rive::|(^|[^[:alnum:]_])Sk[A-Z]|(^|[^[:alnum:]_])YG|(^|[^[:alnum:]_])hb_|(^|[^[:alnum:]_])ma_' "$VALIDATION_DIR/$(basename "$DYLIB").undefined.txt"
python3 -c "import ctypes,os,sys; ctypes.CDLL(sys.argv[1], mode=os.RTLD_NOW)" "$DYLIB"
otool -L "$DYLIB"
codesign --verify --deep "$DYLIB" 2>/dev/null || true
```

### Acceptance criteria

- `file` reports an arm64 Mach-O dynamically linked shared library, not universal or x86_64.
- `rive_library_init` is exported.
- The unresolved-symbol filter is empty.
- `ctypes.CDLL(..., RTLD_NOW)` exits 0.
- `otool -L` shows CoreText, CoreGraphics, CoreFoundation, CoreAudio, and AudioToolbox as direct load commands. Check each name explicitly; missing expected linkage is investigated rather than waived.
- Code-sign verification is informational because local linker output may be ad-hoc signed; loadability is the required gate.
- Before trusting the unresolved-symbol filter, run representative `_YGNodeFree`, `_hb_shape`, and `_ma_engine_init` fixture lines through the same underscore-normalization and regular expression and require the filter to match all three.

## WP4: Exercise a pristine editor import

### Goal

Prove that a checkout without a generated `.godot` cache can import the demo reliably on Godot 4.6.3.

### Procedure and acceptance criteria

1. Copy the tracked `demo/` tree plus the newly built frameworks into a temporary directory without `.godot`.
2. Run `/Applications/Godot.app/Contents/MacOS/Godot --headless --editor --import --path <temporary-demo>` at least three times from independently pristine copies.
3. Require every run to exit 0 without `ERROR`, `CRASH`, or segmentation-fault output.
4. Keep `editor/import/use_multiple_threads=false` in `demo/project.godot` while godotengine/godot#111039 remains unresolved; it prevents the confirmed parallel multi-font importer race reproduced during this validation.
