# T35: Electron

**Summary**: Electron 当前的预加载脚本仅支持在渲染进程的 web frame 中运行，无法在 Service Worker 等其他执行上下文中使用。RFC-0008 提出实现"预加载领域"（Preload Realm）功能，允许在 Service Worker 中运行隔离的预加载脚本，通过 IPC 与主进程通信，为扩展和应用提供在 worker 上下文中定制 API 的能力。

**Motivation**: Electron 对 Chrome 扩展 API 的支持有限，完整支持会增加维护负担。社区需要在 Service Worker 中使用预加载脚本的能力，以便：(1) 为扩展的 Service Worker 提供自定义 API；(2) 修复 worker 中的 API 问题（如 atob/btoa 实现）；(3) 在 worker 与主进程之间建立 IPC 通道。预加载领域基于 V8 的 ShadowRealm 概念，提供隔离的 JavaScript 执行环境。

**Proposal**: 在 Electron 中实现 Service Worker 的预加载领域支持，包括：(1) 创建 `ServiceWorkerMain` 类处理 Service Worker 与主进程的 IPC 通信；(2) 扩展 Session API 支持为不同上下文类型注册预加载脚本；(3) 实现 `IpcMainServiceWorker` 类作为 Service Worker 专用的 IPC 处理器；(4) 在渲染进程中创建预加载领域上下文并执行脚本。

**Design Details**:

1. 构建系统配置：
   - `BUILD.gn`：添加 `electron_preload_realm_bundle` webpack 构建目标
   - `build/webpack/webpack.config.preload_realm.js`：预加载领域的 webpack 配置
   - `filenames.gni`：更新文件名列表，包含新增的预加载领域相关文件

2. 浏览器进程 API：
   - `lib/browser/api/service-worker-main.ts`：实现 `ServiceWorkerMain` 类，提供 `send()` 方法和 `ipc` 属性
   - `lib/browser/api/session.ts`：扩展 `setPreloads()` 支持指定目标上下文类型
   - `shell/browser/api/electron_api_session.cc/h`：C++ 侧 Session API 实现

3. IPC 通信层：
   - `lib/browser/ipc-dispatch.ts`：IPC 消息分发逻辑
   - `shell/browser/api/ipc_dispatcher.h`：IPC 分发器接口
   - `shell/browser/electron_api_sw_ipc_handler_impl.cc/h`：Service Worker IPC 处理实现
   - `shell/common/gin_helper/reply_channel.cc/h`：回复通道实现

4. 预加载领域运行时：
   - `lib/preload_realm/init.ts`：预加载领域初始化入口
   - `lib/preload_realm/api/exports/electron.ts`：导出 electron 模块
   - `lib/preload_realm/api/module-list.ts`：模块列表管理

5. 渲染进程集成：
   - `shell/renderer/preload_realm_context.cc/h`：预加载领域 V8 上下文管理
   - `shell/renderer/preload_utils.cc/h`：预加载工具函数
   - `shell/renderer/service_worker_data.cc/h`：Service Worker 数据管理
   - `shell/renderer/electron_sandboxed_renderer_client.cc/h`：沙箱渲染器客户端更新

6. IPC Renderer 侧：
   - `lib/renderer/api/ipc-renderer.ts`：更新 ipcRenderer 支持 Service Worker
   - `lib/renderer/ipc-native-setup.ts`：原生 IPC 设置
   - `lib/renderer/ipc-renderer-bindings.ts`：IPC 绑定
   - `shell/renderer/api/electron_api_ipc_renderer.cc`：C++ IPC 实现
   - `shell/renderer/electron_ipc_native.cc/h`：原生 IPC 实现

7. 文档：
   - `docs/api/ipc-main-service-worker.md`：IpcMainServiceWorker API 文档
   - `docs/api/service-worker-main.md`：ServiceWorkerMain 更新
   - `docs/api/service-workers.md`：Service Workers 文档更新
   - `docs/api/process.md`：添加 `service-worker` 进程类型
   - `docs/api/structures/`：相关结构体文档

8. 类型定义：
   - `typings/internal-ambient.d.ts`：内部类型声明
   - `typings/internal-electron.d.ts`：内部 Electron 类型

9. 测试：
   - `spec/api-service-worker-main-spec.ts`：ServiceWorkerMain 测试
   - `spec/api-service-workers-spec.ts`：Service Workers 测试
   - `spec/fixtures/api/preload-realm/`：预加载领域测试 fixtures

## Requirement
https://github.com/electron/rfcs/blob/main/text/0008-preload-realm.md
