extends SceneTree

var failures: Array[String] = []


func fail(message: String) -> void:
	failures.append(message)
	push_error(message)


func find_riv_files(path: String) -> Array[String]:
	var files: Array[String] = []
	var directory := DirAccess.open(path)
	if directory == null:
		fail("cannot open %s" % path)
		return files
	directory.list_dir_begin()
	var entry := directory.get_next()
	while not entry.is_empty():
		var child := path.path_join(entry)
		if directory.current_is_dir():
			if entry != "." and entry != "..":
				files.append_array(find_riv_files(child))
		elif entry.get_extension().to_lower() == "riv":
			files.append(child)
		entry = directory.get_next()
	directory.list_dir_end()
	return files


func make_viewer(path: String) -> RiveViewer2D:
	var viewer := RiveViewer2D.new()
	root.add_child(viewer)
	viewer.set("size", Vector2(256, 256))
	viewer.set("file_path", path)
	return viewer


func _initialize() -> void:
	for registered_class in ["RiveViewer", "RiveViewer2D", "RiveFile", "RiveScene", "RiveInput", "RiveListener", "RiveAnimation", "RiveArtboard"]:
		if not ClassDB.class_exists(registered_class):
			fail("extension not loaded: missing %s; run 'godot --headless --path demo --import' first" % registered_class)
	if not failures.is_empty():
		quit(1)
		return

	var paths := find_riv_files("res://examples")
	paths.sort()
	var summary: Array[Dictionary] = []
	for path in paths:
		var viewer := make_viewer(path)
		await process_frame
		var file = viewer.call("get_file")
		if file == null or file.get_artboard_count() <= 0:
			fail("%s did not import an artboard" % path)
			viewer.queue_free()
			await process_frame
			continue
		var scene_count := 0
		var animation_count := 0
		for artboard_index in file.get_artboard_count():
			var artboard = file.get_artboard(artboard_index)
			if artboard == null:
				fail("%s artboard %d is null" % [path, artboard_index])
				continue
			scene_count += artboard.get_scene_count()
			animation_count += artboard.get_animation_count()
		summary.append({"file": path, "artboards": file.get_artboard_count(), "scenes": scene_count, "animations": animation_count})
		viewer.queue_free()
		await process_frame

	if paths.size() != 50:
		fail("expected 50 .riv files, found %d" % paths.size())

	var viewer := make_viewer("res://examples/house_resizing.riv")
	viewer.set("artboard", 0)
	viewer.set("scene", 0)
	await process_frame
	var scene = viewer.call("get_scene")
	if scene == null or scene.get_input_count() <= 0:
		fail("known state machine has no inputs")
	else:
		var round_trip := false
		for input_index in scene.get_input_count():
			var input = scene.get_input(input_index)
			if input.is_number():
				input.set_value(0.75)
				if abs(float(input.get_value()) - 0.75) > 0.00001:
					fail("numeric input did not round-trip")
				round_trip = true
				break
			if input.is_bool():
				var expected := not bool(input.get_value())
				input.set_value(expected)
				if bool(input.get_value()) != expected:
					fail("boolean input did not round-trip")
				round_trip = true
				break
		if not round_trip:
			fail("known state machine has no bool or numeric input")
		for listener in scene.get_listeners():
			var listener_type: int = listener.get_type()
			if listener_type != -1 and not listener.has_type(listener_type):
				fail("listener %s type query is inconsistent" % listener.get_name())

	var elapsed_before: float = viewer.call("get_elapsed_time")
	for frame_index in 60:
		await process_frame
	var elapsed_delta: float = viewer.call("get_elapsed_time") - elapsed_before
	if abs(elapsed_delta - 1.0) >= 0.05:
		fail("60 frames advanced by %.4f seconds instead of 1.0" % elapsed_delta)
	var image: Image = viewer.call("get_image")
	if image == null or image.get_width() != 256 or image.get_height() != 256:
		fail("rendered image is missing or has the wrong size")
	else:
		var opaque_samples := 0
		for y in range(8, 256, 16):
			for x in range(8, 256, 16):
				if image.get_pixel(x, y).a > 0.0:
					opaque_samples += 1
		if opaque_samples < 3:
			fail("rendered image contains too few non-transparent pixels (%d/256)" % opaque_samples)
	viewer.queue_free()

	print("file\tartboards\tscenes\tanimations")
	for row in summary:
		print("%s\t%d\t%d\t%d" % [row.file, row.artboards, row.scenes, row.animations])
	print("Smoke test: %d files, %d failure(s)" % [summary.size(), failures.size()])
	quit(0 if failures.is_empty() else 1)
