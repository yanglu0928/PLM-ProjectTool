# PRJ-04-A09-P01：Project Member 列表 cursor 前置

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A09-P01。输入：冻结 API-01 完整性保护 keyset、API-02 成员列表、PRJ-02-A01 内部 MemberId 分页；决策 `DEC-20260925-063`。
- Changed：新增独立 HMAC-SHA256 不透明成员列表 cursor，绑定资源族、ProjectId、Session 摘要、page_size 与最后 MemberId；篡改、跨项目/会话/查询或非规范编码拒绝。顺手修正既有 Secret cursor 契约测试的随机误报：确保“篡改”用例一定改变字符。
- Files：成员 cursor 编解码及单元测试、既有 Secret 测试修正、决策/状态/版本记录。
- Migration：无。API：无公开路由；冻结 `/api/v1` 合同未变。
- Tests：Windows 11/Python 3.13 后端 401/401 PASS，成员 cursor 往返/作用域/签名/输入界限 PASS；开发 wheel 构建 PASS。未运行 PostgreSQL（此项纯编解码，无 SQL 变更）。
- Result：cursor 前置 PASS；正式 Windows 当前账户独立密钥 `project-member-list-cursor-v1` 的供给/备份和组合仍待，成员列表 HTTP 尚未开放。
- Known Issues：正式发行信任源、Server 2025/HTTPS、Debian 13 和最终程序包未完成。
- Next：PRJ-04-A09-P02 成员列表可选 HTTP 安全投影及 PostgreSQL 分页验证。
