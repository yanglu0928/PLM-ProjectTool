# SOL-04-A12：Section LIST 独立签名 cursor

日期：2026-10-09。结果：`SOL_04_A12_SECTION_LIST_CURSOR_PASS`，限 codec、合成密钥和 Windows 11 隔离 PostgreSQL 18.6 串页；正式 Vault key/公开 HTTP 未实现。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A12。
- 输入基线：冻结 `SOL_SECTION_LIST`、A11 内部 UUID keyset、Outline LIST 游标安全模式。
- 前置：Section LIST Owner/真实 Session-PG 三页及成员/指针复验已通过。
- 模块/实体/API/权限：仅 Section 专用 cursor codec/测试；无实体、Schema/Migration、角色或公开 API 变更。
- 验收：同 Session/Project/page size/Section 家族解码，跨 Session/项目/大小/密钥/家族与篡改拒绝，隔离 PG 两页真实串接，后端全量。
- 风险：密钥误复用或合成 key 进入正式环境。codec 要求独立 32 字节 key；本项仅测试常量，A13 另供 Vault key ref 和备份恢复。

## 实施与验证

新增 `SectionListCursorCodec`，使用 HMAC-SHA256 不透明令牌，固定 `project-section-list` 家族，绑定 ProjectId、Session token 摘要、page size 指纹与最后 SectionId；严格 canonical base64/JSON/UUID 和签名比较。单元测试验证轮回、错误输入、篡改、跨 Session/项目/页大小/密钥，以及相同测试 key 下也无法与 Outline 家族互换。Windows 11 一次性 PG18.6 复用 A11 真实 Session/三 Section，第一页位置经签名解码后取第二页；原 PROJECT Reference 与 Section LIST 夹具回归通过。

后端全量 `3389 passed, 3 skipped, 5108 subtests passed`。兼容/升级/回滚：无 Migration、依赖、公开 API 或前端变化；移除 codec 即可回滚，Section 历史保留。下一项 `SOL-04-A13` Windows 独立 Vault key/备份恢复；随后可选 HTTP/平台组合。正式目标账户、20 并发、Server2025、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
