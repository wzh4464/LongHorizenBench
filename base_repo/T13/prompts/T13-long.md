# T13: Godot Engine - 动画标记系统 (Animation Markers)

## Summary

Godot 引擎的动画系统目前无法指定动画的部分片段进行循环播放。当动画包含启动序列和循环主体时，每次循环都会从头播放启动序列。本任务需要为 Animation 资源添加标记 (Marker) 系统，并扩展 AnimationPlayer 以支持基于标记的片段播放功能。

## Motivation

在游戏开发中，很多动画需要"启动-循环"的播放模式：

- **角色攻击动画**：抬手准备 -> 挥砍循环
- **跑步动画**：起步加速 -> 稳定跑步循环
- **技能特效**：蓄力阶段 -> 持续释放循环

当前 Godot 的动画循环会从头开始，导致：
- 每次循环都重复播放启动帧
- 无法实现"播放一次启动，然后只循环主体"的效果
- 开发者需要将动画拆分为多个资源，增加管理复杂度

通过引入动画标记系统，开发者可以在单个动画中标记不同片段，并指定要播放/循环的区域。

## Proposal

为 Godot 引擎的动画系统添加标记 (Marker) 功能：

1. 在 Animation 资源中添加标记数据结构，支持命名标记和时间点关联
2. 为 Animation 类添加标记的增删查改 API
3. 为 AnimationPlayer 添加基于标记的片段播放方法
4. 在动画编辑器中添加标记的可视化编辑界面
5. 支持在 AnimationTree/AnimationNodeAnimation 中使用标记配置自定义时间线

## Design Details

1. **Animation 类扩展**：在 `scene/resources/animation.h/.cpp` 中为 Animation 类添加标记存储结构；实现 `add_marker(name, time)`、`remove_marker(name)`、`has_marker(name)`、`get_marker_time(name)`、`get_marker_names()` 等方法；添加 `get_marker_color(name)`、`set_marker_color(name, color)` 支持标记颜色自定义。

2. **标记查询方法**：实现 `get_marker_at_time(time)` 返回指定时间点的标记；实现 `get_next_marker(time)` 和 `get_prev_marker(time)` 返回相邻标记。

3. **AnimationPlayer 片段播放**：在 `scene/animation/animation_player.h/.cpp` 中添加 `play_section(name, start_time, end_time, ...)` 方法；添加 `play_section_with_markers(name, start_marker, end_marker, ...)` 基于标记名播放；实现 `play_section_backwards` 和 `play_section_with_markers_backwards` 反向播放版本。

4. **片段状态管理**：添加 `has_section()`、`get_section_start_time()`、`get_section_end_time()` 查询当前片段状态；添加 `reset_section()` 清除片段设置恢复全动画播放。

5. **AnimationMixer 集成**：在 `scene/animation/animation_mixer.h/.cpp` 中处理片段边界逻辑；确保片段结束时间不超过动画长度；正确处理循环模式下的片段边界。

6. **编辑器 UI - 标记添加**：在 `editor/animation_track_editor.cpp/.h` 中添加右键菜单选项"Add Marker"；实现标记名称输入对话框，验证名称唯一性。

7. **编辑器 UI - 标记显示**：添加标记图标资源 (`editor/icons/Marker.svg`, `MarkerSelected.svg`)；在时间轴上渲染标记，支持选中、拖动调整时间。

8. **编辑器 UI - 片段选择**：实现双击两个标记选中它们之间的片段；高亮显示选中的片段区域；播放按钮在有片段选中时播放片段而非全动画。

9. **AnimationTree 支持**：在 `editor/plugins/animation_blend_tree_editor_plugin.cpp/.h` 中添加"Set Custom Timeline from Marker"按钮；实现标记选择对话框，自动填充时间偏移和长度。

10. **文档更新**：更新 `doc/classes/Animation.xml` 添加新方法文档；更新 `doc/classes/AnimationPlayer.xml` 添加片段播放方法文档。

## Requirement

https://github.com/godotengine/godot-proposals/issues/2159
