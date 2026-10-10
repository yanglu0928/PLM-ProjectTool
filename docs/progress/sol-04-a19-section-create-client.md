# SOL-04-A19：Section CREATE 安全传输/客户端

日期：2026-10-09。结果：`SOL_04_A19_SECTION_CREATE_CLIENT_PASS`；仅客户端与合同测试，创建页/真实浏览器未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A19。
- 输入基线：Gate 2 冻结 API-04 `SOL_SECTION_CREATE`、CR-SOL-012、A04/A05 后端 HTTP/Windows 验证及 A16 拆分；前置满足。
- 模块/实体/API/权限：Auth `SessionClient` 受保护 POST 传输、Solution `SectionCreateClient`；Section 初态身份与同项目 Outline 父项，冻结 POST 路径不变。前端仅 PM/实施成员预门控，最终授权由后端复验。
- 验收：规范 SectionKey 与 canonical Project/OutlineId、原 Idempotency-Key/CSRF、精确 201 初态/ETag/Location/Trace、已知拒绝和未知结果失败关闭；合同、前端全量/typecheck/build。
- 风险：创建结果不明时换操作号产生重复；返回不可信父目录/项目造成跨项目导航；把初态 Section 当作已审批正文。

## 实施与验证

`SessionClient` 新增 `postProjectSectionCreate`，复用受保护同源 POST、CSRF 与幂等传输，不自动重试。`SectionCreateClient` 仅接受 NFKC/trim 后 1～128 字符且无控制字符的稳定 SectionKey、当前项目 PM/实施成员；发送精确 `solution_outline_id`/`section_key`。成功要求固定初态字段、同项目/父目录、`ACTIVE`/无批准指针/`v0`、JSON/no-store、Trace Header 与 Envelope 一致、ETag 和 Location 指向返回的 Section。已知状态/错误码映射；网络、超时、未知响应或畸形 201 标为 uncertain，由后续 UI 持久保存原 Key 并提示核对，不在客户端生成新 Key。

创建客户端与 `SessionClient` 定向 `174 passed`；前端全量 `116 files, 1676 passed`；`pnpm --dir apps/frontend build` 含 typecheck/build，退出 0。后端真实 PG/ASGI 属 A04/A05 已有证据，本项未运行新后端/浏览器测试，不能标真实用户创建完成。构建既有大块提示不改变本项结论。

兼容/升级/回滚：无 Schema/Migration、依赖或冻结 API 变化；撤下新客户端/传输入口可回滚，已有 Section 历史保留。下一项 `SOL-04-A20` 创建页/父 Outline 入口与合同，然后 A21 Win11 浏览器/PG。TraceLink：Gate 2/API-04 → CR-SOL-012/A05 → A16 → A19 → A20。
