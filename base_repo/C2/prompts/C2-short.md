**Summary**: add_layer_norm 和 layer_norm_grad_v3 算子在特定硬件上存在精度问题。ReduceSum 相关的计算路径产生不正确的结果。

**Proposal**: 移除有问题的硬件特殊处理分支，统一 ReduceSum 的调用方式；同时修正 ReduceSum 的 count 参数以确保计算精度。
