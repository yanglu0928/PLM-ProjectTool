# WFL-01-A08-P03：Workflow START 首次回执安全客户端

2026-10-02 / Phase 2 / `FRONTEND_RECEIPT_PASS`。编码前检查：P01 固定 V1 安全读投影、P02 私有 Session 写桥接和后端同 Key 首次结果语义已具备。只新增客户端回执校验，不接页面、不更改业务 Gate/API/Schema/依赖。风险为把历史 200 重放误用作当前流程状态。

实现：只允许带规范 ProjectId、原始 NOT_STARTED/`"v0"` WorkflowView 和原 Key 调用；200 响应须与原 WorkflowId 对应、固定 V1 ACTIVE/HANDOVER/`"v1"`、首阶段 ACTIVE、其他阶段 NOT_STARTED、十二清单 PENDING，响应头/体强 ETag 一致。返回 `is_current_state_proof=false` 的首次回执；当前流程须独立 GET。已知 401/403/404/409 错误按固定代码提示，未知网络/格式/结果差异都标“不确定”，不能自动生成新 Key 或重试。

验证：新增13项回执单元及拒绝矩阵，前端全量60文件1188项、typecheck和production build通过。未运行真实浏览器或项目页面；旧非发行 ZIP 不含本项。

兼容/升级/回滚：仅未接线前端客户端，现有路由/API/Schema/权限/依赖不变；重建前端资产，无数据迁移；可撤未调用客户端。下一项 `WFL-01-A08-P04` 项目 Workflow 页面/导航与状态/原操作保护。正式 License、A07 Owner/Gate、Server2025/Debian、真实浏览器/UAT/Gate3仍开放。
