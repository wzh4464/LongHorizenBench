**Summary**: Godot 引擎的动画系统目前无法指定动画的部分片段进行循环播放。当动画包含启动序列和循环主体时，每次循环都会从头播放启动序列。本任务需要为 Animation 资源添加标记 (Marker) 系统，并扩展 AnimationPlayer 以支持基于标记的片段播放功能。

**Proposal**: 为 Godot 引擎的动画系统添加标记功能，在 Animation 资源中添加支持命名标记和时间点关联的数据结构，为 Animation 类添加标记的增删查改 API，为 AnimationPlayer 添加基于标记的片段播放方法，在动画编辑器中添加标记的可视化编辑界面，并支持在 AnimationTree 中使用标记配置自定义时间线。
