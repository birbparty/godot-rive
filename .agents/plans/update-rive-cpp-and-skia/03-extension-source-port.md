# 03 – Extension source port to runtime-v0.1.384

Gate G3 (the extension compiles and links on Linux) lives here together with `04`. Prerequisite: G2.

Every edit below is anchored to a verified line in the current tree and to a verified upstream declaration at commit `45d4d01d`. Edits are grouped per file. Everything not listed compiles unchanged (finding 9 in `00`).

## WP7: Source port

### Goal and prerequisite state

`src/` compiles against `thirdparty/rive-cpp/include` at the new pin with `WITH_RIVE_TEXT`, `WITH_RIVE_LAYOUT`, `WITH_RIVE_AUDIO` defined, and links against the six rive archives plus `libskia.a`. Prerequisite: G2 outputs exist so compile errors are real.

### 7.1 `src/skia_instance.hpp` — `rivestd` removal

Evidence: upstream commit `9ea0fb6a` ("Bump core runtime to C++17 … remove the rivestd polyfills"); `include/utils/rive_std.hpp` no longer exists; no `rivestd` symbol remains under `include/` or `src/` upstream.

| Line | Current | Change |
| --- | --- | --- |
| 26 | `Ptr<SkiaFactory> factory = rivestd::make_unique<SkiaFactory>();` | `std::make_unique<SkiaFactory>()` |
| 69 | `renderer = rivestd::make_unique<SkiaRenderer>(surface->getCanvas());` | `std::make_unique<SkiaRenderer>(...)` |

Add `#include <memory>` at the top of the file (currently relies on transitive includes).

### 7.2 `src/utils/read_rive_file.hpp` and `src/api/rive_file.hpp` — `File::import` returns `rcp<File>`

Evidence: `include/rive/file.hpp:121-133` (`static rcp<File> import(Span<const uint8_t>, Factory*, ImportResult* = nullptr, FileAssetLoader* = nullptr, ScriptingVM* = nullptr)`); `include/rive/refcnt.hpp` exists; `ArtboardInstance::file(rcp<const File>)` shows instances now retain their `File`.

`src/utils/read_rive_file.hpp`:

- Line 38: `Ptr<File> file = File::import(bytes, factory, &result);` becomes `rive::rcp<rive::File> file = File::import(bytes, factory, &result);`
- Return type of `read_rive_file` (line 26) becomes `rive::rcp<rive::File>`; the `return nullptr;` on line 45 stays valid (`rcp` is constructible from `nullptr`).
- Line 35: `Span<const uint8_t> bytes = Span(const_cast<uint8_t *>(_bytes.ptr()), length);` — keep; `Span(T*, size_t)` is unchanged and the deduction guide still yields `Span<uint8_t>`, convertible to `Span<const uint8_t>`. If the compiler rejects the conversion, write `Span<const uint8_t> bytes(_bytes.ptr(), length);`.
- Add `#include <rive/refcnt.hpp>`.

`src/api/rive_file.hpp`:

- Line 32: `Ptr<rive::File> file;` becomes `rive::rcp<rive::File> file;`
- Line 77: `static Ref<RiveFile> MakeRef(Ptr<rive::File> file_value, String path_value)` takes `rive::rcp<rive::File>`; line 80 `obj->file = std::move(file_value);` stays.
- Line 87: `Ptr<rive::File> file = read_rive_file(path, factory);` becomes `auto file = read_rive_file(path, factory);`
- Lines 36-40 (`file.get()`, `file->artboardAt(index)`, `file->artboardNameAt(index)`, `file->artboardCount()`): unchanged; `rcp` provides `get()` and `->`.
- `RiveArtboard::file` (`src/api/rive_artboard.hpp:33`, `rive::File *file`) stays a raw pointer; the `RiveFile` that owns the `rcp` outlives every `RiveArtboard` it vends because `Instances<RiveArtboard>` is a member of `RiveFile`. No change.

`src/utils/memory.hpp` `nullify(Ptr<T>)` is unused for `File`; no change.

### 7.3 `src/api/rive_listener.hpp` — listener type query

