# Job列表运行Contract增量

P03（2026-09-27）：Windows当前账户只读专用`job-list-cursor-v1` KeyRef入口与临时Vault失密/错误口令/防覆盖/原key恢复旧密文游标已验。正式运行账户通过既有交互生命周期独立供给/备份，运行时不能自动生成替代。尚未挂Windows列表，正式供给/其他账户/Server2025未验证。

2026-09-27/API-01及API-03冻结基线保持，CR-JOB-005补实现与安全控制。

- 可选`GET /api/v1/projects/{project_id}/jobs`与`GET /api/v1/admin/jobs`，当前Session/License、Project membership及Owner来源逐页再核。项目PM/IM看受权metadata，客户仅原creator；Admin只GLOBAL/DEPLOYMENT、不绕项目。registry只支持已验证Owner，不猜其他Owner权限；完整Scope后续补齐。
- 查询`page_size`默认50、1～200，`cursor`服务器不透明AES-256-GCM token；可选`scope`：项目仅PROJECT，管理面GLOBAL或DEPLOYMENT，省略为该路径全部允许Scope。未知/重复query400，错误size/scope422；只接受固定倒序created_at/job_id稳定keyset。
- Envelope：data={items:[当前安全Job metadata],next_cursor:string|null,has_more:boolean},trace_id；无total_count/私有position/正文/payload/Lease/path。单项使用与详情相同已核安全字段，unknown细分进度/error仍null，不编造；结果逻辑ref不授下载权。响应no-store/nosniff。
- 每页最多page_size候选，受限来源可隐藏；可能空items但has_more=true，继续next_cursor。下一位置来自最后消耗候选，已加密不能看到隐藏JobID。跨页不承诺固定快照/自动填满或并发新任务包含；坏来源不是隐藏正常页，静态503。
- 游标绑定family/版本、Session摘要、project_id、scope查询、page_size，随机96-bit nonce/专用256-bit密钥；身份撤销仍逐页拒绝，不缓存授权。篡改/错key-family-session-project-scope-size400；恢复原专用密钥旧token可继续，密钥缺失不能临时生成替代。Windows密钥安全来源/运行挂载下一项，默认应用仍404。
- 无Migration/新依赖/Breaking路径变化；既有0044要求保留。性能/三平台/全Owner/正式发行及Gate3待。
