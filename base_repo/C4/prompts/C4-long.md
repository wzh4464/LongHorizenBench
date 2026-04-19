**Summary**: 为昇腾 NPU 实现 Exp（指数函数）自定义算子，支持 `base^(scale*x+shift)` 计算，覆盖 float16/float32/bfloat16 数据类型。

**Motivation**: 当前 CANN 算子库缺少独立的 Exp 算子。虽然部分融合算子内部包含指数运算，但没有支持自定义 base/scale/shift 参数的通用 Exp 实现。多个下游模型（如 attention score 的 temperature scaling、自定义激活函数）需要此能力。

**Proposal**: 参照仓库中已有算子的标准结构，在 contrib 目录下实现完整的 Exp 算子，包括 host 端（算子定义、tiling、shape 推断）、device 端（AscendC kernel）、示例程序和测试。

**Design Details**:

1. 算子规格：
   - 输入：x (REQUIRED)，支持 DT_FLOAT16 / DT_FLOAT / DT_BF16，FORMAT_ND
   - 输出：y (REQUIRED)，与输入同 dtype 和 format
   - 属性：base (float, optional, default=-1.0 表示自然底数 e), scale (float, optional, default=1.0), shift (float, optional, default=0.0)
   - 目标平台：ascend910b

2. Host 端设计：
   - 算子注册：定义输入/输出/属性，绑定 tiling 函数和 shape 推断函数
   - Tiling 策略：基于 UB 大小和核数计算数据分片（大核/小核分别处理不同数据量）。bfloat16 需要额外的中间 buffer 用于 cast 到 float 计算
   - Shape 推断：输出 shape 与输入相同

3. Device 端设计：
   - 使用 AscendC 编程模型实现 CopyIn → Compute → CopyOut 三级流水线
   - Compute 阶段：先算 scale*x+shift，若 base 非自然底数则乘以 log(base)，最后执行 Exp 运算
   - bfloat16 处理：先 Cast 到 float 计算，再 Cast 回 bfloat16

4. 示例和测试：
   - 提供 C++ 驱动程序调用 aclnn 接口
   - Python 数据生成脚本（numpy 生成输入并计算参考输出）和验证脚本
   - pytest 测试用例覆盖不同 dtype 和属性组合

5. 参考：仓库中已有的 math 类算子（如 abs、add 等）提供了标准目录结构和实现模式，应遵循一致的代码组织方式。
