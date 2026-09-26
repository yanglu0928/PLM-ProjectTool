# PRJ-04-A13-P01：Department 列表游标前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A13-P01。来源：冻结 API-01/02、PRJ-03-A01；决策 DEC-20260925-075。
- Changed：新增独立 HMAC-SHA256 部门历史 keyset 游标；绑定资源族、ProjectId、当前 Session、page size 与 `department_id` 稳定位置。成员游标不能互换；未开放 HTTP。
- Compatibility/Upgrade：无新 Schema/Migration/依赖或 Breaking API；升级无需数据操作。
- Tests：Windows 11/Python 3.13 后端 424/424 PASS；游标往返、不同会话/项目/page size、篡改、错误密钥、跨资源族及无效位置拒绝 PASS；开发 wheel PASS。PostgreSQL 不适用于本纯编码组件，本项未运行数据库测试。
- Result：游标前置 PASS；公开 GET、Windows 正式密钥来源、Gate 3 与可用程序包未完成。
- Known Issues：Windows Server 2025 与 Debian 13 本项未验证；公开路由须独立确认权限和 License。
- Next：PRJ-04-A13-P02 Department 列表可选 HTTP。
