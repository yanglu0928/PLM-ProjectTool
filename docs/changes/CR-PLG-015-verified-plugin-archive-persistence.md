# CR-PLG-015：已验签 Plugin 包正文的私有持久化

- 日期：2026-11-06
- 状态：已记录；PLG-04-A01 编码与 GitHub hosted 验收中
- 来源：Plugin 包导入/安装源码审计；承接 CR-PLG-005、CR-PLG-006、CR-PLG-007、CR-PLG-009、CR-PLG-014
- 适用基线：Gate 2 冻结 Data Model / DB Schema V1、PLG Package/Installation/Execution；CR-EXEC-002 交付顺序
- 执行边界：只用 GitHub hosted runner D 盘或云端沙箱运行代码和测试；不在用户本机/C 盘运行

## 发现与路线调整

当前 PLUGIN_PACKAGE_VERIFY Worker 读取隔离暂存 ZIP、重验 SHA-256、执行签名/Manifest/兼容检查，并将不可变元数据登记到 PostgreSQL；ZIP 正文只在内存中处理。PluginInstallationOwner 依赖独立 Host evidence adapter 证明“精确包已安装”，但产品目前没有受控的包正文持久化与对应验证适配器。故后续安装/运行链无法从持久的签名原文重新核验包内容。

当前 Output 路线已有 P34B Storage→FileObject→DocumentVersion→P33 的受控发布原语；继续接 Output Worker/Plugin subprocess 前，需要先补足 Plugin 包可重复验证的私有存储基础。本调整将下一单项切换为 PLG-04-A01：仅保存并核验已登记的签名 ZIP，解除其后续安全安装证据适配器的基础阻断。

## 决策与实现范围

1. 沿用现有 private data root，增加 Plugin package 私有、UUID 寻址的 ZIP 存储；拒绝用户控制的路径、符号链接/reparse point、硬链接、既存不匹配内容和越界尺寸。
2. 按原始签名字节写入，重验长度与 SHA-256；同包同字节重放幂等，已存在但摘要/内容不同则失败关闭。写入采用同卷原子、无覆盖策略，临时文件失败可安全清理。
3. Worker 只在 Package Registration 成功返回确切 PluginPackageId 后保存 ZIP，并在存储完成后才完成 Job。存储暂时失败可有限重试；登记重放必须保持现有同版本/同摘要语义。
4. 增加内部只读 package evidence adapter：读取私有 ZIP，验证其 SHA-256、签名、Manifest 身份/版本与登记快照相符；仅返回受控证据，不返回路径或包正文。
5. 不解压、不安装依赖、不启动插件、不开放 API、不修改 DB Schema/Migration、冻结 API/数据模型、默认 Worker 组合或 Product publisher trust 清单。现有正式 signer 为空时，生产包仍须失败关闭；测试仅用合成密钥与包。

## 差异、风险和回滚

- 本CR调整执行顺序，并新增内部私有文件存储/证据适配器；不改变 Gate 2 冻结基线语义，不改包注册状态。
- 文件系统和 PostgreSQL 不存在跨资源原子事务。Worker 在元数据登记成功后保存正文；若持久化失败，Job 可重试，登记为精确同包幂等重放；拒绝冲突并保留已有证据，不盲删包文件。
- ZIP 仍是攻击输入；实现必须限制读取大小并在证据检查时重做现有 ArchiveInspector 验签、ZIP envelope 和 Manifest 校验。
- 回滚时保持新适配器未装配，保留所有已写入包正文；只可通过另行受审的受控归档流程清理，不在本WBS执行删除。

## 验收计划

- 定向单测覆盖安全路径、原子无覆盖、同包幂等、既存错误字节拒绝、字节/摘要/签名/Manifest 篡改拒绝、恢复/清理失败关闭、Worker 顺序与有限重试。
- Hosted PostgreSQL 18.6 + 合成签名 ZIP 验证 Worker 从 staging 到私有正文，再重试精确完成且 metadata/Audit 不重复；生产 signer 为空不得误判为正式信任。
- GitHub hosted Windows Server 2025 D 盘执行后端全量测试/wheel、前端/build、父包/PG smoke/A17/A34/A35/A50既有链；P25 独立阻断按其状态报告。
- 最高结论为 PASS_SCOPE_LIMITED。无客户数据、外部 API/数据外发、插件执行、生产写入或不可恢复操作；不代表 Windows 11 实机、Gate、Pilot 或 Release 通过。

## 首轮 Hosted 验收偏差（2026-11-06，修复前登记）

GitHub hosted run [42063771396](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42063771396) 中，后端全量测试/wheel、前端/build、PG18 clean parent smoke、离线后端/父包组装、A35、P24与A50通过。A17 packaged flow 在合成验收代码直接构造 `PluginPackageImportWorker` 时失败：新增必需的 `archive_store` Port 未在该验证器构造中注入，日志明确为 `TypeError: PluginPackageImportWorker.__init__() missing 1 required keyword-only argument: 'archive_store'`。因此A17该次不通过，不能把对应的合成 Worker 链路视为已验证；产品 Windows composition 已接入同一 `LocalFileStorage`，后端全量通过。

修复计划：仅在 `validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py` 的合成验证器构造中注入 `archive_store=storage`，用临时data_root验证精确ZIP持久化；保留A17已有的合成信任、Job、DB与Edge断言，随后重跑完整GitHub hosted workflow。无产品行为/Schema/API变更。P25同run仍因initdb.exe退出0xC0000135失败，独立保持BLOCKED_DIAGNOSTIC。


## 第二轮 Hosted A17 验收偏差（2026-11-06，修复前登记）

第二轮 hosted run [42067292485](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42067292485) 中，后端全量/wheel、前端/build、PG18 clean parent smoke、A35/P24/A50和父包构建通过；A17 packaged flow已越过首次漏注入，完成合成签名包导入与Worker重试后，因旧验证器断言整个storage_root固定只有3个文件而失败。新增的正确产品行为会在登记成功后另存一个私有 Plugin ZIP，故旧总数断言漏算了该目录，报告“A08 worker smoke changed the staged package count”。该次A17未PASS；不是存储Hash或Worker断言失败。P25仍独立因initdb.exe 0xC0000135失败。

修复计划：保持原有3个上传/存储对象数量语义，额外要求受限 `plugins/packages` 目录下仅有1个归档文件，并逐字节核对它等于合成 `valid_archive`；保留所有现有Job/Audit/签名/重试断言，再重跑完整Hosted workflow。仅更新独立验收器，不调整产品行为和验收阈值。
