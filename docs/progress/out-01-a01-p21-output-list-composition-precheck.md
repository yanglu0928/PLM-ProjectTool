# OUT-01-A01-P21：OutputRequest列表Windows只读组合编码前检查

- 日期：2026-11-04
- 结果：PASS_WITH_LIMITATION，可开始单项实施
- Change Request：CR-OUT-017
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P21

## 单一目标

将冻结的 `GET /api/v1/projects/{project_id}/output-requests` keyset分页路由接入Windows显式read组合，使用专用HMAC cursor key，默认App保持未挂载。

## 编码前检查

- P14已有OUTPUT_REQUEST_LIST的Service、按ProjectId过滤的SQL keyset Repository、严格HTTP查询参数及独立 `OutputRequestListCursorCodec`。
- API-03允许ProjectManager、ImplementationMember、CustomerManager；不得扩展CustomerMember。游标绑定Session、Project、page_size与独立Output cursor family。
- Codec要求32-byte专用key；目前尚无Output cursor key的Windows组合Resolver。现有 `WindowsSecretKeyProvider` 可按当前账户从Windows Credential Manager只读获取32-byte key，Plan/Review也采用各自独立key ref。
- 新增独立key ref/factory；缺失/错误密钥时失败关闭，不写凭据、不复用其它模块key。列表router仅挂到 `include_secret_read`。
- 无Schema/API/Migration变化；正式服务账户Vault provision与Windows 11实机验证仍单独待办。

## 验收计划

1. 专属key ref解析/拒绝、project/session/page_size与cursor篡改测试；
2. Hosted PG18.6实际HTTP合成PM/IM/CustomerManager分页/续页与项目隔离；默认App无route；
3. 后端全量/wheel、前端及父包/A17/A34/A35/A50全量托管回归；仅runner D盘执行；
4. 完成后仅以PASS_SCOPE_LIMITED记录，保留真实Vault/Win11信任限制。
