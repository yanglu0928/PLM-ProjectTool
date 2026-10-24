# SOL-02-A06-P06 Windows Outline 列表游标密钥来源

日期：2026-10-09。状态：当前账户独立 Credential Manager key ref 与临时加密备份恢复验证通过；目标服务账户正式供给未验。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P06。
- 输入基线：P05 独立 `OutlineListCursorCodec`；现有 Windows SecretKeyProvider/生命周期与 PROJECT Reference 独立密钥模式。
- 前置任务：P05 游标家族/会话/项目/查询绑定及真实 PG keyset 串接通过。
- 模块/实体/API/权限：Windows composition 的独立 key resolver 工厂；不新增实体、公开 API 或业务权限。缺 key 或错长拒启动。
- 验收标准：与 Reference/Document key ref 不同；只接受 32 字节；随机临时 Windows Credential Manager 凭据删除后从加密备份恢复，旧游标仍可验证。
- 风险：当前交互账户与随机测试 ref 不能代表目标服务账户的 Vault ACL、正式备份保管或 Server2025 验收；正式 key 未创建、不写入仓库。

## 实施与验证

新增 `OUTLINE_LIST_CURSOR_KEY_REF=project-outline-list-cursor-v1` 与 fail-closed `create_windows_outline_list_cursor_codec`。生产构造只读取当前账户 Credential Manager 中的独立 32 字节 key；缺失或无效只给非敏感启动错误。不自动生成密钥，不在日志/配置/仓库存储 key。

- 定向单元：2 passed / 3 subtests，含独立 ref、缺失/错长拒启动、Windows 11 真实临时 Credential Manager 凭据删除与加密备份恢复，旧 token 解码一致。
- 后端全量回归：3381 passed / 3 skipped / 5075 subtests passed。
- Schema/Migration/依赖/冻结 API：无变更。删除此独立工厂可回滚；测试仅使用随机临时 ref，清理后不影响正式凭据。

下一项：`SOL-02-A06-P07` 可选 LIST HTTP；随后 Windows 显式平台组合注入该独立 key。正式目标服务账户/发行仍待。
