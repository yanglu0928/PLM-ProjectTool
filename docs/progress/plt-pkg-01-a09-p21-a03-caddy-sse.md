# PLT-PKG-01-A09-P21-A03：Caddy HTTPS SSE 传输层验证

日期：2026-10-01；状态：`SYNTHETIC_SSE_TRANSPORT_PASS / PRODUCT_SSE_OPEN`。追溯：`CR-PKG-005`、P21-A01/A02。当前产品包无可直接用于此项验收的正式业务SSE端点，本项仅测Web边界，不能声称AI流式功能PASS。

编码前检查：Phase2/Gate3开放；输入为固定P15 ZIP/P17布局、Caddy v2.11.4输入及P21-A01 Host兜底。仅新增隔离传输测试，不改业务模块、实体、API合同、权限、Schema/Migration或正式包。验收：固定字节、`text/event-stream`首帧即时到达/正文完整、`Cache-Control:no-cache`、错误Host拒绝、断开后上游取消、资源清理；风险为纯合成路由不能证明真实AI或浏览器长期流质量。

`tools/smoke_caddy_sse_transport.py`在内存中给默认FastAPI追加仅测试用`/api/v1/test/synthetic-sse`，未写入包或正式API Contract。P15/布局21,103件与官方Caddy输入复核后，在两个随机回环端口用2小时合成证书启动Uvicorn/Caddy。真实网络请求：错误Host为421；正常`Accept:text/event-stream`取得200及`text/event-stream`/`no-cache`，首帧四行`id/event/data/空行`完整且在3秒内可读（上游第二帧故意延迟30秒以检测缓冲）；客户端主动断开后5秒内上游生成器`finally`收到取消。完整复验exit0、状态`SYNTHETIC_CADDY_SSE_TRANSPORT_PASS`；Caddy/API退出、证书目录清理。`release_eligible=false`。

未验证产品实际SSE端点、授权与项目隔离、负载/20并发、正式证书/账户/客户网络、Server2025/Debian13或Gate。下一项P22将已固定Caddy输入及配置模板作为**新**非发行候选装配，不重写P15；完整NOTICE/源码义务与安装服务/ACL/证书恢复仍单独审查。回滚撤销测试工具，不影响旧包或业务代码。
