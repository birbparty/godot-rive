dofile("rive_build_config.lua")

RIVE_RUNTIME_DIR = path.getabsolute("../../thirdparty/rive-cpp")
dofile(path.join(RIVE_RUNTIME_DIR, "premake5_v2.lua"))
dofile(path.join(RIVE_RUNTIME_DIR, "skia/renderer/premake5_v2.lua"))
