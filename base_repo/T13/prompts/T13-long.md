# T13: Godot Engine - Animation Loop Segments via Markers

*Upstream reference:* Godot proposal https://github.com/godotengine/godot-proposals/issues/2159, implementation PR https://github.com/godotengine/godot/pull/60965. All relevant content is inlined below; the implementing agent must not perform network access.

## 1. Background

Godot's `AnimationPlayer` supports looping playback, but only for the entire animation. Many game scenes need finer control: playing a character "intro" once, then looping an idle section, then playing an outro when triggered. Today authors work around this by splitting a single motion across three animations and cross-fading in GDScript or `AnimationTree`. This is verbose and error prone, and each split loses shared curve state.

The proposal introduces **named markers** on `Animation` resources (time positions on the timeline with string names and a color) and **section playback** APIs on `AnimationPlayer` that accept marker names (or raw times). The engine plays only the selected section, optionally looping between two markers.

## 2. Feature goals

1. Add markers to `Animation`: each marker is identified by a `StringName`, has a `time` (double, seconds), and an optional `Color`.
2. Allow the editor to add/rename/recolor/delete markers and render them on the timeline.
3. Expose new `AnimationPlayer` methods to play only a slice of the animation, optionally with a loopable subsection.
4. Keep backwards compatibility: `play()` without arguments must behave exactly as before.

## 3. Detailed design

### 3.1 Markers on `Animation`

```gdscript
animation.add_marker("loop_start", 1.5)
animation.add_marker("loop_end", 3.0, Color.GREEN)
animation.get_marker_time("loop_start")    # 1.5
animation.get_marker_names()               # ["loop_start", "loop_end"]
animation.remove_marker("loop_start")
```

Markers are stored as a sorted list of `(time, name, color)`. Lookups by name are O(N) but expected usage is small counts (typically < 16).

### 3.2 New `AnimationPlayer` API

```
play_section(anim_name, start_time, end_time, custom_blend=-1, custom_speed=1, from_end=false)
play_section_with_markers(anim_name, start_marker, end_marker, custom_blend=-1, custom_speed=1, from_end=false)
play_with_capture(anim_name, duration, ...)         # existing helper, unchanged
set_section(start_time, end_time)                  # adjust the playing section on the fly
get_section_start_time() / get_section_end_time()
```

While a section is active, the animation loops between `start_time` and `end_time` irrespective of the animation's own loop mode.

### 3.3 AnimationMixer integration

`AnimationMixer` (the successor of `AnimationTree`) adds a `PlaybackInfo.section_start/section_end` pair on the advance path; when both are non-zero they clamp the effective playback window and wrap the playback position when it exceeds the end.

### 3.4 Editor integration

The animation editor gains a new track-header affordance: right-clicking on the timeline inserts a marker. Markers show as flags above the timeline, can be renamed/recoloured, and are draggable with the mouse.

### 3.5 Save format

Markers are persisted on `Animation` as:

```gdscript
animation.add_marker("loop_start", 1.5)
animation.add_marker("loop_end", 3.0)
```

## 4. Implementation Task

1. The `Animation` resource — marker storage, helpers `Animation.add_marker()`, `Animation.remove_marker()`, `Animation.get_marker_names()`, and the corresponding serialization.
2. `AnimationPlayer` exposes `play_section(start_time, end_time, ...)` and `play_section_with_markers(start_name, end_name, ...)`.
3. The `AnimationMixer` advance/blend code: add `PlaybackInfo.section_start/section_end`; clamp the blend processing to the active section.
4. Editor support: extend the animation-player editor plugin and the animation-track editor with the marker UX.
5. Documentation updates for `Animation`, `AnimationPlayer`, `AnimationMixer`, `AnimationTree`.
6. Add tests covering marker upsert, section playback semantics, and serialization round-trip.

## 5. Acceptance Criteria

- Adding a marker at time `t` with `add_marker(name, t)` and reading it back via `get_marker_time(name)` returns `t`.
- `AnimationPlayer.play_section_with_markers("anim", "s", "e")` plays only between the two markers and loops within that range while the section is active.
- Deleting the `AnimationPlayer` mid-playback does not leak timers.
- All existing tests for `AnimationPlayer`/`AnimationTree` continue to pass.
