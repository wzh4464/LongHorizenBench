**Summary**: 为昇腾 NPU 实现 Exp（指数函数）自定义算子，支持 `base^(scale*x+shift)` 计算，覆盖 float16/float32/bfloat16 数据类型。

**Proposal**: 参照仓库中已有算子的标准结构，在 contrib 目录下实现完整的 Exp 算子，包括 host 端（算子定义、tiling、shape 推断）、device 端（AscendC kernel）、示例程序和测试。
