# Execution handoff

Implementation starts only after two independent plan reviews and the required adversarial review are complete and accepted findings are incorporated into the plan.

## Dependency-ordered work packages

| Order | Package | Result | Prerequisite | Verification |
| --- | --- | --- | --- | --- |
| 1 | WP1 readiness | Exact pins and all Mac tools available | branch `update` at `96dba5a` | G0 commands in `01` |
| 2 | WP2 clean builds | Fresh arm64 debug and release frameworks | G0 | both build commands and `file` |
| 3 | WP3 binary gates | Both artifacts load and resolve dependencies | WP2 | `nm`, `ctypes`, `otool`, signing info |
| 4 | WP4 runtime gates | Debug and release each pass all 50 files | WP3 | fixed-FPS logs and restored descriptor |
| 5 | WP5 editor gate | Three scenes and interactions pass visually | WP4 | inspected screenshot and no error output |
| 6 | WP6 artifact retention | Validated payloads replace legacy binaries | WP5 | hashes and repeated WP3 |
| 7 | WP7 documentation | README matches shipped artifacts | WP6 | claim-to-evidence review |
| 8 | WP8 hygiene | Narrow diff and clean submodules | WP7 | G5 commands |
| 9 | WP9 delivery | Commit, push, and draft PR with evidence | G5 | G6 remote checks |

The packages are sequential because later acceptance depends on the exact produced framework files. Tool installation and initial submodule download may overlap operationally, but no build begins before both finish.

## Stop/go rules

- Do not test release by overwriting the debug framework. Remap only the descriptor and restore it through guaranteed cleanup.
- Do not retain a framework whose exact bytes did not pass its corresponding smoke and binary gates.
- Do not treat the screenshot as proof without also checking interaction behavior and output errors.
- Do not make an unrelated source cleanup while diagnosing a platform failure.
- Do not push before the preflight workflow passes, and never force-push `update`.

## Integration and regression gate

After WP8, run WP3 once more for both retained framework executables, then run the debug smoke gate once more with the committed descriptor. This final pass detects accidental artifact replacement or descriptor drift during cleanup/documentation.

## Definition of done

1. Both clean arm64 builds completed on this host from the exact submodule pins.
2. Both retained framework executables pass architecture, export, unresolved-symbol, dependency, and `RTLD_NOW` checks.
3. Both framework configurations pass the 50-file smoke gate with zero failures and error lines.
4. The three manual scenes and listed interactions pass, and the inspected macOS screenshot is committed at `screenshots/macos-validation.png`.
5. `README.md` describes the refreshed arm64 frameworks and does not overstate Linux validation.
6. Both submodule worktrees are clean at their pinned commits.
7. `git diff --check` and the final debug regression gate pass.
8. The final report names the artifact hashes, tool versions, smoke summaries, visual result, any gate-driven fixes, and the still-outstanding native Linux x86_64 validation.
9. The selective commit is present on `origin/update`, and the draft PR contains durable validation evidence.

## Deferred work

- Native Linux x86_64 clean build, headless smoke, and graphical editor validation from the original upgrade plan.
- macOS universal packaging.
