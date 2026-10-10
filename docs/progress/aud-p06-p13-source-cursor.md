# P06-P13-P03-A01：坏来源有界候选游标

2026-09-27/Phase2，CR-AUD-005。编码前：Jobs Application/Repository，新增内部ScanCursor/Reservation DTO，无API/权限/实体/Schema/依赖变化；前置只锁reservation通过。只实现候选游标及明确INVALID_EXPORT_REF分类，Audit/Step后续接线，不能报告坏来源整体已修复。

选择：新增scan_next，不改变旧peek/reserve。cursor为priority降序、available_at/JobId升序技术坐标，SQL参数化keyset，单次仅一个SKIP LOCKED reservation；一个cursor常数内存、不积累排除集。UUID格式/零值损坏只返回固定原因与JobId技术坐标；系统数据库/身份异常不转为坏源，原candidate不授权限。应用前后都核精确DTO。下一阶段持有游标推进，到尾只读复查/回绕；不可声称一次None代表全队列空，也不改变或终止坏Job。

验收：strict cursor/envelope/错误脱敏unit，实际双Scope多坏payload之间跨页走到正常候选，全程六表无写、旧reserve仍失败关闭，未授Claim/正文/成功。回滚撤新增Port保旧入口；无迁移/升级。风险：Root/pair/Lease错误分类、循环接线和诊断待，锁序deadlock实际验证仍待，完整产品/Gate未完成。

结果 PORT_INTERNAL_PASS：3新unit/1119项后端通过（2既有权限跳过），cursor严格类型/时间/整数范围、envelope绑定JobId及固定错误分类；backend异常拒绝，非INVALID_EXPORT_REF。实际PG双Scope按游标跨过两个坏候选（格式错误/零UUID）找到正常候选与当前末尾，每次仅一个reservation，全程六表不写。旧admission仍拒坏源，恢复本轮测试来源后实际发布/原并发与回滚发布回归通过。未接入Admission/Step/Loop，不把Port通过当整体隔离修复。

开发wheel632733 bytes，SHA256 `3b75c63330c29b24090da3c3f4205db6d8503fc42ec9c81707c0a1471a20b6a8`；无Migration/API/依赖变化。下一P03-A02原Root/pair明确SOURCE_REJECTED分类和正常栈游标推进/安全诊断，保持系统故障失败关闭、坏Job无写，随后Loop集成实际验证。CR/Gate/完整包未关闭。
