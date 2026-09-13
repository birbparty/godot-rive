# 01 – Readiness, toolchain, and submodule move

Gate G0 lives here. Nothing in `02`–`05` starts until G0 is green.

## WP1: Toolchain readiness (Linux)

### Goal and prerequisite state

The machine can run upstream `build/build_rive.sh`, Skia's `gn`/`ninja` build, and `scons`. Prerequisite: none.

### Repository evidence

- Upstream `build/rive_build_config.lua` accepts only `--toolset=clang` or `--toolset=msc`; Linux builds therefore require `clang`/`clang++`.
- Upstream `build/build_rive.sh` bootstraps premake by cloning `premake-core` at `v5.0.0-beta7` and running `make -f Bootstrap.mak linux`; it needs `git`, `make`, and a C compiler.
- Skia's `tools/git-sync-deps` needs `python3`; `bin/fetch-gn` downloads a `gn` binary; the build needs `ninja`.
- `godot-cpp/tools/linux.py` exposes `use_llvm=yes` so the extension can be compiled with clang too.
- Verified present: `gcc`, `g++`, `python3` (3.12), `cmake`, `make`, `git`, `godot` (4.6.3). Verified missing: `clang`, `clang++`, `scons`, `ninja`, `premake5`, `gn`.

### Change surface

No repository files. Machine setup only. Record the exact commands used in the PR description, not in the repo.

Required tools and how the implementer resolves them (Ubuntu-family host inferred from `apt`-style paths; adjust if the distro differs):

| Tool | Resolution |
| --- | --- |
| `clang`, `clang++`, `lld` (optional) | distro package `clang` (version 15 or newer) |
| `scons` | `pipx install scons` or distro package `scons` (4.x) |
| `ninja` | distro package `ninja-build` |
| `premake5` | not installed by hand; `build_rive.sh` bootstraps it into `thirdparty/rive-cpp/build/dependencies/premake-core/bin/v5.0.0-beta7_release/` |
| `gn` | not installed by hand; `bin/fetch-gn` inside the Skia checkout |

### Acceptance criteria (gate G0)

All of the following succeed from the repository root:

```bash
clang++ --version          # prints a version >= 15
scons --version            # prints SCons 4.x
ninja --version
python3 --version          # 3.12.x
godot --version            # 4.6.x
```

G0 is a tool-version check only. The premake bootstrap is verified in `02` WP4 (first step), using this repository's own `build/rive/premake5.lua` and the WP4 environment. Do **not** bootstrap by running `build_rive.sh` inside `thirdparty/rive-cpp/tests/`: that generates upstream's whole tools workspace (PLS renderer, decoders, glfw, libpng) and clones their dependencies into the submodule working tree, because `build_rive.sh` runs premake before honouring `nobuild` (`build/build_rive.sh:386-391`).

### Risks and exclusions

- Distro `clang` older than 15 may reject C++17 features used upstream; if so, install from the LLVM apt repository. Record the version in the PR.
- macOS toolchain readiness is covered in `05` (WP11), because it runs on a different machine.

## WP2: Move the rive-cpp submodule and fix its URL

### Goal and prerequisite state

`thirdparty/rive-cpp` checks out upstream commit `45d4d01dfd1fe70d3f9e73764538c16f63a04d07` (tag `runtime-v0.1.384`), and `.gitmodules` names the canonical repository. Prerequisite: none (independent of WP1).

### Repository evidence

- `.gitmodules` currently:

  ```ini
  [submodule "thirdparty/rive-cpp"]
      path = thirdparty/rive-cpp
      url = https://github.com/rive-app/rive-cpp.git
  ```

- `https://github.com/rive-app/rive-cpp` returns an HTTP redirect to `https://github.com/rive-app/rive-runtime`. Git follows the redirect today; the plan removes the dependence on it.
- The submodule has no nested `.gitmodules` at the target commit (verified: `git show origin/main:.gitmodules` fails), so no recursive init is needed.
- The path stays `thirdparty/rive-cpp` to avoid touching every include path in `src/` and `build/`; the README already calls the library `rive-cpp`.

### Change surface

- `.gitmodules`: change `url` to `https://github.com/rive-app/rive-runtime.git`; add `ignore = untracked` so the premake bootstrap files that upstream does not git-ignore (`build/dependencies/`) do not mark the submodule as modified. Keep `path`.
- `thirdparty/rive-cpp` gitlink: `45d4d01dfd1fe70d3f9e73764538c16f63a04d07`.

Procedure (edit `.gitmodules` first so `sync` copies the new URL into `.git/config`):

```bash
git config -f .gitmodules submodule.thirdparty/rive-cpp.url https://github.com/rive-app/rive-runtime.git
git config -f .gitmodules submodule.thirdparty/rive-cpp.ignore untracked
git submodule sync thirdparty/rive-cpp
git -C thirdparty/rive-cpp fetch origin
git -C thirdparty/rive-cpp checkout 45d4d01dfd1fe70d3f9e73764538c16f63a04d07
git add .gitmodules thirdparty/rive-cpp
```

### Intended behavior and invariants

- `git submodule status` shows `45d4d01d…` with no `+`/`-` prefix after `git submodule update --init`.
- `thirdparty/rive-cpp/.rive_head` reads `2505c4bb9c0a60479c26eced62390c1ecfd44329` (verified content at the target commit; this is upstream's internal monorepo pointer, informational only).
- The submodule working tree will later contain untracked, upstream-unignored files created by the build (`build/dependencies/premake-core/`). With `ignore = untracked` in `.gitmodules`, default `git status` stays quiet about them. If a patch from `build/patches/rive-cpp/` is applied (`02` WP4), `git status` reports `modified: thirdparty/rive-cpp (modified content)`; that is expected and the gitlink must still point at `45d4d01d`. Do **not** commit anything inside the submodule and do not commit a changed gitlink.

### Acceptance criteria

```bash
git submodule status thirdparty/rive-cpp      # " 45d4d01dfd1fe70d3f9e73764538c16f63a04d07 thirdparty/rive-cpp (runtime-v0.1.384)"
git config -f .gitmodules submodule.thirdparty/rive-cpp.url      # https://github.com/rive-app/rive-runtime.git
git config -f .gitmodules submodule.thirdparty/rive-cpp.ignore   # untracked
test -f thirdparty/rive-cpp/build/build_rive.sh && test -f thirdparty/rive-cpp/skia/renderer/premake5_v2.lua
```

### Risks and exclusions

- The `godot-cpp` submodule is **not** moved (non-goal in `00`).
- Do not run `git submodule update --remote` later; it would drift the pin.
