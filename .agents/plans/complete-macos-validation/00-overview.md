# Complete macOS validation for the Rive runtime upgrade

**Status: Ready.** This plan covers the remaining macOS validation and artifact refresh on branch `update`. Planning has not performed the work described below. The runtime/Skia upgrade itself already exists at commit `96dba5a`. Two independent reviews and one adversarial review completed; accepted findings are incorporated into the work packages and gates.

## Application context

```json
{
  "application_context": {
    "has_active_users": false,
    "backward_compatibility_required": false,
    "feature_flags": "not-applicable",
    "confirmation_digest": "ece4c26d308d376289932b32df4b766b37f213bdf3218f3ad8d2b3d6ae6bf95e",
    "confirmed_at": "2026-09-13T00:01:27Z"
  }
}
```

There is no rollout or migration requirement. The refreshed macOS frameworks may become arm64-only, as the existing upgrade plan specifies. Rollback is a revert of the framework and README commit; generated dependency trees remain untracked and can be rebuilt.

## Change type and affected areas

Change type: **platform validation, generated-binary refresh, and release documentation correction**.

| Area | Existing surface |
| --- | --- |
| Build orchestration | `build/build.py`, `build/skia/build_skia.py`, `build/rive/premake5.lua`, `build/SConstruct` |
| Runtime packaging | `demo/bin/librive.macos.template_{debug,release}.framework/`, `demo/rive.gdextension` |
| Automated validation | `demo/smoke_test.gd`, `demo/examples/` |
| Manual validation | `demo/main.tscn`, `demo/demo_2d.tscn`, `demo/demo_control.tscn` |
| User documentation | `README.md` |

## Requested outcome

Read the Beans handoff `godot-rive-g8cn`, plan the remaining work, independently review and revise the plan, then implement it.

Success means:

1. Clean macOS arm64 debug and release builds complete from the upgraded sources on branch `update`.
2. Both produced framework executables are arm64 Mach-O files, load with `RTLD_NOW`, contain `rive_library_init`, have no unresolved Rive/Skia/Yoga/HarfBuzz/miniaudio symbols, and link the expected Apple frameworks.
3. Debug and release each pass the 50-file Godot headless smoke test at fixed 60 FPS with no Godot/Rive error lines, using a zsh-safe exit-status check.
4. `main.tscn`, `demo_2d.tscn`, and `demo_control.tscn` render and react correctly in the macOS editor/runtime checks, including resize, file change, scene switch, slider, hover, and click interactions.
5. The two tracked macOS framework executables are replaced by the validated arm64 builds.
6. `README.md` no longer calls the committed frameworks legacy and accurately states their architecture and validation commands.
7. The superproject is free of unintended changes; both submodules have no tracked working-tree modifications; `git diff --check` passes.
8. The validated change is committed, pushed to `origin/update`, and represented by a draft pull request containing smoke results and durable screenshot evidence.

## Scope

In scope:

- Initialize the pinned `godot-cpp` and `thirdparty/rive-cpp` submodules.
- Install or otherwise provide SCons without changing repository dependency declarations.
- Clean and rebuild Skia, Rive, and the extension for macOS arm64 in debug and release modes.
- Fix defects in the upgrade implementation only when they block a specified macOS gate.
- Run automated binary and Godot smoke validation for both configurations.
- Run the macOS editor/runtime interaction gate and add `screenshots/macos-validation.png` (**new**, under existing `screenshots/`) as durable pull-request evidence.
- Replace the tracked framework executables and correct `README.md`.
- Commit the bounded result, run push preflight, push `update`, and create or update a draft pull request with the validation evidence.

Out of scope:

- Native Linux x86_64 validation. It remains an explicit follow-up and prevents claiming that every upgrade-platform gate is complete unless the user waives it.
- macOS x86_64 or universal frameworks.
- New runtime features, Godot API redesign, dependency repinning, or a `godot-cpp` update.
- Beans issue/handoff mutation. The handoff is source evidence; completing the code delivery does not authorize changing hub records.

## Repository-grounded findings

