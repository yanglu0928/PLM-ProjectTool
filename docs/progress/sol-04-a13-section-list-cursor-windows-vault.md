# SOL-04-A13：Section LIST Windows 独立 Vault key

日期：2026-10-09。结果：`SOL_04_A13_SECTION_CURSOR_WINDOWS_VAULT_PASS`，限 Windows 11 当前账户随机临时凭据及合成备份恢复；目标服务账户正式供给未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A13。
- 输入基线：A12 Section 专用 HMAC cursor、现有 Windows Credential Manager 密钥来源和受控备份恢复规则。
- 前置：codec 的家族/Session/Project/page size/位置绑定与真实 PG 跨页已验证。
- 模块/实体/API/权限：仅 Windows Section cursor key ref/失败关闭工厂及测试；无实体、Schema/Migration、公开 API 或角色变动。
- 验收：独立 key ref、不存在/错长密钥拒启动、随机临时 Credential Manager 凭据丢失和加密备份恢复后旧 cursor 解码；后端回归。
- 风险：测试凭据误作生产来源。正式 key 不自动生成/提交，目标服务账户 Vault ACL、备份保管和 Server2025 另验。

## 实施与验证

新增独立 `project-section-list-cursor-v1` 引用与 `create_windows_section_list_cursor_codec`；仅从当前账户 `WindowsSecretKeyProvider` 只读 32 字节 key，缺失/非法时统一拒启动。与 Outline、PROJECT/GLOBAL Reference、Document cursor key ref 明确不同。Win11 随机临时引用测试供给、生成旧 cursor、删除临时凭据、确认失密、加密备份恢复、解码旧 cursor，最后清理临时引用。测试中未创建正式 key，也未把合成 passphrase/密钥写入 Git。

定向 `2 passed, 3 subtests passed`；后端全量 `3391 passed, 3 skipped, 5111 subtests passed`。兼容/升级/回滚：无 Migration、依赖、公开 API 或前端变化；撤下工厂可回滚，Section 历史保留。下一项 `SOL-04-A14` Section LIST 可选 HTTP/真实 ASGI-PG，再接 Windows 显式组合。目标服务账户/正式 key 供给和恢复、20 并发、Server2025、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
