# 决策日志

## DEC-OUT-001：先完成 PLG-01 包登记基础，再接入 Output 生产注册（2026-11-02）

- 状态：已决定，待实施与云端验收
- 类型：L2 执行顺序调整
- 背景：OUT-01-A01-P03 已验证 resolver Port 边界，但生产树没有 Plugin 模块/Package registry，也没有 Output template/policy registry 或 Requirement/Solution/Plan 统一固定来源读适配器。继续直接实现 Output Create 会依赖合成或虚构的注册事实。
- 基线证据：冻结 DB SC-01 将 PLG-01 定义为不可变签名 PluginPackage，并列出 plg_packages、plg_manifest_operations、plg_manifest_dependencies、plg_package_verifications；SC-02将 PLG-01定位为 SEC-DEP，SC-03定义 plugin/version 和 enabled operation 唯一性；DM-04/ADR-005要求验证开发者签名、Manifest、Plugin API、OS、依赖、入口并保持 PluginService 子进程边界。当前应用树尚无生产 plugin owner/migration。
- 决策：将下一WBS从 Output 注册/来源适配调整为 PLG-01-A01：只实现开发者签名插件包的不可变元数据持久层（ORM、Alembic、up/down、空库/含历史验证）。该切片不导入包、不验证真实签名、不启用/执行插件、不调用外部服务，也不纳入私钥/客户数据。通过公开Port与失败关闭保持未安装/未验证包不可运行。
- 差异与影响：仅调整模块依赖顺序；API-03、DM-04、SC-01～03、Gate2冻结基线不变。数据库实现依照已冻结的PLG-01逻辑映射，字段与物理约束只采用冻结Schema候选允许的方式；若发现需新增列/实体或变更语义，先另建CR。
- 回滚：不改写已发布migration；只可追加down migration撤销空的包元数据表。若已有记录则禁止降级破坏，需先制定安全保留迁移。
- 验证：GitHub hosted Windows Server 2025 / D盘runner temp；合成无签名业务夹具；校验升级、降级与再升级、不可变内容保护、跨版本唯一性和写入口关闭；无本机/C盘代码执行。
- 后续：完成 PLG-01-A01 后，继续开发者包验证/Installation Owner，再回到 Output 的可信模板/策略/Source Owner 生产适配。禁止在这之前把P03合成Port当作生产注册或启用默认Output Create。


### DEC-PLG-001：Plugin实施顺序先完成无需发布根密钥的Manifest校验

- 日期：2026-11-03
- 状态：已记录并执行
- 决定：PLG-01-A02已完成合成信任Port上的纯Ed25519验签。当前仓库/开发工作台没有可核实的正式Plugin publisher root public key或撤销材料，故不能构造真实Package trust adapter，也不能用License信任锚或测试key冒充。按用户授权，先推进不依赖真实key的有界Manifest parser/入口路径校验（PLG-01-A03，CR-PLG-002）；发布者信任源另列后续WBS。
- 依据：ADR-005、DM-04、API-03、PLG-01-A02 PASS_SCOPE_LIMITED与本轮代码树/工作台只读检查。
- 影响：不改变Gate2冻结架构、安全要求或产品Scope；调整插件工作依赖排序。测试通过不构成发布者信任、包安装或可执行性。
- 回滚/恢复：若A03无法在不解包/执行或改变基线下完成，包导入保持关闭并转向其他不受阻碍开发项。


### DEC-PLG-002：先实现签名key ceremony，不在云端或用户本机生成真实Plugin私钥

- 日期：2026-11-03
- 状态：已记录并执行
- 决定：A03后最缺的是Developer Workbench插件签发密钥来源。复用既有License密钥仪式的隔离约束，开发独立Plugin Ed25519工具与空的公开key清单模板；当前只运行合成测试。由于用户要求本机不执行代码且真实私钥只能在Developer Workbench，真实密钥创建/口令/离线恢复不在本轮操作。
- 影响：顺序为A04工作台key ceremony、A05运行时包内公开清单Resolver/撤销、后续包导入。测试工具通过不代表生产key或trust已就绪。
- 回滚：若key ceremony或包边界验收失败，保持信任清单空、所有包导入关闭，转其他独立任务。