Evidence: at the pin, `include/rive/animation/state_machine_listener.hpp:26` declared `ListenerType listenerType() const`; upstream `main` has it commented out (lines 23-26) and instead offers `virtual bool hasListener(ListenerType) const` and `bool hasListeners(Span<const ListenerType>) const`. `ListenerType` is declared in `include/rive/listener_type.hpp` at both revisions (the pin's `state_machine_listener.hpp:4` includes it), now with values `enter=0, exit=1, down=2, up=3, move=4, event=5, click=6, componentProvided=7, textInput=8, dragStart=9, dragEnd=10, viewModel=11, drag=12, focus=13, blur=14, keyboard=15, semanticAction=16, gamepad=17`.

Changes:

1. Add `#include <rive/listener_type.hpp>` (explicit; do not rely on transitive includes).
2. Replace `get_type()` (lines 81-83):

   ```cpp
   // Priority order preserves the old single-type semantics for the common cases.
   static constexpr rive::ListenerType kQueryOrder[] = {
       rive::ListenerType::down, rive::ListenerType::up, rive::ListenerType::click,
       rive::ListenerType::enter, rive::ListenerType::exit, rive::ListenerType::move };
   int get_type() const {
       if (listener)
           for (auto t : kQueryOrder) if (listener->hasListener(t)) return (int)t;
       return -1;  // none of the bound types; has_type() still answers for any raw ListenerType value
   }
   bool has_type(int type) const { return listener && listener->hasListener((rive::ListenerType)type); }
   ```

3. Bind `has_type` in `_bind_methods` (`D_METHOD("has_type", "type")`). Add an integer constant `CLICK = (int)rive::ListenerType::click` next to the existing five constants so `has_type(RiveListener.CLICK)` is expressible. Do not bind the remaining 12 values (non-goal: new features).
4. `get_type_string()` (lines 85-99): add a `case rive::ListenerType::click: return "RiveListenerType::CLICK";` and return `"RiveListenerType::NONE"` when `get_type()` is `-1`.

Behavior note for the PR description: `get_type()` was a single value; now it is the highest-priority matching bound type, or `-1` when the listener only has types the extension does not bind (`event`, `viewModel`, and the rest of the 18), and `has_type()` is the exact query. `get_type_string()` returns `"RiveListenerType::NONE"` for `-1`. This is an accepted API behavior change (backward compatibility not required).

### 7.4 `src/api/rive_scene.hpp` — verify only

- Lines 185-195 (`pointerMove/pointerDown/pointerUp`): upstream returns `HitResult` and adds defaulted parameters; call sites discard the result. No edit. If the compiler warns with `-Werror=unused-result` (it will not; `[[nodiscard]]` is not present on these declarations at `include/rive/animation/state_machine_instance.hpp:182-186`), cast to `(void)`.
- Lines 45-49 (`listeners` lambda) uses `scene->stateMachine()->inputCount()` as the upper bound for listener indices; `listenerCount()` exists at both revisions. Fixed in §7.11.

### 7.5 `src/rive_instance.hpp` — verify only

- Line 54 `rive::computeAlignment(fit, alignment, AABB, bounds)`: upstream adds a defaulted `scaleFactor`; no edit.
- Line 80 `ab->artboard->advance(delta)`: upstream adds defaulted `AdvanceFlags`; no edit.
- Line 78 `sm->scene->advanceAndApply(delta)`, line 79 `anim->animation->advanceAndApply(delta)`: present (`state_machine_instance.hpp:173`, `linear_animation_instance.hpp:139`). No edit.

### 7.6 `src/api/rive_artboard.hpp` — verify only

- Lines 212-213 `hasDirt(ComponentDirt::Components)` / `addDirt(ComponentDirt::Components, false)`: `include/rive/component.hpp:197-198` and `component_dirt.hpp:21`. No edit.
- Line 176 `worldTransform().decompose()`: `mat2d.hpp:79`. No edit.

### 7.7 `src/viewer_props.hpp` — verify only

- `rive::Fit` gained `layout` (`include/rive/layout.hpp:5-14`); the `convert(FIT)` switch has a `default:` branch, so no `-Wswitch` error. No edit. Note the pre-existing mismatch between `enum FIT { … SCALE_DOWN = 9 }` and the hint string `ScaleDown:7`; deferred (see `06`).

### 7.8 Includes that must resolve with the new include roots

The extension includes Skia as `<skia/dependencies/skia/include/core/SkBitmap.h>` relative to the rive-cpp root (`src/rive_viewer_base.h:26-28`, `src/rive_instance.hpp:20-22`, `src/skia_instance.hpp:8-10`). After WP3 Skia lives at `build/deps/skia`, not `thirdparty/rive-cpp/skia/dependencies/skia`. Change these nine include lines to `<include/core/SkBitmap.h>`, `<include/core/SkCanvas.h>`, `<include/core/SkSurface.h>` and put `build/deps/skia` on `CPPPATH` (`04`). Upstream's own renderer headers include Skia the same way (`skia/renderer/include/to_skia.hpp:12-14` use `"include/core/SkPathTypes.h"`).

The `<skia/renderer/include/skia_factory.hpp>` and `<skia/renderer/include/skia_renderer.hpp>` includes resolve relative to `thirdparty/rive-cpp` (already on `CPPPATH`); unchanged.

### 7.9 `src/rive_exceptions.hpp` — libc++-only macro

Evidence: `src/rive_exceptions.hpp:35` and `:43` write `godot::String get_caller() const _NOEXCEPT {`. `_NOEXCEPT` is defined by libc++'s `<__config>` only; `grep -rl "define _NOEXCEPT" /usr/include/c++/` finds nothing with libstdc++ 13 on this machine. Replace both occurrences with `noexcept`. This is why the extension has only ever compiled on macOS.

### 7.10 `src/rive_viewer_base.h` — expose the rendered raster for verification

Evidence: `src/rive_viewer_base.h:55-56` hold `Ref<Image> image` and `Ref<ImageTexture> texture` privately; `RIVE_VIEWER_BIND` (`src/rive_viewer_base.h:190-216`) binds no accessor for either, so a script cannot prove that anything was drawn. Each frame writes pixels into the extension-owned `Image` in place (`src/rive_viewer_base.cpp:65` `image->set_data(...)`, `:208`) and then calls `texture->update(image)`. Under Godot's headless dummy rendering server, `texture_2d_initialize` stores a copy of the initial (blank) image and `texture_2d_update` is a no-op, so `ImageTexture::get_image()` stays transparent headless while the `Image` member is correct.

Change: add `Ref<Image> get_image() const { return image; }` to `RiveViewerBase` (public section, next to `get_elapsed_time`), add `RIVE_VIEWER_GET(Ref<Image>, image)` to `RIVE_VIEWER_WRAPPER`, and `BIND_GET(cls, image)` to `RIVE_VIEWER_BIND`. Returns `null` before the first processed frame; the returned `Image` is the live buffer (callers that want a snapshot call `duplicate()`). Used by the smoke test in `05` (pixel check). Do not bind the `ImageTexture`.

### 7.11 Count, find, and list methods must not depend on the inspector having run

Evidence: `RiveFile::get_artboard_count` (`src/api/rive_file.hpp:119-121`), `RiveArtboard::get_scene_count`/`get_animation_count` (`src/api/rive_artboard.hpp:141-147`), `RiveScene::get_input_count`/`get_listener_count` (`src/api/rive_scene.hpp:118-124`) return `Instances::get_size()`, the size of the instantiated map (`src/api/instances.hpp:71-73`); `find_*`, `get_*s`, and `get_*_names` iterate that map. The map is filled by `RiveInstance::instantiate()` (`src/rive_instance.hpp:105-118`), which only runs from `get_property_list` and `on_set` (`src/rive_viewer_base.cpp:114`, `:168`), that is, from the inspector. Setting `file_path` from a script fills nothing, so counts are 0 and `find_input("Rooms")` (used by `demo/demo_control.gd`) returns null outside the editor. The listeners cache lambda (`src/api/rive_scene.hpp:45-49`) also bounds indices by `stateMachine()->inputCount()` instead of `listenerCount()`.

Change (same files):

| Method | New implementation |
| --- | --- |
| `RiveFile::get_artboard_count` | `file ? (int)file->artboardCount() : 0` |
| `RiveArtboard::get_scene_count` / `get_animation_count` | `artboard ? (int)artboard->stateMachineCount() : 0` / `animationCount()` |
| `RiveScene::get_input_count` / `get_listener_count` | `scene ? (int)scene->inputCount() : 0` / `scene && scene->stateMachine() ? (int)scene->stateMachine()->listenerCount() : 0` |
| every `find_*`, `get_*s`, `get_*_names`, `_get_*_property_hint` | call the matching `_instantiate_*()` helper first (they already exist: `_instantiate_artboards`, `_instantiate_scenes`, `_instantiate_animations`, `_instantiate_inputs`; add `_instantiate_listeners`), then iterate the map |
| listeners lambda bound | `index >= scene->stateMachine()->listenerCount()` |

`Instances::get(index)` already instantiates on demand, so `get_artboard(i)` etc. are unchanged. The `_instantiate_*` helpers throw `RiveException` on a null instance; the callers above must catch and report exactly like `RiveInstance::instantiate()` does.

Acceptance: covered by the smoke test in `05` (counts match the runtime, `find_input` works from a script with no editor).

### Intended behavior and invariants after the port

- Loading, artboard/scene/animation enumeration, input get/set, mouse events, and rendering behave as before for the demo files.
- `RiveFile` keeps the only strong reference to `rive::File`; artboard instances hold an internal `rcp<const File>` upstream, so destroying `RiveFile` before its `RiveArtboard`s no longer dangles (an improvement, not a requirement).
- No new GDScript classes. Two new methods (`RiveListener.has_type`, `RiveViewer.get_image` / `RiveViewer2D.get_image`) and one new constant (`RiveListener.CLICK`). Count/find methods keep their names and now answer from the runtime.

### Tests and acceptance criteria (gate G3, together with `04`)

```bash
scons -C build platform=linux target=template_debug arch=x86_64 use_llvm=yes rive_out=out/debug skia_out=out/debug
test -f demo/bin/librive.linux.template_debug.x86_64.so
grep -rn "rivestd" src/ | wc -l        # 0
grep -rn "skia/dependencies/skia" src/ | wc -l   # 0
grep -rn "_NOEXCEPT" src/ | wc -l      # 0
```

Behavioral acceptance is in `05` (smoke test covers file import, enumeration, advance, input round-trip, listener `get_type`/`has_type`, and a non-transparent rendered raster via `get_image`).

### Risks, edge cases, exclusions

- `-Werror` is not enabled for the extension by godot-cpp; do not add it during the port.
- `String(errs.str().c_str())` in `read_rive_file.hpp:39` captures `std::cerr`; upstream import errors still print to `std::cerr` (unchanged mechanism). No edit.
- Do not add view-model, data-binding, text-run, or audio bindings (non-goals).
