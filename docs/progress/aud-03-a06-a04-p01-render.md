# AUD-03-A06-A04-P01：固定集合安全JSONL

日期2026-09-26；版本0.1.0.dev0；Phase2；结果SAFE_RENDER_INTERNAL_PASS。输出验证为内存字节，不是实际文件/Artifact发布。

## 编码前检查 / Changed / Files

输入JSONL_V1、AUDIT-EVENT-SAFE-V1、CAPTURE-MEMBERSHIP-V1及A03真实已受理/当前权限/Lease/seal；前置满足。实施前DEC-20260926-202。本项只解决固定来源的安全字节和清单。新增render_export.py合同/renderer、render_source.py owned逐批查询、7项unit与真实来源隔离验证；无新Schema/API/权限/依赖。

JSONL只含显式17个既有安全事件字段；不使用ORM/asdict全字段复制，不带actor_hint_digest/请求正文/Session/Worker/路径。UTF8无BOM，紧凑排序key、LF、UTC微秒，逐行完整写入；独立AUDIT-EXPORT-MANIFEST-V1保存固定意图/Scope/窗口/筛选/用途/版本、成员count/hash及输出byte_count/file_sha256。成员摘要证明坐标集合，文件摘要证明实际写入字节，两者不可混用。

owned source只JOIN已固定member与真实不可变Audit，按member.position排序，显式安全列yield_per128，finally关闭结果。不重查live集合。renderer逐条检查连续position、实际Scope/完整Spec筛选/窗口及安全Actor/code/typedRef格式，按原规范重新计算顺序/唯一/完整成员摘要，最终count/hash完全一致才返回清单。空集合零JSONL字节合法；未绑定/坏版本/超100000计数拒绝。

输出上限128MiB、单行16KiB，短写/异常/错项/源中途失败/超限不返回成功清单，不截断冒充完整。成功或失败均关闭source迭代器，不关闭caller-owned sink。可能已经写部分字节，必须由后续受控临时产物保持不可下载并清理；不声称数据库回滚能撤销文件I/O。摘要去重仍O(n)UUID内存，不把逐批SQL误说常量内存或性能已达标。

## Tests / Result

Windows11/Python3.13/PostgreSQL18独立库：实际用户/PM/Admin受权提交、原Queue/claim、Worker当前权限/capture，两Scope固定member接真实source渲染到内存；实际UNRESOLVED Audit带合成hint，输出与SQL投影均不含hint；仅正确Scope/筛选事件，精确file hash/size/count、manifest来源hash、empty成功、后续真实新事件不改旧字节。受权fixture显式核验当前RENDER权限、原Root/acceptance/pair、Lease/seal，read-only业务全表不变。此fixture不是生产渲染授权Service或文件生命周期。

7项unit：确定性/UTF8/LF/无BOM/UTC时区等价/空集、两类hash区分、绑定与版本、缺/多/重复/逆序/错位置、Scope/窗口/六筛选和不安全codes、短写/磁盘异常/源异常、小上限拒绝及source关闭/sink保留。小上限机制不是实际128MiB性能验证，合成磁盘异常不冒充真实目标盘容量演练。

后端880项无失败，2项既有Windows符号链接权限跳过；真实渲染来源与已受理Worker capture/撤权/取消/到期/40P01回归通过。License为合成Guard。开发wheel通过，SHA-256 `33057bd9945596fbfe414a6ae9369c6b270308246608ac23244a1055c57fb2fd`，非正式可用包。独立库finally清理，无客户数据外发或生产操作。

## Migration / API / Compatibility / Known Issues / Next

无Migration/API/依赖变化，需既有0039，升级无新动作；撤未装配renderer不删除历史。Server2025未验，Debian13暂缓但目标保留。当前pure renderer/source不鉴权/建UOW/授予交付，真正Worker RENDER checkpoint/临时产物/Hash落盘/发布/下载/崩溃清理/空间及目标账户ACL仍待。正式信任、质量、实际业务Owner、性能、Gate3/UAT/完整程序包未完成，Scope不缩减。

下一项AUD-03-A06-A04-P02：受控Artifact存储生命周期前置核查。已初步核查既有document/application/publish_file.py只接GLOBAL/PROJECT，不能把DEPLOYMENT审计重标GLOBAL或造Document绕过；后续按正式模型证据记录必要CR后实施。先核对FileObject/Artifact归属/状态/结果ref合同，再接真实临时写入、重新读Hash/长度、不可变发布与恢复。导出POST继续关闭。
