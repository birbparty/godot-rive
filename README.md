# Godot Rive

### An integration of Rive into Godot 4.1+ using GDExtension

> [!WARNING]
> This extension is in **alpha**. That means:
> * You may encounter some bugs
> * It's untested on many platforms
> * Most features are implemented, but the API may change a little

This extensions adds [Rive](https://rive.app) support to Godot 4.

It makes use of the following third-party libraries:
- [`rive-runtime`](https://github.com/rive-app/rive-runtime) at `runtime-v0.1.384`
- [`rive-app/skia`](https://github.com/rive-app/skia) at `bae2881` (fetched by the build script)

## Table of Contents

1. [Features](#features)
2. [Building](#building)
3. [Installation](#installation)
4. [Roadmap](#roadmap)
5. [Contributing](#contributing)
6. [Screenshots](#screenshots)

## Features

* Load `.riv` files (artboards, animations, and state machines)
* Listen for input events
* Change state machine properties in-editor and in code
* Robust API for runtime interaction
* Optimized for Godot

## Building

The following must be installed:
- Python 3
- [git](https://git-scm.com/)
- [SCons](https://scons.org/)
- [Ninja](https://ninja-build.org/)
- Clang 15 or newer (Xcode Command Line Tools on macOS)

Build from the repository root. The first run clones Skia and its dependencies and bootstraps Premake, so it is a large download.
The build also applies the checked-in compatibility patches under `build/patches/` without changing either submodule pin.

```bash
python3 build/build.py --platform=linux --target=debug
python3 build/build.py --platform=linux --target=release

# On an Apple Silicon Mac:
python3 build/build.py --platform=macos --arch=arm64 --target=debug
python3 build/build.py --platform=macos --arch=arm64 --target=release
```

To see the available options, run:
```bash
python3 build/build.py --help
```

### Verifying

After building, import the extension and run the headless smoke test:

```bash
godot --headless --path demo --import
godot --headless --fixed-fps 60 --path demo --script smoke_test.gd 2>&1 | tee /tmp/rive-smoke.log
test ${PIPESTATUS[0]} -eq 0 && ! grep -E "ERROR:|SCRIPT ERROR:|\[Rive\] .*(Failed|Unable)" /tmp/rive-smoke.log
```

## Installation

Linux binaries must currently be built locally. The committed macOS frameworks are legacy universal binaries built against the previous runtime pin; rebuild them as arm64 before shipping this update.

1. Copy `demo/bin/`, `demo/icons/`, and `demo/rive.gdextension` to your project folder
2. Update the paths in `rive.gdextension` to match your project folder structure

## Roadmap
- [x] Load `.riv` files
- [x] Run and play Rive animations
- [x] Raster image support
- [x] Input events (hover, pressed, etc.)
- [x] Alignment & size exported properties
- [x] Multiple scenes/artboards
- [x] Dynamic exported properties based on state machine
- [x] API for interaction during runtime
- [x] Add error handling
- [x] Add signals for event listeners (hover, pressed, etc)
- [x] Disable/enable event listeners (hover, pressed, etc) in API and editor
- [x] Optimization
- [x] Static editor preview
- [x] Animated editor preview
- [ ] Add reset button
- [ ] `.riv` ResourceLoader (thumbnails)
- [x] Linux x86_64 and arm64 support
- [ ] Any missing features

## Contributing

Help would be MUCH appreciated testing and/or building for the following platforms:
* Windows
* Android
* iOS
* Web

Feel free to contribute bug fixes (see open issues), documentation, or features as well.

## Screenshots

![In-editor screenshot](screenshots/screenshot_1.png)
