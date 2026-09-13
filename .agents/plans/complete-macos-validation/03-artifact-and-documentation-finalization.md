# Artifact and documentation finalization

## WP6: Retain only validated framework payloads

### Goal and prerequisite state

Make the two successful arm64 artifacts the tracked macOS deliverables. G3 and G4 must pass.

### Exact change surface

- Replace the existing tracked executable in `demo/bin/librive.macos.template_debug.framework/`.
- Replace the existing tracked executable in `demo/bin/librive.macos.template_release.framework/`.
- Do not add generated Skia/Rive outputs, smoke logs, `.godot/`, framework metadata not produced by the existing build, or submodule working-tree changes. The only screenshot added is `screenshots/macos-validation.png` (**new**).

### Acceptance criteria

- `git diff --numstat` shows binary replacements at both exact framework paths.
- Re-running WP3 against the retained paths still passes.
- The hashes in the final report match the retained files.

## WP7: Correct README claims

### Goal

Document what was actually built and validated without overstating Linux completion.

### Change surface: `README.md`

- Replace the installation warning that calls the committed macOS frameworks legacy universal binaries.
- State that committed debug and release frameworks are arm64 and were rebuilt against `runtime-v0.1.384`.
- Keep Linux binaries as locally built artifacts. Do not claim native Linux x86_64 validation from this Mac.
- Replace the Bash-only `${PIPESTATUS[0]}` example with the zsh-safe `set -o pipefail` plus immediate `$?` check used in WP4. Retain build and smoke commands only if they were executed successfully as written. If the actual Godot executable required an application-bundle path, document both that path and the `godot`-on-`PATH` form without making PATH modification a repository requirement.

### Acceptance criteria

- No `legacy universal` or universal-availability claim remains.
- Architecture and runtime pin match `file` output and `.gitmodules`/gitlink evidence.
- Documentation does not imply that the pending native Linux x86_64 gate passed.

## WP8: Restore submodules and prove repository hygiene

### Goal

Remove build-induced checkout changes without removing the two superproject framework artifacts.

### Procedure

1. Restore tracked files inside `godot-cpp` and `thirdparty/rive-cpp` using their own Git worktrees. Preserve upstream-managed dependency caches only when ignored/untracked.
2. Verify both submodule HEADs still equal the superproject gitlinks.
3. Remove `demo/.godot/` or leave it ignored; confirm it does not appear in `git status`.
4. Run Python syntax checks and ask Godot to parse/open the project files exercised by the implementation.
5. Run `git diff --check` and inspect the complete diff against `96dba5a`.

### Acceptance criteria (G5)

```bash
git -C godot-cpp status --short
git -C thirdparty/rive-cpp status --short
test "$(git -C godot-cpp rev-parse HEAD)" = c370f0f24a6e4ce767e21673731838f1affc45fb
test "$(git -C thirdparty/rive-cpp rev-parse HEAD)" = 45d4d01dfd1fe70d3f9e73764538c16f63a04d07
python3 -m py_compile build/build.py build/skia/build_skia.py
godot --headless --path demo --editor --quit
git diff --exit-code -- demo/rive.gdextension
git diff --check
git diff --name-only 96dba5a
```

The two submodule status commands must print nothing. Compare `git diff --name-only 96dba5a` to the allowlist: `.agents/plans/complete-macos-validation/*.md`, both exact framework executables, `README.md`, `screenshots/macos-validation.png`, `build/skia/build_skia.py` for the macOS 26 SDK zlib gate fix, and `demo/project.godot` for the confirmed Godot parallel multi-font import crash mitigation. Any other path requires a documented failed gate, correction rationale, and full downstream rerun.

## WP9: Commit, push, and create or update the draft PR

### Goal and prerequisite state

Deliver the validated Mac continuation on branch `update`, as required by the Beans handoff. G5 must pass.

### Procedure

1. Run the repository `preflight` workflow before any push. Stop on missing authentication, remote mismatch, insufficient scopes, or lack of push access.
2. Fetch `origin` immediately before staging and require `git rev-parse origin/update` to equal the validated starting SHA `96dba5a235c9aa251b435c8934787dd68fed216a`. If it differs, stop; integrate deliberately, then rebuild and rerun every affected gate before delivery.
3. Selectively stage only the G5 allowlist plus documented gate-driven fixes.
4. Commit the Mac frameworks, validation screenshot, README correction, and reviewed plan as one bounded continuation commit.
5. Push `update` to `origin` without force.
6. If no PR exists for `update`, create a draft PR targeting `main`. Otherwise update the existing PR body.
7. Record tool versions, clean debug/release build log names and results, artifact hashes, WP3 checks, both 50-file smoke summaries, the manual checklist, and the screenshot link. State that native Linux x86_64 validation remains outstanding.

### Acceptance criteria (G6)

- `git rev-parse HEAD` names the reported commit.
- `git rev-parse origin/update` equals `HEAD` after a fetch.
- `gh pr view --json url,isDraft,headRefName,baseRefName` returns the reported URL, `isDraft: true`, head `update`, and base `main`.
- The PR body contains the two smoke summaries, binary validation result, every manual observation, screenshot, and explicit Linux x86_64 pending status.
- `git status --short --branch` is clean and not ahead of `origin/update`.

## Rollback and recovery

- Before committing, restore either framework with `git restore --source=96dba5a -- <exact-framework-executable>`.
- After committing, revert the final macOS artifact/documentation commit as one unit and push the revert only with explicit user direction.
- If a build is interrupted, restore both submodules before retrying, then start the affected target at WP2's clean command.
- Never use a broad destructive cleanup at repository root. Delete only explicit generated directories owned by `build.py` or ignored Godot import state.
