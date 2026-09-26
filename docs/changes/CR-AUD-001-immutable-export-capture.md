# CR-AUD-001：审计导出不可变意图与来源集合

日期2026-09-26；Phase2；执行依据V1.1及用户持续授权。实施前记录；原冻结64cdf09及0001～0036不改写。

## 缺口、选择及边界

冻结API-02需要异步受权审计导出，但当前只有追加aud_events和分页读取；时间窗口/游标不是MVCC快照。A01已记录迟提交和回填风险。新增Audit owned导出意图、capture header及来源成员，保持模块化单体/PostgreSQL任务。选择一次capture事务内单条INSERT SELECT固定来源，再封口；不选逐页查询追加、不复制原始请求/Session、不通过假Document实现文件归属。

请求固定原Actor、Scope/Project、起止时间/筛选/目的、策略/投影/格式及指纹；请求时间与实际capture时间分离。意图不可变，实际Job绑定及结果后续按公共Port另验；不用外模块内部表写入。Worker异步capture时重新核验实际权限，不声称POST时点快照。一个Export首个成功封口集合永久固定，失败事务整批回滚；后续Job generation复用原集合，不静默换集合。需要新集合必须新请求/ExportRef。

## 数据库设计与实施分项

1. A04-P01：先固定CAPTURE-MEMBERSHIP-V1规范摘要：有域分隔的SHA-256，逐条规范UUID和UTC微秒时间，以查询既有顺序(time,UUID)降序流入；禁止重复ID、逆序、无时区、零UUID，明确空集合摘要。只验证成员坐标，不是权限、来源真实性或文件Hash。
2. A04-P02：增量0037/ORM新增不可变Export意图、单一capture header、成员关联。Export保存服务器版本化意图且禁止更新/删除/truncate；capture唯一Export，成员(event,time,position)关联真实不可变aud_events且必须符合原Scope/完整筛选。禁止修改/删除/truncate。单次查询选择、封口及调用者UOW将分项实现，Schema须通过真实空/有数据升级/降级。
3. 事务提交完整性要求：header声明count与全部成员数一致、位置连续、排序正确、摘要与P01一致；空集合合法。提交后禁止再追加，成员插入必须锁header/Export；deferred约束及封口状态必须防止并发在封口后塞入。不能只依靠应用DTO或CHECK count>=0。最终Schema设计在P02实施前补充具体SQL/锁序并验证，尚未实施不得标PASS。
4. A04-P03：实际capture repository以真实授权调用方事务执行单statement INSERT SELECT，验证迟提交/回填/新增事件不会进入已封口集合，重试读同一集合，错误Scope/源缺失/空集合/故障全回滚。实际Actor权限、Job fencing、publish和下载在A05～A07完成，不以Schema验收替代。

## 风险、迁移、回滚及验收

增量DDL需要维护窗口与备份；AI仅使用独立UUID临时库，不操作生产。旧Audit/Job/业务数据不得回填、重标、删除或改写。down先按固定锁序锁新增表，再检查任何历史；有记录拒绝降级，不销毁导出历史；离线down禁止，无记录可撤新增结构。并发down写阻塞必须实测。未来任何格式/摘要版本变化使用新版本规则，保留旧读回，不拿当前常量重算旧历史。

成员量可能很大：应用摘要增量计算，不载全部事件正文；P01为拒绝不同时间的重复UUID保存O(n)标识集合，不能宣称常量内存或性能达标。后续实际capture须规定行数/空间上限，数据库唯一约束与SQL摘要可避免完整成员驻留应用，但必须验收规范一致性；capture SQL/排序/数据库摘要与空间上限的实际性能待验。超限明确失败，禁止截断后声称完整。文件Hash是输出字节完整性，成员摘要是固定来源坐标完整性，两者不能互换。无秘密字段/自由正文/路径/Session/Token进入成员。

验证要求：P01规范向量/空集/时区等价/排序/重复/腐损/字段绑定；P02 ORM parity、真实空/旧数据up/down/re-up、不可变/源归属/完整性/锁竞争；P03晚提交/回填/重试/故障。无公开API/角色/依赖变化；新增结果下载API如需扩展冻结合同另建CR。Windows11先验，Server2025未验，Debian暂缓但目标保留。Gate3/质量/UAT/完整包仍未通过。

当前状态：IMPLEMENTATION_IN_PROGRESS。不得将计划视为Schema或真实权限证据。
