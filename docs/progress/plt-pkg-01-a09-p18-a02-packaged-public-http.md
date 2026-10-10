# PLT-PKG-01-A09-P18-A02：随包公共HTTP与前端静态资产

日期：2026-10-01；状态：`SYNTHETIC_PACKAGED_PUBLIC_HTTP_FRONTEND_PASS / PRODUCTION_COMPOSITION_OPEN`。

编码前检查：Phase2/Gate3开放；输入为P15固定非发行ZIP、P17隔离布局、P18-A01随包空库初始化证据。仅以随包嵌入式Python在127.0.0.1短时启动默认`create_app()`和标准库静态文件服务，验证公共健康与前端实际字节；不挂载生产登录/Project写组合、不接正式License或已有DB、不改API/权限/Schema/服务配置。验收：21,103件与固定ZIP逐项Hash，live/ready=200且`UP`、默认Project路由404、前端index与两件JS/CSS网络字节和落盘相同、子进程正常退出。风险：标准库静态服务无HTTPS/正式SPA回退/安全代理，不是发行Web服务器；可撤测试脚本，既有程序不变。

首次网络执行被新探针误判：健康响应实际已是200/UP、Project默认404，但脚本按大小写精确查询`Cache-Control`键，而Python HTTP头字典返回`cache-control`。两个本轮子进程退出后，经随包`TestClient`复核真实响应，修正探针将头名规范为小写，再完整重跑。实测公共`/health/live`与`/health/ready`均200、`{"status":"UP"}`、`cache-control: no-store`；默认`/api/v1/projects`为404；静态`index.html`和所引用一件JS/一件CSS通过loopback HTTP读取并与包内文件SHA-256一致。定向单元2/2，停止后无本轮`uvicorn`/`http.server`残留，`C:\PLMTool`仍不存在。

此项明确不验证生产组合、用户登录/创建项目、真实License、TLS/反向代理、前端API跨源配置、业务UAT、目标账户、Server2025或Debian13。下一任务应检查隔离装配中的前端→API连接契约与正式安全代理/信任源缺口，再选择可验证的集成实现；Gate与发行仍保持开放，`release_eligible=false`。
