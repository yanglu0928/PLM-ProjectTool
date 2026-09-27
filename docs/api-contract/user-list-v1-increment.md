# User列表运行Contract

A06（2026-09-27）：Windows当前账户只读独立user-list-cursor-v1入口已验，无运行时创建/明文fallback；随机非正式临时Vault失密/错口令/防覆盖/恢复原key旧cipher与清理实际通过，1276无失败/2既有跳过。正式引用未供给，列表尚未挂；下一装配新增必需KeyRef，须先按原交互工具独立供给备份，不能把测试来源当正式信任。

2026-09-27 / AUT-04-A05，冻结API-02 AUTH_USER_LIST/64cdf09保留。可选GET `/api/v1/admin/users`，default404/Windows尚未挂。

- 当前合法Session Cookie与可信Host、同UOW ENABLED DeploymentAdmin/License每页重新核；读取不续Session/不写Audit/receipt。DISABLED目标也可见，不新增管理权限。Session未知/撤销401，当前非Admin404，Host/License403，错误query/cursor400、非法页size422，未知源503 SYSTEM_UNAVAILABLE。
- query仅page_size（默认50、1～200）与cursor；重复/未知query400。固定created_at DESC/user_id DESC keyset/n+1，没有total_count。并发变更不保证跨页固定快照或新用户出现在已开始的分页中。
- data={items:[与User详情相同八项安全UserView],next_cursor:string|null,has_more:boolean}、Envelope trace_id/no-store/nosniff。无Credential hash/算法参数/ID、token/CSRF、username canonical/retention、私有position。
- 独立AES-256-GCM/32byte key/随机96bit nonce、user-list专属family与版本、Session摘要/page_size AAD；位置UTC timestamp/user ID均密文。强校验canonical payload/base64，篡改/错Session-size-family-key400；恢复原key旧cursor仍可解但必须重新授权；密钥供给来源不能自动生成fallback。
- 3cursor unit+5HTTP Contract与真实PG分页/当前权限/五表无写通过，1273无失败/2既有跳过，正向key/License合成。无Migration/依赖/角色/Breaking，回滚撤router保历史；Windows来源/正式供给/性能/完整管理面/三平台/包/Gate待。
