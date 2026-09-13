# 06 – Execution handoff

Planning only; no implementation has occurred. Work on a branch off `main` (for example `update-rive-runtime`). Commit after each work package so a failing later package can be bisected.

## Dependency-ordered work packages

| # | Package | File | Changes | Prerequisites | Parallelizable with |
| --- | --- | --- | --- | --- | --- |
| WP2 | Move submodule, fix URL, `ignore = untracked` | `01` | `.gitmodules`, `thirdparty/rive-cpp` gitlink | none | WP1 |
| WP1 | Linux toolchain readiness (G0, tool versions only) | `01` | machine only | none | WP2, WP3 design |
| WP3 | Skia fetch/build script (G1) | `02` | `build/skia/build_skia.py` (new), `.gitignore` lines | G0; decision N2 resolved before the macOS run | WP4 premake bootstrap (after `mkdir -p build/deps`) |
| WP4 | premake wrapper: bootstrap (`nobuild`), then rive + Skia renderer (G2) | `02` | `build/rive/premake5.lua` (new), optional `build/patches/rive-cpp/*.patch` (new) | G0, WP2; WP3 output (`build/deps/skia`) must exist before the compile step | — |
| WP6 | `build/build.py` rewrite | `02` | `build/build.py` | WP3, WP4 | WP7 |
| WP7 | Source port | `03` | `src/skia_instance.hpp`, `src/utils/read_rive_file.hpp`, `src/api/rive_file.hpp`, `src/api/rive_artboard.hpp`, `src/api/rive_scene.hpp`, `src/api/rive_listener.hpp` (counts/find, listeners bound), `src/rive_exceptions.hpp` (`_NOEXCEPT`), `src/rive_viewer_base.h` (`get_image`), nine Skia include lines in `src/rive_viewer_base.h`, `src/rive_instance.hpp`, `src/skia_instance.hpp` | G2 | WP8 |
| WP8 | SCons, `.gdextension`, ignore, VS Code (G3) | `04` | `build/SConstruct`, `demo/rive.gdextension`, `.gitignore`, `.vscode/c_cpp_properties.json` | WP7 | — |
| WP9 | Headless smoke test (G4 with WP10) | `05` | `demo/smoke_test.gd` (new) | G3 | WP12 drafting |
| WP10 | Editor visual check (G4 with WP9; G5 on macOS) | `05` | none (screenshot in PR) | WP9 | — |
| WP11 | macOS arm64 pass (G5) | `05` | `demo/bin/*.framework/*` regenerated | G4, a Mac | — |
| WP12 | README and docs | `05` | `README.md` | G4 (Linux text), G5 (macOS text) | — |

Strict order for a single implementer: WP2 → WP1 → WP3 → WP4 → WP6 → WP7 → WP8 → WP9 → WP10 → WP12 (Linux text) → WP11 → WP12 (macOS text).

## Per-package verification commands

WP2:

```bash
git submodule status thirdparty/rive-cpp | grep -q '^ 45d4d01dfd1fe70d3f9e73764538c16f63a04d07'
git config -f .gitmodules submodule.thirdparty/rive-cpp.url | grep -q 'rive-app/rive-runtime.git$'
```

WP1 (G0):

```bash
clang++ --version && scons --version && ninja --version && python3 --version && godot --version
```

WP3 (G1):

```bash
python3 build/skia/build_skia.py --target=debug && python3 build/skia/build_skia.py --target=release
test -s build/deps/skia/out/debug/libskia.a && test -s build/deps/skia/out/release/libskia.a
for c in debug release; do build/deps/skia/bin/gn args build/deps/skia/out/$c --list=is_trivial_abi --short; done   # is_trivial_abi = false, twice
nm build/deps/skia/out/release/libskia.a | grep -c " U gl[A-Z]"   # expect 0
```

WP4 (G2):

```bash
mkdir -p build/deps
cd build/rive && unset SKIA_DIR && export DEPENDENCIES="$PWD/../deps" \
  RIVE_PREMAKE_ARGS="--with_rive_text --with_rive_layout --with_rive_audio=system --with-pic --no-lto"
../../thirdparty/rive-cpp/build/build_rive.sh nobuild release          # bootstrap premake, clone deps, generate makefiles
ls ../../thirdparty/rive-cpp/build/dependencies/premake-core/bin/v5.0.0-beta7_release/premake5 out/release/Makefile
../../thirdparty/rive-cpp/build/build_rive.sh release -- rive rive_skia_renderer rive_harfbuzz rive_sheenbidi rive_yoga miniaudio
ls out/release/librive.a out/release/librive_skia_renderer.a out/release/librive_harfbuzz.a out/release/librive_sheenbidi.a out/release/librive_yoga.a out/release/libminiaudio.a
```

WP6:

```bash
python3 build/build.py --help
python3 build/build.py --platform=linux --target=debug --skip-skia --skip-rive   # exercises the scons step only, after WP8
```

WP7 + WP8 (G3):

