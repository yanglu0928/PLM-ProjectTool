# WFL-01-A06-P03：Workflow 启动可选 HTTP 合同

2026-10-02 / Phase 2 / `OPTIONAL_HTTP_PASS`。编码前检查：Gate 2 冻结 `WORKFLOW_START POST /api/v1/projects/{project_id}/workflow:start`（PM、S/L/C/I/M/A、200）、V1.1 最小人工确认、P02 内部命令及 API-01 Session/CSRF/强 ETag/幂等合同具备。本项只建立可选 HTTP 边界，不装入默认或正式 Windows 组合，不改 Schema/依赖/Stage Gate。

实现：Trusted Origin/Host、Cookie Session+CSRF、持久幂等 Key、`If-Match` v0、空 body/无查询参数；调用 P02 的当前受权启动命令。返回仅固定 V1 WorkflowView 白名单、TraceId、`Cache-Control: no-store` 和强 ETag。鉴权/许可/归档/版本/状态/重放冲突映射至冻结公共错误，不向响应泄漏内部异常。默认应用仍 404。

验证：HTTP 单元6项及异常/请求边界矩阵；后端全量1830项通过、3项既有环境跳过。`validation/wfl-01-a06-p03-start-http/verify.py` 在 Windows 11 一次性 PostgreSQL18.6 空库→head、真实 Session/CSRF/PM 和 ASGI 下通过：默认404，非经理404，缺版本428、CSRF/Host/License403，首次200、同 Key原结果200、不同负载/Key冲突409、非空body/查询400；数据库仅一次 ACTIVE/HANDOVER/v1、一条启动Audit和一条完成收据，StageTransition零条。临时库和集群退出后清理；开发 wheel SHA-256 `c0e62cb1dd0aee93ea73e971f8c72c17bab604c88daeb234597fad6c0dac7f2a`，非发行包。合成 License 不代表生产信任。

兼容/升级/回滚：冻结路径/响应/错误增量实现，无新 Migration/依赖；需现有0015/0030。可撤可选 Router；已真实启动的 Workflow/Audit/收据不可直接撤销。Windows 显式生产组合/正式 License、真实浏览器、Stage Gate、Server2025/Debian、性能/UAT/Gate3仍未完成。下一项 `WFL-01-A06-P04` 仅在 Windows 显式组合根挂载并做失败关闭/隔离库验证。
