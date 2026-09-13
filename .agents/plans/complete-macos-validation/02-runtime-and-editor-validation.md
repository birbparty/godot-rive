# Runtime and editor validation

## WP4: Run debug and release headless smoke gates

### Goal and prerequisite state

Prove that each framework works inside Godot 4.6.3, not only through the dynamic loader. WP2 and WP3 must pass.

### Repository evidence

- `demo/smoke_test.gd` expects 50 `.riv` files and returns nonzero for any recorded failure.
- Godot writes extension discovery state under ignored `demo/.godot/` during `--import`.
- `demo/rive.gdextension` maps the editor/debug executable to `macos.debug`; testing the release payload with the editor executable therefore needs a temporary local remap.

### Debug procedure

```bash
godot --headless --path demo --import
set -o pipefail
godot --headless --fixed-fps 60 --path demo --script smoke_test.gd 2>&1 | tee "$VALIDATION_DIR/rive-smoke-macos-debug.log"
test $? -eq 0
! grep -E "ERROR:|SCRIPT ERROR:|\[Rive\] .*(Failed|Unable)" "$VALIDATION_DIR/rive-smoke-macos-debug.log"
```

`VALIDATION_DIR` is a task-specific temporary directory created with `mktemp -d`; it is not committed.

### Release procedure

1. Save a temporary copy of `demo/rive.gdextension` inside `VALIDATION_DIR`.
2. Change only the local `macos.debug` value to `bin/librive.macos.template_release.framework`.
3. Remove `demo/.godot/`, rerun `--import`, and run the same fixed-FPS smoke command into `rive-smoke-macos-release.log`.
4. Restore `demo/rive.gdextension` from the saved copy immediately, even when the smoke command fails.
5. Verify `git diff --exit-code -- demo/rive.gdextension`.

The implementation should use a shell cleanup trap or equivalent structured cleanup so interruption cannot leave the descriptor remapped.

### Acceptance criteria (G3)

- Each run reports `Smoke test: 50 files, 0 failure(s)`.
- Each command pipeline returns the Godot exit status, not `tee`'s status.
- Neither log contains the specified Godot/Rive error patterns.
- Debug and release logs are retained in `VALIDATION_DIR` for final reporting.
- `demo/rive.gdextension` matches `HEAD` after the release run.

If the smoke script itself fails because of a test defect, make the smallest correction under `demo/smoke_test.gd`, rerun both configurations, and include that correction in final scope. Do not weaken the 50-file, frame-advance, input, listener, or raster assertions.

## WP5: Run the macOS editor/runtime interaction gate

### Goal

Exercise behavior that headless validation cannot prove and capture evidence of the macOS run.

### Procedure

1. Restore the debug descriptor and import state.
2. Open `demo/main.tscn` in the Godot editor and confirm its preview animates, then run it for steps 5–7.
3. Open and run `demo/demo_2d.tscn` for step 8.
4. Open and run `demo/demo_control.tscn` for step 9.
5. In `main.tscn`, hover into and out of `GridContainer/RiveViewer1` (`joystick.riv`) and require `Property hovered changed!` output for both transitions. Establish its authored baseline response, then press, drag, and release inside it and require visible pointer response without prescribing a post-release state.
6. In `main.tscn`, resize the running window from 1152×648 to 900×600 and back to 1152×648. Require all six viewers to remain visible and animated after each resize.
7. In the editor inspector, record `GridContainer/RiveViewer2`'s original `ghost.riv`, `artboard = 0`, `scene = 0`, and `animation = -1` values. Change it to the repository's known meteor configuration: `file_path = meteor.riv`, `artboard = 0`, `scene = -1`, `animation = 0`. Changing `file_path` resets the artboard selector, so select `artboard = 0` before the scene/animation values. Verify meteor animation renders, then restore all four ghost values in the same order and verify the ghost state machine renders without a crash.
8. Stop `main.tscn`, run `demo_2d.tscn`, then return to `main.tscn`. Require `tape.riv` to animate in 2D and all six main-scene viewers to resume animation; this is the Godot scene-switch oracle, not a Rive state-machine index change.
9. Run `demo_control.tscn`. Establish the authored asset's baseline response, then set the `Rooms` slider to 3 and 6. Require two visibly distinct, valid house states without assuming that the numeric input maps literally to a count of visible rooms.
10. Capture readable before/after evidence as `screenshots/macos-validation.png` (**new**, under existing `screenshots/`). A single composite image may contain multiple labeled captures; otherwise use the final six-room view plus record the complete observation checklist in the PR.
11. Inspect the screenshot before accepting the gate. Record each observation and the output-panel state in the final report and PR.

### Acceptance criteria (G4)

- All three scenes render and animate.
- The 1152×648 → 900×600 → 1152×648 resize, `main.tscn` ↔ `demo_2d.tscn` switch, and `ghost.riv` → `meteor.riv` → `ghost.riv` replacement preserve rendering and animation.
- Slider values 3 and 6 show distinct valid states; joystick hover emits both property transitions; joystick press-drag-release causes the baseline-confirmed visible pointer response without errors.
- The Godot output contains no `[Rive]` failure lines, script errors, or crashes.
- `screenshots/macos-validation.png` exists, is readable, and shows rendered Rive content on macOS; the PR checklist supplies temporal evidence that a still image cannot carry.

This is a visual gate. If automation cannot reliably perform or observe an interaction, stop and request the smallest human action instead of claiming it passed.
