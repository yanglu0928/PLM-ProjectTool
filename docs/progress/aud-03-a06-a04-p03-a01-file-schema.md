# AUD-03-A06-A04-P03-A01：内部FileObject用途/归属Schema

日期2026-09-26；Phase2；依据CR-AUD-002/ADR010、DEC-20260926-205。结果：限定Schema与普通入口隔离PASS，完整审计导出仍IN_PROGRESS。

## Changed / Files / Migration / API

增量0040新增FileObject usage_kind（旧行DOCUMENT默认）/owner_object_id（旧NULL）；仅AUDIT_EXPORT支持内部DEPLOYMENT+NULL项目或PROJECT+项目，必需PERSISTENT/非零owner/完整Hash与0～128MiB Size/application-x-ndjson MIME。DOCUMENT只GLOBAL/PROJECT且无owner，普通Document/Version/Upload/Parse范围未变。ORM与迁移常量一致，不重写0020～0039。

专用文件初态STAGED/版本0，来源身份/内容Hash/Size/MIME/Locator/Scope/Project/创建Actor时点固定；用途/owner对所有旧新行均不可转换。STAGED→AVAILABLE或FAILED，AVAILABLE→RESTRICTED，失败清理→REMOVED，版本单调，不复活、不删除/截断历史；可用时点有限且固定。状态元数据仍不是文件真实存在/内容证明，也不证明实际Export或Worker权限。

独立DocumentVersion/Upload引用触发器锁文件并要求DOCUMENT/NULL owner，同PROJECT也拒绝误绑；FileState/Publish普通Repository同样只加载DOCUMENT。保持旧函数/普通链路，不新增公开HTTP/角色/依赖。存储Adapter尚未扩展，新用途不能通过旧发布或静态目录下载。

down离线拒绝；先固定锁Document/Upload/Version/File，任何专用历史（含失败、尚未发布文件）拒绝0040降级。无专用历史可撤新增列/保护，旧行原值保持。只用独立UUID临时库验证，不操作生产；正式维护备份/停写/目标账户恢复仍待。

## Tests / Result

- `validation/aud-03-a06-a04-p03-a01-file-schema/verify.py`实际PostgreSQL18临时库：空库up/down/re-up、ORM parity、旧GLOBAL/PROJECT数据所有原列保留与默认用途、旧Document/Upload保留；正常同项目Upload与Version绑定可用；审计用途/Scope/归属/大小/MIME/时点/初态及身份拒变；同项目审计文件误绑明确由新用途保护拒绝；普通状态/发布入口RESOURCE_NOT_FOUND；限制不复活、delete/truncate拒绝；实际竞争down表写锁与含历史拒绝/版本及数据不变PASS。owner UUID合成、无真实Export/Lease或磁盘文件。
- 后端883项无失败，2项Windows符号链接权限条件跳过；新增3项ORM/迁移常量/默认与离线down无DDL测试。最后完整测试结果以本项提交前执行为准。
- 真实回归：DOC-03-A03-P02状态/event/Audit/receipt；P03本地合成bytes发布/恢复；DOC-03-A04-A04上传新旧版本/原子提交/回滚/恢复；AUD-03-A06-A03实际受理/当前权限/Lease/capture/真实取消与deadlock，均PASS。License仍合成，非正式生产安全证明。
- 0.1.0.dev0开发wheel成功：543252 bytes，SHA256 `490a55e6679038ed2ddf0c2da1c9d4a34479257ab2f029f4e737bdaeb280bd6c`，不是可用离线安装包。

## Known Issues / Next

FileObject owner是坐标不是根存在/权限证明；实际owned公共Port、生成尝试/唯一结果、私有文件写/Hash读回/不可覆盖提升/崩溃恢复、原子发布/取消/下载HTTP与再授权尚未完成。不把Schema可用等同可下载。P03-A02先Document owned公共元数据与受控存储；之后Audit尝试/结果Schema和真实Worker短事务发布。Gate3/质量/正式License来源/三平台与目标账户证明及完整交付Scope保留。
