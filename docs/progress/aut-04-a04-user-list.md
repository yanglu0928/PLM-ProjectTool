# AUT-04-A04：安全User列表内部读取

2026-09-27 Phase2编码前PASS。输入冻结64cdf09 API-02 AUTH_USER_LIST、0045/A01～A03实际User读取与当前Admin。仅内部稳定分页，无HTTP/cursor/Windows新供给。

DEC289：共享安全UserReadView八项metadata，固定created_at DESC/user_id DESC keyset，page_size1～200/n+1，严格源排序/唯一ID/边界/has_more；当前Session/ENABLED Admin/License每页重新核，禁用目标也管理可见。一次SQL读取metadata快照，不对全页目标加锁，不宣称跨页固定快照；原Admin Session/User锁仍保持。位置只内部DTO、未来公开游标不得裸返回。无Credential表读取/业务写/commit/新Schema/依赖/角色。

验收真实PG同时间多行/多页无漏重/空末页、禁用目标、当前普通用户/撤会话/降权/License拒绝五表无写、非法Source和最后Guard失败；旧详情/Windows/发布回归。风险：并发新增不保证同一快照、分页索引与20并发性能未验；公开cursor独立供给后续。回滚撤服务调用保历史，无生产迁移。

执行结果：WINDOWS_INTERNAL_LIST_PASS。6新unit/1265后端无失败（2既有权限跳过），真实PG七个相同timestamp目标UUID倒序、多页完整无重漏/200页与空末页/DISABLED可见，普通/未知/实际撤Session与Admin降权/License拒绝五表完整无写；旧WindowsUser详情与原双Scope文件发布回归通过。首次unit因引用未使用package路径失败，仅改相对测试引用后全套通过，不改生产保护。

开发wheel687737字节，SHA256 b184d72dd742742291ff057df9acba6148325c7280d7cb186e882c7980944469，非安装包。无Migration/公开API/依赖/角色/升级动作；现0045兼容、撤内部服务调用回滚保历史。正向License合成，公开游标/HTTP/Windows供给/跨页并发快照/索引性能/完整管理面/三平台/包/Gate未证明。Next AUT-04-A05独立加密游标与可选User列表HTTP，实时授权每页仍必需。
