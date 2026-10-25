# PRT-01-A11-A04-A03-P04：Prototype Workflow 页面显式接线

日期：2026-10-08。状态：页面内部测试通过；正常路由与生产后端均未启用 Prototype。

编码前检查：依据 Gate 2 冻结 Workflow/Checklist 合同、`CR-PRT-005` 以及 A04-A02/A03-P01～P03 的可选服务与客户端。只增加流程页的可选操作能力，不扩权限、Schema、API 或业务事实。真实 HTTP/PG/磁盘与性能尚未验证，默认关闭是必要防线；不能把资格预览或首回执表述为正式客户确认。

实现：页面增加 `prototypeWorkflowEnabled` 显式布尔入口，默认不传为关闭。开启时仍仅 ProjectManager、当前 ACTIVE PROTOTYPE 阶段可核验/记录两项；预览只显示 REQ-03 与 PRT-03 主体计数，不展示内部 UUID/正文/磁盘路径。PROTOTYPE→SOLUTION 仍需两项当前 PASS、填写理由和二次确认，写时交由服务端重新复验。未知结果保留原 Key/Body/ETag，首次回执不代表当前状态。正常应用路由未传该开关，因此生产用户仍看不到按钮。

验证：页面定向 21 项覆盖默认关闭、显式开启、主体计数不泄漏标识和双 PASS 才显示推进；前端全量 101 文件/1605 项、typecheck、220 模块构建通过。真实 Win11/PG/HTTP/文件/性能待 A05。

兼容性/升级/回滚：无迁移或新依赖，重建前端即可；保持开关关闭即回到旧行为，Workflow 历史不变。A05 满足 `CR-PRT-005` 全部证据后，才能在正式组合与路由中显式开启。

TraceLink：`CR-PRT-005` → A04-A02 可选后端组合 → A03-P01～P03 客户端 → A03-P04 页面 → A05 真实验收。
