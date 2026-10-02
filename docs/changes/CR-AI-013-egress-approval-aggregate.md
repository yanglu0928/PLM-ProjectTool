# CR-AI-013：Egress Preview/Authorization 正式授权聚合

日期：2026-10-03；状态：依 V1.1 持续授权登记，0068～0069、内部服务、Task Owner、可选HTTP、Windows 11数据库组合、正式部署策略来源与显式写平台挂载已实施；关联冻结 API-03 `EGRESS_PREVIEW_CREATE/GET/AUTHORIZE/REVOKE`、DM-04、SC-01/02、CR-AI-011/012；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A04-P01～P09`。

缺口与证据：冻结 API 要求每个逻辑外发操作先生成不发送数据的 EgressPreview，再由 ProjectManager/CustomerManager 且满足部署策略的主体显式授权，并支持撤销。当前仓库只有 AITask 内不可变消费快照，无 Preview/Authorization 权威根、来源明细、批准或撤销历史、首次幂等结果。SC-01 的 AI-04 物理映射也仅列 Task/Invocation owned tables。消费快照不能反向冒充批准来源。

方案比较：A 以一张可变表同时充当 Preview、Authorization 和 Task Snapshot，会改写历史并混淆权威源/消费证据，否决。B 仅在应用内存中授权，无法审计、重放或跨进程验证，否决。C 新增 AI-owned Preview Root+不可变 SourceRef，Authorization Root 引用 Preview 并保存批准事实，撤销以状态与不可变事件/首次结果记录；Task 创建由 Owner 锁定 Authorization 并复制最小快照，选择C。

聚合边界：Preview 存 purpose/operation type、Provider/Config/Model/region、数据类别、不可变源引用、最小正文/查询范围的受控策略引用、记录/字节/Token/重试上限、payload/source fingerprint、有效期和风险代码，不存正文/Key。Authorization 只能从未过期 Preview 创建，只能缩小不能扩大，首版一 Preview 最多一个 Authorization；核心批准事实不可变，状态仅 `AUTHORIZED→REVOKED`。历史快照保留，Worker 未开始/下一批次重读当前状态。

权限：Preview Create 允许 ProjectManager/ImplementationMember/CustomerManager，Get 允许同项目受权成员；Authorize 仅 ProjectManager/CustomerManager 并额外通过可注入部署策略；Revoke 仅原批准者或当前 ProjectManager/CustomerManager。这些Operation需加入Project授权矩阵，不以AI Task权限替代。

迁移/回滚：以0068建 Preview/SourceRef，0069建 Authorization/撤销历史/首次结果；均为增量表。空表可物理降级，有历史后拒绝降级并采用向前修复或受控备份恢复。公开路由持续保持404，直到生产策略与信任源组合验收。

验证与切片：P02 只实现0068 Preview/SourceRef Schema与PG18升降/历史/不可变/跨项目/指纹边界；P03 实现0069 Authorization/撤销历史；P04～P06 分别实现Preview内部创建/读取、Authorize/Revoke与Task Owner投影；之后再做可选HTTP和Windows显式组合。无客户数据外发。

P02结果：已实现ORM/Migration0068。Preview 与 SourceRef 不可改写，Provider/Config/Region 及 AVAILABLE Model 由 PostgreSQL 守卫核验，集合项和语义来源必须唯一，Scope/Project、UUID、指纹、定量上限和时间窗口均失败关闭。Win11/PG18.6 空库升降重升、drift、负例与非空拒降 PASS；后端2111运行/3跳过、wheel PASS。无生产迁移、HTTP或外发。

P03结果：已实现ORM/Migration0069。Authorization 只能在当前 ACTIVE Provider/Config 和 AVAILABLE Model 上缩小 Preview 边界，并以 `AUTHORIZED@0→REVOKED@1` 单向迁移。延迟约束触发器强制批准/撤销与各自首次结果成套原子提交。Win11/PG18.6升降重升、已有Preview升级、drift、权限形状/越界/历史/非空拒降PASS；后端2111运行/3跳过、wheel PASS。首轮PL/pgSQL变量名和夹具引号问题已修正并全量重跑；无生产迁移、HTTP或外发。

P04结果：已实现 Preview 内部原子创建与同项目受权读取。创建链组合 License、Session/CSRF、Project 权限、Input Owner、当前 Provider/Config/Model 路由与版本化最小外发策略，原子落 Root/Source/Audit/Receipt；数据类别规范化后参与幂等指纹。Win11/PG18.6 真实原子链、重放/冲突/回滚/隔离 PASS，定向12、后端2116运行/3跳过 PASS，wheel SHA-256 `2160e09b852932c733add19ef0ee6e5bc2cad10749d0cb8848716ab89be03673`。首轮全量发现权限库存断言33未包含新操作，更新为35并全量重跑；无新Schema、HTTP、生产组合或外发。

P05结果：已实现 Project Authorize/Revoke 内部服务及仓储，强制ProjectManager/CustomerManager、可注入部署策略、Preview指纹与只缩小边界；批准/撤销各自将根、Audit、不可变首次结果和Receipt原子提交。撤销后原Authorize Key仍精确重放首次`AUTHORIZED@0`。Win11/PG18.6真实策略拒绝/缩小/回滚/重放/撤销/隔离PASS，定向17、后端2121运行/3跳过PASS，wheel SHA-256 `2b319bb6b3275317bd489aede16ed2e07041c6fdd41a2b42db4ed1e551afc1cd`。首轮夹具幂等键长度失败已修正并全量重跑；无新Schema、HTTP、生产组合或外发。

P06结果：已实现锁定当前Authorization、Provider/Config/Model路由与受信Task→Purpose的Owner投影，并正式满足AITask已有Port。撤销、过期、SourceRef指纹或Project不一致的新Task失败关闭；同Key已完成Task仅重放原Task/Job。Win11/PG18.6真实Task七类原子链与上述负例PASS，定向14、后端2125运行/3跳过PASS，wheel SHA-256 `ad6e4a017f425c8a58bf6fc1643add7bf2a70c87998869548ae9a360f5ce687c`。首轮合成时钟、次轮Job表名夹具问题已修正并完整重跑；无新Schema、HTTP或外发。

P07结果：已实现四条冻结路径的单一可选HTTP Router，严格执行Session/License应用链、Origin/CSRF/幂等/强ETag、精确JSON与安全投影；Authorize以`If-Match: "v0"`绑定不可变Preview版本，并以正文Preview指纹绑定具体内容，Revoke只接受Authorization v0。默认应用与当前生产组合四路径均404。合同5、后端2130运行/3跳过、wheel SHA-256 `e83a9586fe28193ccd4ca201e5665525e6c534bad0ec4f1c9afd1973e6209bd9` PASS；无Schema、依赖、真实PG HTTP组合或外发。

P08结果：新增只有完整显式依赖才可构造的Windows Egress组合工厂和读/写Session分流适配器；当前生产组合仍未挂载。Win11/PG18.6真实Session、Project角色、DocumentVersion Owner、Preview/Authorization/Audit/Receipt HTTP链及重放/隔离/撤销/License拒绝PASS。首轮发现P07将首次结果trace与当前重放trace错误比较导致503，移除该非业务等值要求并补合同后完整重跑。后端2130运行/3跳过、wheel SHA-256 `d1533684503661409b357c5a567091bd01acab693b4da4b0f2645e75f2fff093` PASS；信任/策略为合成注入，无外发。

P09实施前计划：现有Bootstrap只有Provider探针策略，不能作为逐次外发批准策略；选择新增最多16条非秘密、版本化`ai_egress_policies`，每项严格固定reference、operation/data category、TTL、记录/字节/Token/重试上限、风险代码、批准角色和数据区域。启动时转换为不可变Preview Registry与Approval Policy，缺失或畸形固定错误失败关闭。仅Windows显式写平台在正式License/Session/文档读取等既有信任源和该策略同时存在时挂载Egress Router；默认、登录和只读平台保持关闭。升级需受控编辑Bootstrap并重启；回滚移除策略并重启即可恢复404，既有授权历史保留。验证覆盖配置/YAML负例、策略允许/拒绝、三种平台路由矩阵和Win11隔离PG链；不连接Provider或外发。

P09结果：已新增严格非秘密Bootstrap策略源，转换为不可变Preview/Approval策略并仅在Windows显式写平台且配置非空时挂载；默认/登录/只读保持404。配置单元6、生产组合合同32、Win11/PG18.6使用Bootstrap策略的真实HTTP/数据库链、后端2136运行/3跳过、wheel `7eeafd306f5d45efd283fdc3c1d9919090afa585ece13f4737bf99d1be6cfe5e` PASS。无Schema/依赖/Breaking API/外发。