```bash
python3 build/build.py --platform=linux --target=debug && python3 build/build.py --platform=linux --target=release
ldd -r demo/bin/librive.linux.template_release.x86_64.so | grep -c "undefined symbol"   # 0
nm -D demo/bin/librive.linux.template_release.x86_64.so | grep -c " T rive_library_init"   # 1
! nm -D demo/bin/librive.linux.template_release.x86_64.so | c++filt | grep -qE ' U (YG|hb_|ma_|rive::|Sk[A-Z])'
python3 -c "import ctypes,sys; ctypes.CDLL(sys.argv[1], ctypes.RTLD_NOW)" demo/bin/librive.linux.template_release.x86_64.so
grep -rn "rivestd\|skia/dependencies/skia\|_NOEXCEPT" src/ | wc -l   # 0
```

(`grep -c … # 0` lines mean "count must be 0"; `grep -c` exits 1 in that case, so scripted gates use `! grep -q`.)

WP9 (G4):

```bash
godot --headless --path demo --import
godot --headless --fixed-fps 60 --path demo --script smoke_test.gd 2>&1 | tee "$SCRATCH/rive-smoke.log"; test ${PIPESTATUS[0]} -eq 0
! grep -E "ERROR:|SCRIPT ERROR:|\[Rive\] .*(Failed|Unable)" "$SCRATCH/rive-smoke.log"
```

WP10 (part of G4): editor checklist in `05` plus a screenshot attached to the PR.

WP11 (G5): the WP3/WP4/WP7/WP8/WP9/WP10 commands with `--platform=macos --arch=arm64` (or universal per N2), plus the `file`, demangled `nm -u`, `dlopen` probe, and `otool -L` checks from `05`.

## Integration and regression gates

- **Integration gate (Linux):** G0 → G1 → G2 → G3 → G4 in order; each gate's command list must pass at least once from clean build outputs before opening the PR: `python3 build/build.py --clean --platform=linux --target=debug`, the same for `release`, `rm -rf build/rive/out demo/.godot`, then rebuild. Keep `build/deps/` (the Skia and dependency checkouts) to avoid a multi-GB re-fetch; a full `git clean -xfd build/` is only required if `build_skia.py` or the premake wrapper changed.
- **Regression gate:** the WP9 smoke test enumerates every `.riv` in `demo/examples/` and must report 50 successful imports. The editor check (WP10) covers issues #1 (crash on changing file path) and #12 (no render after resize) from git history.
- **Cross-platform gate:** G5 on macOS before merge; decision N2 (arm64-only vs universal) is confirmed with the user before WP3 runs on the Mac. If no Mac is available when the Linux work is done, open the PR with G5 marked pending and keep the old macOS binaries in place with a README note that they were built against the previous pin; merging with G5 pending is the user's call (non-blocking decision N1 owner).

## Definition of done

All of the following are true on `main` after merge:

1. `.gitmodules` URL is `https://github.com/rive-app/rive-runtime.git` and `thirdparty/rive-cpp` is at `45d4d01dfd1fe70d3f9e73764538c16f63a04d07`.
2. `build/skia/build_skia.py`, `build/rive/premake5.lua`, and the rewritten `build/build.py` exist; `build/build.py --platform=linux` and `--platform=macos --arch=arm64` succeed for both targets.
3. `src/` contains no `rivestd`, no `_NOEXCEPT`, and no `skia/dependencies/skia` include; `RiveListener.has_type`, `RiveListener.CLICK`, and `RiveViewer.get_image` exist; count/find methods answer from the runtime (`03` §7.11).
4. `demo/rive.gdextension` lists Linux x86_64 and macOS entries; the `.so` files are git-ignored; the macOS frameworks are regenerated binaries with the architecture chosen in decision N2 (default arm64).
5. `demo/smoke_test.gd` passes headless (after `--import`, under `--fixed-fps 60`) on Linux and macOS with zero error lines, including the non-transparent-pixel check.
6. `README.md` matches the new build steps, prerequisites, platform claims, and verification command.
7. The `thirdparty/rive-cpp` gitlink equals `45d4d01dfd1fe70d3f9e73764538c16f63a04d07`; working-tree patches, if any, are applied only from `build/patches/rive-cpp/` by `build.py` and are listed in the PR; nothing is committed inside the submodule.
8. The WP10 editor visual check passed on Linux and macOS, with one screenshot per platform in the PR.

## Deferred work and follow-ups (not part of this plan)

- Fix `src/viewer_props.hpp`: `FIT::SCALE_DOWN = 9` vs hint string `ScaleDown:7`.
- macOS universal binaries (needs Skia built twice and `lipo`, plus `--arch=universal` for rive and `arch=universal` for scons).
- Windows, Android, iOS, Web targets (README "Contributing" list).
- Decide whether to commit Linux `.so` binaries (currently ignored) or move all binaries out of git (non-blocking decision N1).
- Expose newer runtime features (view models/data binding, text runs, events, audio control, the remaining 12 `ListenerType` values).
- Evaluate migrating from the Skia renderer to `rive_pls_renderer`; upstream no longer CI-builds the Skia renderer, so this port carries maintenance risk.
- Update the `godot-cpp` submodule (4.1.1 → 4.6) and raise `compatibility_minimum`.
