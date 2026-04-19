# KEP-5365 代码生成评估 - 评分汇总

## 评分公式

```
score = 25 × (0.25·A + 0.10·B + 0.10·C + 0.55·D)
```

| 参数 | 含义 | 权重 |
|------|------|:----:|
| A | 功能正确性 (Functional Correctness) | 25% |
| B | 完整性 (Completeness & Coverage) | 10% |
| C | 行为等价 (Behavioral Equivalence) | 10% |
| D | 手写文件命中率 (Handwritten File Coverage) | 55% |

- A/B/C 各维度满分 5，来自评估报告原始打分
- D = 手写文件命中数 / 15 × 5，归一化到 /5 量纲（GT PR 共 15 个手写文件）
- 满分 125

## 各模型原始分数

| Model | A | B | C | D | 手写命中 |
|-------|:-:|:-:|:-:|:---:|:--------:|
| opus_long_loop | 4 | 3 | 2 | 3.33 | 10/15 |
| opus_long | 4 | 2 | 2 | 2.67 | 8/15 |
| codearts_long | 2 | 2 | 1 | 2.33 | 7/15 |
| opus_short_loop | 2 | 1 | 1 | 2.00 | 6/15 |
| opencodeglm_long | 2 | 1 | 1 | 2.00 | 6/15 |
| lingxi_long | 2 | 1 | 1 | 1.67 | 5/15 |
| opus_short | 1 | 1 | 0 | 1.67 | 5/15 |
| opencodeglm_short | 1 | 1 | 0 | 1.33 | 4/15 |
| lingxi_short | 1 | 1 | 0 | 1.00 | 3/15 |
| codearts_short | 1 | 0 | 0 | 0.00 | 0/15 |

## 最终得分（按 long 从差到好排列）

| Model | lingxi | opencodeglm | codearts | opus | opus (loop) |
|-------|:------:|:-----------:|:--------:|:----:|:-----------:|
| **short** | 22.5 | 27.1 | 6.2 | 31.7 | 45.0 |
| **long** | 40.4 | 45.0 | 52.1 | **71.7** | **83.3** |

## 各模型一句话总结

| Model | 得分 | 总结 |
|-------|:----:|------|
| opus_long_loop | 83.3 | 正确识别并实现 KEP 指定特性，覆盖 feature gate、字段剥离、digest 填充及部分测试，但使用 KEP 原始扁平 API 而非 PR 最终嵌套设计，缺少 validation tests 和 e2e tests。 |
| opus_long | 71.7 | 实现核心 KEP 功能（feature gate、digest 填充、字段剥离逻辑），API 遵循 KEP 扁平设计，但缺少服务端 validation、kuberuntime 导出函数、e2e tests 和 CRI API 扩展。 |
| codearts_long | 52.1 | 识别正确特性方向并修改了 7 个手写文件，但 API 设计错误（扁平 `ImageRef` 而非嵌套 `VolumeStatus`），缺少 feature gate drop logic、validation、tests 和 CRI API 变更。 |
| opus_short_loop | 45.0 | 尝试实现 image volume digest 但使用不兼容的 API 设计（pod 级 `ImageVolumesStatuses` 列表），缺少 `ImageVolumeWithDigest` feature gate 和 CRI API 变更，仅覆盖 40% 手写文件。 |
| opencodeglm_long | 45.0 | 使用扁平 `ImageRef` 设计（与 PR 嵌套结构不兼容），feature gate 版本号错误（1.33 而非 1.35），缺少 validation、drop logic、kuberuntime 导出和 e2e tests。 |
| lingxi_long | 40.4 | API 设计不兼容（扁平 `ImageRef`），kubelet 中使用 `sync.Map` 缓存而非运行时查询，缺少 validation、drop logic、kuberuntime 导出和 e2e tests。 |
| opus_short | 31.7 | 实现了完全不同的特性（`ContainerStatusResolvedImage`，修改 `ContainerStatus.Image` 而非 `VolumeMountStatus`），与 KEP-5365 零功能重叠。 |
| opencodeglm_short | 27.1 | API 结构根本错误（pod 级 `ImageVolumeStatuses` 列表而非 per-mount 嵌套），代码无法编译（引用未定义的 `extractDigest`），缺少所有 feature gate、tests 和 CRI API 变更。 |
| lingxi_short | 22.5 | 实现了两个无关特性（`CompleteContainerImageInfo` 和 `ImageVolumeLiveMigration`），feature gate 名称错误，代码存在语法错误无法编译，仅命中 3 个手写文件。 |
| codearts_short | 6.2 | 完全误解需求，实现了镜像拉取时的 digest 校验（安全特性）而非 pod status 中的 digest 暴露（可观测性特性），未触及任何手写文件。 |
