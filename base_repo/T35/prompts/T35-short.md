**Summary**: Electron 当前的预加载脚本仅支持在渲染进程的 web frame 中运行，无法在 Service Worker 等其他执行上下文中使用。RFC-0008 提出实现"预加载领域"（Preload Realm）功能，允许在 Service Worker 中运行隔离的预加载脚本，通过 IPC 与主进程通信，为扩展和应用提供在 worker 上下文中定制 API 的能力。

**Proposal**: 在 Electron 中实现 Service Worker 的预加载领域支持，创建 `ServiceWorkerMain` 类处理 Service Worker 与主进程的 IPC 通信，扩展 Session API 支持为不同上下文类型注册预加载脚本，实现 `IpcMainServiceWorker` 类作为 Service Worker 专用的 IPC 处理器，并在渲染进程中创建预加载领域上下文并执行脚本。