- `origin/update` and local `update` point at `96dba5a`, the completed Linux implementation named by the handoff.
- `godot-cpp` is pinned at `c370f0f...` and `thirdparty/rive-cpp` at `45d4d01...`; both were uninitialized at planning start.
- The host is Apple Silicon macOS 26.6.2. Godot is 4.6.3, Apple clang is 17.0.0, Ninja is 1.13.0, Python is 3.14.5, and Xcode is selected. SCons is missing.
- `build/build.py` applies the checked-in `godot-cpp` compatibility patch before SCons and supports only arm64 for macOS.
- `build/skia/build_skia.py` uses one `out/<target>` directory per configuration, pins `rive-app/skia@bae2881`, disables GPU paths, and forces `is_trivial_abi=false`.
- The checked-in debug and release framework executables are universal x86_64/arm64 legacy binaries. They are the only tracked payloads inside their framework directories.
- `demo/rive.gdextension` selects `macos.debug` or `macos.release` by framework directory. The editor binary normally exercises the debug entry, so release smoke validation requires a temporary local descriptor remap that must be restored.
- `demo/smoke_test.gd` recursively expects exactly 50 `.riv` files and verifies import, enumeration, input round-trip, 60-frame advancement, listener queries, and non-transparent raster output.
- Build cleanup intentionally restores tracked changes inside both submodules. Final hygiene must therefore run after the last build, without deleting the produced superproject frameworks.

## Key decisions

1. **Validate arm64-only artifacts.** This matches the implemented macOS constraint and avoids reopening the deferred universal-build design.
2. **Build debug and release from clean target-specific outputs.** Cached dependency checkouts may remain, but Skia/Rive output directories must be regenerated so old archives cannot satisfy the gate.
3. **Test release through a temporary `macos.debug` descriptor remap.** Restore `demo/rive.gdextension` immediately after the release test and verify it has no diff.
4. **Treat fixes as gate-driven.** Any source/build edit must explain a failed criterion and receive the same relevant rerun; unrelated cleanup remains out of scope.
5. **Deliver through the existing `update` branch.** Use a selective commit and preflight-verified push, then create or update a draft PR because the handoff explicitly requires both push and PR evidence.

## Change model

```text
legacy tracked universal frameworks
        |
        v
initialize exact submodule pins -> verify host tools -> clean debug build
        |                                      |
        |                                      v
        |                              debug binary + smoke gates
        v
clean release build ----------------> release binary + remapped smoke gates
                                               |
                                               v
                              editor/runtime interaction gate
                                               |
                                               v
                         keep arm64 frameworks + correct README + hygiene
```

## Risks, assumptions, and gates

- **G0 — Readiness:** stop if submodule commits differ from their gitlinks, required tools are unavailable, or SCons cannot run.
- **G1 — Debug build:** stop and diagnose if a clean debug build fails. Do not continue to release with modified build logic that has not passed debug.
- **G2 — Release build:** stop if a clean release build fails or either artifact is not arm64.
- **G3 — Automated runtime:** both configurations must pass `RTLD_NOW`, symbol/dependency inspection, and the 50-file smoke test.
- **G4 — Visual/runtime:** stop before artifact finalization if any scene fails to render, animate, resize, switch, or respond to the documented inputs.
- **G5 — Finalization:** only the plan, two framework executables, `README.md`, `screenshots/macos-validation.png` (**new**), and a narrowly justified blocker fix such as `build/skia/build_skia.py` may differ from `96dba5a`; submodules must have no tracked changes.
- **G6 — Delivery:** a selective commit is on `origin/update`, and a draft PR records both smoke summaries, binary checks, the visual checklist, screenshot, and the outstanding native Linux x86_64 gate.

Assumption: Homebrew SCons is acceptable as a machine-local prerequisite because the repository already documents SCons but does not pin it. If installation is unavailable, use an isolated Python environment and record the executable used.

Unresolved decisions: none blocking. The Linux x86_64 follow-up is intentionally outside this macOS plan and remains visible in the handoff.

## Document map

| File | Purpose |
| --- | --- |
| [01-build-and-binary-gates.md](01-build-and-binary-gates.md) | Prepare the Mac, produce clean artifacts, and inspect both binaries. |
| [02-runtime-and-editor-validation.md](02-runtime-and-editor-validation.md) | Exercise debug/release in Godot and complete the interaction gate. |
| [03-artifact-and-documentation-finalization.md](03-artifact-and-documentation-finalization.md) | Retain validated frameworks, correct documentation, prove hygiene, and deliver the branch. |
| [04-execution-handoff.md](04-execution-handoff.md) | Execute the work packages in dependency order with stop/go criteria. |
