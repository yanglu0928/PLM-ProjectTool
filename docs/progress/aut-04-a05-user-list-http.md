# AUT-04-A05：User列表加密游标与HTTP

2026-09-27 Phase2编码前PASS；冻结API-02 AUTH_USER_LIST/A04真实分页、当前0045。仅可选GET `/api/v1/admin/users`与Auth owned加密cursor，不接Windows新Key供给，不公开写。

DEC290：既有批准cryptography AES-256-GCM、独立32byte key与family/user ID私有position，随机nonce，AAD绑Session摘要/page_size；严格canonical载荷和base64，错误400。每页当前Session.validate再Admin/License，读不写；严格page_size1～200/默认50、仅page_size/cursor query、重复未知400。Envelope items/next_cursor/has_more与trace_id/no-store/nosniff，安全UserView与详情一致。无total_count/私有position/credential字段，无跨页固定快照承诺。无Migration/依赖/权限/API Breaking，default404，回滚撤router保历史。

验收cursor篡改/跨Session/页size/key/family/恢复/无明文，真实多页同timestamp/权限撤销/License/五表无写及契约源错/错误静态；正式Key来源/Windows组合/性能/完整包/Gate待。

执行结果：WINDOWS_HTTP_INTERNAL_PASS。新增Auth owned `api/user_list_cursor.py`与`api/user_list.py`、create_app可选router；3cursor unit+5HTTP Contract，1273后端无失败（2既有权限跳过）。cursor实际随机化/无明文UUID/恢复原key后可读/改Session页size-family-key与篡改拒绝，错误不包含内部来源。

实际PG当前Session/Admin/独立合成cursor key：多页全部User与七同timestamp UUID正确稳定倒序/无重漏、DISABLED目标；篡改/改变页size/另一真实有效Session/非Admin/未知和实际撤Session/撤Admin角色/License拒绝五表完整無写；首次cursor并不授后续访问权。默认404、源对象不符或private exception静态503。A04内部分页与旧Windows详情/实际双Scope文件发布回归通过。

开发wheel690520字节，SHA256 7ea6b90a2c3fb2cde87aea6422c3ca0622caddb82009e30b69f7cd2e89ca9b9e，非可用安装包；无Migration/新依赖/角色/Breaking/升级动作、现0045兼容。撤可选router回滚保历史。正向License/cursor key合成，Windows尚未挂列表，正式Key供给/锁及索引性能/三平台/用户写生命周期/完整管理面/包/Gate待。Next AUT-04-A06：Windows独立user-list-cursor-v1只读KeyRef来源与临时Vault失密/备份恢复，随后A07装配。
