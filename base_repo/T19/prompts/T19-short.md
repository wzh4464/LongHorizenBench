**Summary**: gRPC C++ 现有的异步 API（基于 CompletionQueue）使用复杂，需要手动管理轮询和 RPC 生命周期。本任务要求实现回调式异步 API，让库在 RPC 操作完成时直接调用用户指定的回调函数，简化异步编程模型，同时保持高性能。

**Proposal**: 实现基于回调的异步 API，采用"反应器"（Reactor）设计模式。为不同 RPC 类型（unary、client streaming、server streaming、bidi streaming）提供客户端和服务端反应器基类。用户继承这些基类，重写完成回调方法（如 `OnReadDone`、`OnWriteDone`、`OnDone`）即可实现异步逻辑，库内部管理 CompletionQueue 轮询，用户无需关心。
