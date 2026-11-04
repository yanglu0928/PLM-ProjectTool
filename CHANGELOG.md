## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- OUT-01-A01-P11按CR-OUT-008编码中：新增Plugin owner-backed能力只读端口与Output adapter；Output能力默认改为关闭，只有明确的enabled/trusted证据才可通过。托管PG18验证与全链结果待完成，不构成正式publisher信任或Pilot结论。

- PLG-02-A08按CR-PLG-013完成并以 `PASS_SCOPE_LIMITED` 关闭。Hosted run [41770188317](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41770188317) 13/13 jobs成功：后端3970 tests/wheel、前端测试/typecheck/build、PG18 Migration 0230与插件停用HTTP幂等/Audit回滚验收、20,180项非发行父包及A17/A34/A35/A50通过。父包SHA-256 `a49af407…b61dfae`。三轮失败及修复先记CR后处理。未在Win11设备实测、未启动正式产品API；Pilot/Gate 3/正式Release仍未通过。详见`docs/progress/plg-02-a08-installation-disable-result.md`。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A07按CR-PLG-012完成并以`PASS_SCOPE_LIMITED`关闭。Hosted run [41759878694](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41759878694) 13/13 jobs成功：后端3967 tests/wheel、前端/build、PG18.6 Installation详情读取、父包20,176项、A17/A34/A35/A50通过。父包SHA-256 `cd54f676…d9a6a7`。首次FastAPI测试断言失败已先登记CR、改成公开HTTP行为校验后全量通过。未启动产品API、未做Win11实机验证，Pilot/Gate/正式Release未通过。详见`docs/progress/plg-02-a07-installation-read-result.md`。下一项PLG-02-A08冻结PLUGIN_DISABLE HTTP入口编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A06按CR-PLG-011完成内部Installation操作停用Owner，PG18真实临时库验证多操作原子撤销、History/Audit、stale lock、失败回滚和精确重放。Hosted run [41755590662](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41755590662) 13/13 jobs、后端3,959 tests/wheel及完整父包/A17/A34/A35/A50通过；父包20,173文件SHA `cfe8f74d…a3d1072`。不接公开API/默认组合/插件执行。详见`docs/progress/plg-02-a06-installation-disable-result.md`。开始A07冻结Installation detail GET前置核查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A06编码前核查已通过并登记CR-PLG-011：冻结API存在人工PLUGIN_DISABLE，但现有Owner缺少显式停用命令；本项实现同事务操作撤销、DISABLED History/Audit与状态版本更新。真实宿主安装适配器、公钥/License正式信任缺口保留为独立任务。详见`docs/progress/plg-02-a06-installation-disable-precheck.md`。后端实现及云端验收待完成。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A05按CR-PLG-010完成并以`PASS_SCOPE_LIMITED`关闭。GitHub hosted run [41743782405](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41743782405) 13/13 jobs成功；后端3,955 tests/wheel、PG18.6 Migration 0229退役guard、父包/A17/A34/A35/A50链通过。父包20,173文件SHA `81b1425c…e016515`。A34显示产品启动仍被正式信任、DB凭据、ACL和TLS阻断。无公开API/默认组合/物理卸载/插件执行。详见`docs/progress/plg-02-a05-installation-retirement-result.md`。下一项PLG-02-A06编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A05编码前检查已通过：冻结状态已含RETIRED，现有逐操作History/Audit可表达人工退役；登记CR-PLG-010后实现内部终态Owner与Migration 0229。范围排除API、物理卸载和插件执行。详见`docs/progress/plg-02-a05-installation-retirement-precheck.md`。托管验收待完成。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A04按CR-PLG-009完成并以`PASS_SCOPE_LIMITED`关闭。GitHub hosted run [41738951137](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41738951137) 13/13 jobs成功：后端3,945 tests/wheel、前端/build、PG18.6 Migration 0228及有数据降级保护、父包PG smoke、A17/A34/A35/A50通过。两轮验证器偏差已先记CR再仅修正断言并完整重跑。未接公开API/默认组合/真实安装适配器，不安装/执行插件；Pilot/Gate/正式Release仍未通过。详见`docs/progress/plg-02-a04-runtime-revalidation-result.md`。下一项PLG-02-A05编码前检查。

- PLG-02-A04编码前检查完成：按冻结Installation/RuntimeValidation状态设计内部重验证Owner；不兼容时原子撤销操作启用、标记INCOMPATIBLE并记逐操作历史/Audit；从不兼容恢复只转DISABLED，须显式再启用。CR-PLG-009先行登记Migration 0228、回滚和托管验收计划；目前未改程序。详见 `docs/progress/plg-02-a04-runtime-revalidation-precheck.md`。用户本机不运行代码/测试。

- PLG-02-A03按CR-PLG-008以 `PASS_SCOPE_LIMITED` 完成：operation集合原子切换、历史安装状态维护、同事务Audit与逐operation不可变历史；migration 0227。GitHub hosted run [41728983860](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41728983860) 13/13 jobs成功，后端3,937项、父包PG18 smoke、A17、A34、A35、A50通过。首次PG verifier 17/3守卫计数偏差已先记CR，再更新为20/4并重验通过。无API/默认组合/物理安装/PluginExecution；Pilot/Release仍未就绪。详见 `docs/progress/plg-02-a03-installation-activation-result.md`。下一项PLG-02-A04编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- 已完成PLG-02-A03编码前检查并登记CR-PLG-008：实现Manifest operation子集按操作原子切换、旧/新Installation状态和同事务Audit；不接API/默认组合、不执行插件。计划revision 0227并用合成数据在GitHub hosted D盘验收。详见`docs/progress/plg-02-a03-installation-activation-precheck.md`。

- PLG-02-A02以`PASS_SCOPE_LIMITED`完成：内部安装事实Owner、PostgreSQL 0226最小INSERT守卫、原子Audit与PG18验证通过；GitHub hosted run [41721092729](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41721092729) 13/13成功，后端3932项和父包/A17/A34/A35/A50链通过。仅合成安装记录，无物理安装/默认组合/API/启用/执行/正式信任。两个迁移head断言偏差已先记CR再修复。详见`docs/progress/plg-02-a02-installation-owner-result.md`。下一项PLG-02-A03启用/状态变更Owner前置核查。

- PLG-02-A02第二轮run 41718480221后端全量、前端、PG18 sidecar与父包组装成功；Windows父包PG smoke发现PLG-01迁移验证器仍固定期待0225。偏差修复前已记CR-PLG-007；A35通过，A17结果尚未确认，A34未执行。

- PLG-02-A02实现提交0534e041新增受控Installation事实Owner、PostgreSQL repository、0226 append-only insert守卫和合成单测；首轮hosted run 41717001638后端3932项中一项旧migration head契约仍写0225，偏差先记入CR-PLG-007，待修正后完整重跑。未接API/默认组合、未部署真实包、未启用或运行插件。

- PLG-02-A02编码前检查通过有界范围：只记录由受控适配器验证的INSTALLED事实，不安装文件、不启用、不执行；数据库Owner开放需事务局部标记，明确不等于正式数据库身份隔离。无安装来源时失败关闭。详见`docs/progress/plg-02-a02-installation-owner-precheck.md`及CR-PLG-007。

- PLG-02-A01代码提交374fb1f6新增冻结Installation、EnabledOperation、RuntimeValidation三表ORM与PostgreSQL Migration 20261104_0225，包含精确Package/Manifest引用、重复启用唯一索引和Owner关闭/历史保护。GitHub hosted验收待完成。
- 本轮未接安装或启用API，未运行插件，也未创建真实信任/客户事实。

- OUT-01-A01-P10只读源码盘点完成（PASS_SCOPE_LIMITED）：PLG-01-A08只登记VERIFIED包，没有PluginInstallation/启用操作/正式运行信任事实Owner；Output Create继续失败关闭。
- 已先登记CR-PLG-007并完成PLG-02-A01编码前检查。下一项按冻结PLG-02表映射新增Installation/启用操作/runtime validation ORM与受保护Migration 20261104_0225；只在GitHub hosted D盘运行验收，本机/C盘不运行。
- 当前不实现安装/启用业务Owner或API，不执行插件，不创建信任或客户事实；云端全链验收后再更新本记录与STATUS。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）
- A08新增migration 20261103_0224和ORM staging metadata，保存package upload ID/hash/size、detached signature、signer key ref；新验证脚本覆盖append-only、TRUNCATE拒绝及有数据降级拦截，云端PG18验收待完成。
- A08 Job/Outbox首段由run [41602717998](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41602717998)全13/13 jobs成功。编码前复核确认后台验签还需持久保存detached signature/signer key reference；已先记录CR-PLG-006新增append-only暂存元数据表和0224 migration，Job payload仍只存ID/hash/size。
- 修正幂等键哈希域分隔符为固定ASCII冒号；前一替换未匹配转义文本，已记入CR-PLG-006。当前队列代码云端验收待本次提交。
- A08 Job/Outbox测试夹具已修正：无效值在测试函数中构造，避免pytest collection时提前异常；幂等键域分隔符规范化。产品逻辑未改，等待本次hosted验证。


- A08继续开发：新增Plugin package verification Job/Outbox queue contract与PostgreSQL repository；使用Deployment-scoped幂等键摘要，Job payload只含opaque upload ID、SHA-256及大小，Outbox仅引用Job和upload ID。相同key/相同内容重放原Job，内容不同冲突。
- 当前仍缺staging与Job协调/Audit/HTTP/Worker；定向测试与全链云端回归等待本提交运行，A08不标完成。
- 执行全部通过GitHub hosted runner；不在用户本机/C盘运行。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A07 已完成并以 PASS_SCOPE_LIMITED 关闭：hosted run [41593955795](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41593955795) 全13/13 jobs成功，后端3,909项及PostgreSQL 18真实登记/Audit原子性、失败回滚、幂等/冲突、0223迁移守卫通过。A07验收结果与CR-PLG-005已更新。
- 父子行写入顺序修复在同一事务先flush Package再添加子行；Audit/子记录失败仍整体回滚。代码未提前commit。
- 当前进入 PLG-01-A08 编码前检查，目标对齐冻结的异步签名包导入Contract。A07不包含公开HTTP/Job、ZIP持久化、安装或插件执行。
- 运行仅在GitHub hosted Windows Server 2025 D盘临时工作区，未在用户本机/C盘；测试数据为合成数据。正式信任、Win11实机、Gate/Pilot/Release状态不变。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- 路线纠正：A06后续路线先误指向已在2026-11-02完成的OUT-01-A01-P03，且该P03结果当时指向已完成的PLG-01-A01。保留历史记录，依据实际结果将当前WBS校正为PLG-01-A07；详见CR-PLG-005。
- PLG-01-A07编码前检查已完成：目标为只读验签/归档检查后的Package、Manifest operation/dependency和Verification结果原子登记；沿用0222元数据表，新增Owner migration仅允许INSERT并拒绝UPDATE/DELETE，保留TRUNCATE守卫。无公开HTTP/Job、ZIP内容落盘、安装、启用或插件执行。
- 限制：包内正式信任清单仍为空；hosted测试只用合成key/包。A07不让测试信任源进入默认生产组合，Pilot/Gate/Release不变。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 全链路验收完成：GitHub hosted Windows run [41582564698](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41582564698) 13/13 jobs成功；后端3,902项/wheel、前端、PG18/pgvector、父包、A35 handoff、A17包内PlanVersion flow及A34替换/显式恢复演练通过。A06只读ZIP/Manifest/整包签名联合检查为PASS_SCOPE_LIMITED。
- 偏差追溯：首轮Windows ZIP/EOCD fixture错误与第二轮既有随机UUID误报均先记录、后修正并完整复验，详见CR-PLG-004及A06结果文档；未改产品逻辑来消除随机误报。
- 兼容性/升级：没有新增DB/API/Migration或外部包格式升级；不执行插件导入、安装或运行。
- 限制：仅GitHub hosted Windows Server 2025合成验证；未形成Windows 11设备验收、正式信任、Gate、Pilot或Release证据。下一项按CR-EXEC-002为OUT-01-A01-P03。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 第二轮hosted run [41581853457](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581853457) 的A06定向归档/EOCD用例通过，但后端3,902项中1项既有capability source proof单测因随机UUID偶然包含“cccc”而误报敏感repr，导致wheel/父包/A17/A34跳过。根因与修正前记录见CR-PLG-004/A06检查；先固定测试fixture再跑全量链。A06尚未PASS。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 首轮hosted run [41581198290](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581198290) 后端3,902项中1个测试错误、1个失败；根因为Windows ZIP测试写入器规范化反斜杠夹具与EOCD测试字面量转义错误，检查器的对应负向断言未按预期执行。失败与修正计划先记入CR-PLG-004/A06检查；没有证据显示产品安全绕过，后端失败后wheel/父包链被跳过。
- 状态：A06未通过，正在先修正纯测试夹具后云端重跑。所有运行仍限GitHub hosted runner，不运行用户本机/C盘。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A05 新增只读包内发布者公钥Resolver并适配现有Plugin签名Verifier。hosted run [41579068045](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41579068045) 13/13 jobs成功，后端3,895项、wheel、前端、PG18、父包及A35/A17/A34链通过。空正式key manifest继续拒绝所有真实发布者签名。
- 兼容性：仅GitHub hosted Windows Server 2025；不在用户本机/C盘运行。没有Win11设备验收。
- 升级说明：无ORM/Migration/API；新Resolver只读取包内公开资源，无插件导入/安装/执行。
- 已知限制：仅PASS_SCOPE_LIMITED；无真实发布者key、动态撤销源或生产签名包。Gate3/Pilot/Release状态不变。下一项先固定ZIP envelope和无落盘安全读取合同，见CR-PLG-004。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A04 完成 Developer Workbench 插件 Ed25519 key ceremony 工具、空发布者清单资源及回滚恢复。首轮run [41575141107](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41575141107) 全13 jobs成功后，独立代码审查发现失败回滚残留ACTIVE清单，已先记CR并修复；修复提交 aaef9391b0a98b8b202e5140f7266b8a0a8841a0 的 hosted run [41576991044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41576991044) 全13 jobs成功。后端3,889项、仪式5项、wheel、前端、PG18、父包、A35/A17/A34通过。
- 兼容性：只在 GitHub hosted runner 执行；工作目录/测试key使用 runner D盘临时环境。不在用户本机/C盘运行。
- 升级说明：无DB/API/Migration；wheel包含空公开信任清单。真实签发私钥不生成、不上传。
- 已知限制：A04仅PASS_SCOPE_LIMITED；真实密钥仪式、离线备份恢复、运行时信任、Windows11实机、Gate/Pilot/Release均未由本项证明。详细见 docs/progress/plg-01-a04-key-ceremony-result.md。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 完成只读版本化Manifest parser和路径校验；hosted run [41573036147](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41573036147) 13/13 jobs成功，后端3,889项全通过。此前3次路径断言失败经追查是测试helper直接传dict给bytes parser，已在结果文档中更正测试盲区和失败根因。
- 兼容性：仅GitHub hosted Windows Server 2025与合成Manifest；无本机/C盘运行、无Windows 11实机验收。
- 升级说明：内部代码更新，无DB/API/Migration；不生成安装包。
- 已知限制：不含ZIP解压、正式发布者信任、包导入/安装/执行。A03为PASS_SCOPE_LIMITED，Gate3/Pilot/Release仍NOT_READY。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 第三次 hosted run [41572410413](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41572410413) 发现12个入口路径子例由测试fixture helper误传dict导致，目标字段规则没有被测到。根因已记入CR-PLG-002/前置记录，修复测试后重跑，A03保持未通过。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 第二次 hosted run [41571779122](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41571779122) 仍在入口路径错误码专项断言失败；首次修正未闭合问题。已在CR-PLG-002与前置记录追加复现，暂停PASS结论并进行更精确定位。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 首轮 hosted run [41571211968](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41571211968) 后端3,888项中1项入口NUL错误码断言失败；输入已被拒绝，尚未出现路径穿越绕过。已在编码前检查/CR-PLG-002中记录，修复后重新跑全链。
- 兼容性：仅GitHub hosted Windows Server 2025；未在用户本机/C盘运行。
- 已知限制：A03验收尚未通过，不能标为可安装/可执行；后续包/A17/A34依赖链被跳过。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG任务顺序已记录：正式Plugin发布者根公钥/撤销源尚不存在，不能将合成验签提升为生产信任；先做独立版本化Manifest parser和入口路径校验（PLG-01-A03），其格式已在 [CR-PLG-002](docs/changes/CR-PLG-002-plugin-manifest-v1.md) 固定。生产信任源后续单独建设。
- 兼容性：开发分支文档/实现；Cloud runner D盘运行，用户本机未运行程序。没有Windows 11设备结论。
- 升级说明：Manifest parser无Schema/API迁移；未安装产品。
- 已知限制：A03不验签/解压/执行，不使Package进入VERIFIED；真实Trust root尚待。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A02 按 CR-PLG-001 增加纯Ed25519 detached插件包验签器：对完整包字节计算SHA-256并绑定签发者key-ref，密钥由独立Trust Port提供；8项定向单测及全链 hosted run [41569062762](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41569062762) 13/13成功。
- 兼容性：GitHub hosted Windows Server 2025与合成密钥；未在用户本机/C盘运行，也无Windows 11新实机验证。
- 升级说明：内部开发分支代码，无数据库/API变化；没有产品安装包或生产包升级。
- 已知限制：生产公钥信任/撤销源、包导入、Manifest兼容校验、安装和执行尚未接入；结果PASS_SCOPE_LIMITED，Gate 3/Pilot/Release仍NOT_READY。详情见 `docs/progress/plg-01-a02-signature-verifier-result.md` 和 `docs/changes/CR-PLG-001-plugin-package-signature-format.md`。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A01 已增加插件包不可变元数据持久层；GitHub hosted run [41566771430](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41566771430) 全13 jobs成功。当前转入 PLG-01-A02；由于ADR-005未指定签名算法，先登记 [CR-PLG-001](docs/changes/CR-PLG-001-plugin-package-signature-format.md)，冻结 Ed25519 与完整包摘要签名格式，再开始编码。
- 兼容性：仅云端 Windows Server 2025 runner；无本机/C盘执行、无Windows11新实测。
- 升级说明：仅开发分支规则/代码计划，不生成安装包。
- 已知限制：真实发布者信任源/撤销源缺失；A02合成测试不能作为正式信任、Gate、Pilot或Release证据。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A01 新增 PluginPackage 不可变元数据 ORM 和 migration `20261102_0222`，包含 package、manifest operation/dependency 与追加式验证记录。Hosted run [41566771430](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41566771430) 13/13 jobs成功，后端/前端、PG18 schema、候选包、A35/A17/A34链路均通过。
- 兼容性：仅 GitHub hosted Windows Server 2025 与隔离PG18合成数据；临时文件在runner D盘。没有在用户本机/C盘运行代码，也没有Win11实机验收。
- 升级说明：仅开发分支数据库增量；尚未在用户或生产数据库安装，不是发行/安装包。
- 已知限制：签名验证、正式发布者信任源、包导入/安装/执行和Output registry尚未实现；PLG-01-A01为PASS_SCOPE_LIMITED，Gate 3/Pilot/正式Release仍NOT_READY。详情见 `docs/progress/plg-01-a01-package-registry-schema-result.md`。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- OUT-01-A01-P03 增加可信固定来源 Context resolver：通过显式 Source/Template/Policy/Plugin Operation Ports 校验精确版本、项目授权、审核态和类型关联，只按策略白名单输出受限Context及稳定fingerprint；缺定义/跨项目/未批准状态/不可信操作失败关闭。无Migration/API/Router/Plugin执行。
- 首轮新增深度负向测试夹具未超过限制导致run [41416698193](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41416698193)后端套件失败；已在CR-OUT-003记录后加深夹具。修正提交[run 41417503109](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109)全13 jobs成功，含后端全量/wheel、前端、PG18重建、父包、A50 Edge、A17 Edge/HTTPS/PG、A34隔离替换恢复。
- 兼容性：仅GitHub hosted Windows Server 2025，所有临时运行目录使用D盘runner temp；不在用户本机/C盘运行。本次未做Windows11设备验收。
- 升级说明：包含P03代码的内部非发行父包候选artifact [13129330605](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109/artifacts/13129330605)，不作为安装/发行包，不执行产品安装或服务启动。
- 已知问题：当前仍无生产Template/Policy/Plugin Operation registry和Requirement/Solution/Plan resolver adapters，实际生产Output Create保持不可用/失败关闭。P03为PASS_SCOPE_LIMITED；Gate3、Pilot、正式Release仍NOT_READY。详情见docs/progress/out-01-a01-p03-trusted-resolver-result.md。
- 偏差与修正：详见docs/changes/CR-OUT-003-output-trusted-resolver-boundary.md。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- OUT-01-A01-P02 已完成OutputRequest同事务Owner、幂等回执、Jobs-owned Outbox入队与可逆migration `20261102_0221`。hosted PR run [41413844603](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41413844603) 全13 jobs通过；PG18.6合成验收含并发合流、冲突、故障回滚、快照不可变及含历史的降级/重升级。仅PASS_SCOPE_LIMITED，不含公开HTTP、真实来源/模板注册、插件/Artifact、客户数据或Win11/正式发行验证。详情见 `docs/progress/out-01-a01-p02-create-idempotent-owner-result.md`。

- OUT-01-A01-P01 新增冻结 DM-04/API-03 语义下的 OutputRequest 与不可变 OutputContextSnapshot ORM/迁移，revision `20261102_0220`；CR-OUT-001 按本切片证据验证关闭。hosted run [41405621292](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41405621292) 全13 jobs成功，后端3,853项全量测试通过；PG18.6 空库升级、降级/再升级、既有合成数据升级通过。父包SHA-256 `a3062a6311d20c6d63f93dea6ce13b58136b8c0c45115e93345d45708cb3e1ea`，20,126文件。
- 兼容性：仅GitHub hosted Windows Server 2025，临时工作目录/数据位于D盘runner temp；没有在用户本机C盘运行。未进行本轮Windows 11设备验收。
- 升级说明：仅内部开发分支增量迁移，未在任何用户/生产数据库安装。
- 已知限制：Output业务Owner尚未完成，新表保持写入关闭；未实现HTTP、Plugin、Artifact或端到端生成。未启动产品服务、未使用正式License trust、未处理客户数据；Gate 3、Pilot、正式Release仍NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A50-E01 在 GitHub hosted Windows Server 2025 的 headless Edge 上完成待办来源导航专项合成验收；run [41396427656](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41396427656) 全13 jobs成功。固定版本目标在第2页精确定位；HUMAN来源不产生定位API/虚构锚点；跨项目和失效来源失败关闭并保留Action详情。后端3,850、前端2,075/200文件、typecheck/build及同run父包、PG18/pgvector、A34、A17链路均通过。父包SHA-256 `238d6a53db0f5e7e9955020e6caeecbb5a8d445a0f2025eadca081638ff83237`，20,122个payload文件。
- 兼容性：仅GitHub hosted Windows Server 2025，临时数据/工作目录在D盘runner temp；不是Windows11实机测试。没有在用户本机运行程序，无客户数据或外部API调用。
- 升级说明：生成非发行内部候选Artifact；没有产品安装/服务启动，不含正式License信任。
- 已知限制：状态仍为PASS_LIMITED；Gate 3、Pilot、正式Release及正式信任前置仍NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A50 实现交接待办按需解析固定来源并跳转到精确问题卡片；新增可选只读 source-location 子资源，冻结 Action GET 与数据库结构不变，无 Migration。Hosted run [41391544470](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41391544470) 全12 jobs成功：后端3,850项、前端2,075项/200文件、typecheck/build通过；父包20,122文件 SHA-256 `24f37f60…f8dc6db3eda`，PG18.6/pgvector0.8.6临时生命周期、A34隔离替换恢复、A17 packaged PlanVersion Edge/HTTPS/PG 29 API通过。A50结果为PASS_LIMITED，专项待办导航 Edge 验收留至A50-E01。
- 兼容性：本轮仅GitHub hosted Windows Server 2025；未进行新的Windows 11设备验收。没有在用户本机运行代码。
- 升级说明：非发行候选内部功能增量；无数据库迁移，不构成安装/升级包，不启动产品服务。
- 已知限制：A17浏览器测试覆盖PlanVersion，不覆盖A50来源导航；正式信任及Pilot/Gate/Release仍NOT_READY。

# Changelog

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A49 在可读就绪报告置顶第一条待办，并以JSON字段复用有序动作首项；hosted run 41388401825 全12 jobs成功。零待办仍要求独立核验，授权值全false。父ZIP SHA-256 `07d74e91…f49c88920c`、20,122 files；A17/A34/PG通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；无新Windows 11实测。
- 升级说明：仅内部非发行诊断候选更新，没有产品安装/升级。
- 已知限制：正式信任、DB身份、服务ACL、TLS和法务放行缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A48 按固定依赖顺序输出信任、DB凭据、服务ACL、TLS四组readiness待办；hosted run 41386839114 全12 jobs成功。零blocker完整登记仍需独立核验且不授权；候选ZIP SHA-256 `8e642dc1…aa48948`、20,122 files；A17/A34/PG通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025，无新Windows 11实测。
- 升级说明：仅内部非发行诊断候选更新；未安装/升级产品。
- 已知限制：正式信任/DB/ACL/TLS/法务条件未满足，Pilot/Gate/Release保持NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A47 为9个 readiness 缺项增加静态责任角色和下一步动作；hosted run 41383869172 全12 jobs成功。父包ZIP SHA-256 `1db6e14e…1452d370`、20,122 files；完整不授权、未知/秘密输入不回显；A17/A34/PG组合通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；没有新的 Windows 11 实机验收。
- 升级说明：仅内部非发行候选诊断工具更新；未安装产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS与法务放行缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A46 为 readiness PowerShell 入口新增可选中文可读模式；GitHub hosted run 41382282100 全12 jobs成功。不完整/完整/无效三态通过，完整不授权、哨兵不回显，默认JSON保持兼容。候选ZIP SHA-256 `c9b6d945…7164d3`、20,122 files；A17/A34/PG18组合通过，PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；无新的 Windows 11 实机运行。
- 升级说明：只更新内部非发行父包诊断工具；没有安装/升级程序。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS、法务放行未满足；Pilot/Gate/Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A45 为包内就绪报告增加9个缺项的静态中文填写指导；hosted run 41378263123 全12 jobs成功。候选ZIP SHA-256 `e2858a6b…0256ca`、20,122 files；完整登记不授权、非法值不回显、manifest不变。A17/A34/PG组合通过，结果 PASS_LIMITED。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅更新内部非发行候选诊断工具；未安装或启动产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS和法律放行仍缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A44 将非秘密 Pilot 就绪报告/模板和 PowerShell 入口纳入 Windows 候选包，并在 hosted run 41376505925 完成12/12组合验收；9项缺项正确显示、完整登记仍不授权、非法输入不回显。父包SHA-256 `8e3e4e37…f801d`，20,122 files；A17 29 API/A34恢复通过。详情见 [A44结果](docs/progress/plt-pkg-01-a09-p51-a44-readiness-tool-bundling-result.md) 与 [run](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925)。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅内部非发行包内容变化；没有产品安装/服务升级。
- 已知限制：正式公钥/License/DB身份/服务ACL/TLS和法律放行仍缺；Pilot/Gate/Release保持 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A43 从固定公开输入云端重建当前 PR 源码的 Windows 父包候选；12/12 hosted jobs 成功，父包 ZIP SHA-256 63ed5c8d…05a7a、20,118 个文件。同run完成暂存、PG18/pgvector、A17 29次API合成业务流和A34隔离替换/手动恢复演练。详情见 [A43 结果](docs/progress/plt-pkg-01-a09-p51-a43-hosted-rebuild-result.md) 与 [run 41370951575](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370951575)。
- 兼容性：仅GitHub hosted Windows Server 2025；不能推定Windows 11新运行兼容。
- 升级说明：生成仅限内部验证的临时候选artifact，不是安装器或正式Release；未在本机安装/运行。
- 已知限制：正式信任、License、数据库凭据、服务ACL与TLS前置仍缺，应用/服务未启动，Pilot/Gate/Release保持NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A42 将包外 Authenticode 指纹校验接入候选暂存CLI。安装器与指纹成对提供；校验失败时ZIP暂存目标不创建；成功收据仅标记 TEST_ONLY。GitHub hosted Windows run 41370763918 的26项定向回归和A35集成通过，PASS_LIMITED。
- 兼容性：仅在 GitHub hosted Windows Server 2025 验收；不推定 Windows 11 实机兼容。
- 升级说明：仅开发/云端验证工具更新，没有安装包升级或产品安装。
- 已知问题：真实产品发布者证书/固定指纹及安全安装执行路径仍未建立；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A41 新增 Windows Authenticode 只读校验器，要求包外签发者指纹；未签名、签名异常、指纹不匹配或调用失败均拒绝。GitHub hosted Windows run 41370436650 的24项定向回归及真实签名/未签名文件验证通过，PASS_LIMITED。
- 兼容性：只在 GitHub hosted Windows Server 2025 验证；不推定 Windows 11 实机兼容。
- 升级说明：仅内部验证工具；没有改变候选父包，不安装或升级已有程序。
- 已知限制：未提供真实产品代码签名证书/外部正式指纹，验证结果标记 TEST_ONLY；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A40 新增 hosted 离线候选暂存CLI与专用 GitHub Actions 验收；19/19 定向测试通过。A35 父包 SHA-256 `94700239…e2f2`，20,119 payload files 验证并暂存；A38 保持5项启动阻断，包内诊断 `BLOCKED/exit 2`。验收 run [41369734304](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41369734304)，结果 PASS_LIMITED。
- 兼容性：验收运行于 GitHub hosted Windows Server 2025、D盘 runner temp；不构成 Windows 11 实机兼容证据。自2026-11-02起没有在用户本机运行程序。
- 升级说明：仅内部开发工具/云端workflow变更；没有生成可安装升级包，不触碰已有安装。
- 已知问题：正式产品公钥/License信任、数据库凭据身份、服务账户ACL、TLS材料及包外可验证代码信任仍未齐；未安装、未启动服务，Pilot/Gate/正式Release保持 NOT_READY。

- 2026-10-30 P51-A39：只读核查A35真实父包确认根目录无安装/升级入口，只有manifest、hash清单；payload仅含说明、诊断和fail-closed launcher。A34/A35隔离恢复不等于安装或重启。新增CR-PKG-012，在持续授权下推进离线分阶段安装入口，不越过正式信任/服务/TLS/DB门禁；本轮未解包、安装或重启。见A39结果及CR-PKG-012。
- 2026-10-30 P51-A38：新增只读 Pilot 就绪诊断器，合并非发行父包 manifest 的固定阻断字段与A37登记完整度。即使所有标志为真且登记完整，也恒定返回pilot_ready=false/launch_authorized=false/release_eligible=false/legal_clearance=false。Windows 11 Python 3.13合计12/12测试通过；用A35父包SHA 94700239...e2f2内存读取manifest与空模板完成只读集成。无服务/DB/凭据访问或C盘运行，Pilot/Gate/Release不变。详见 `docs/progress/plt-pkg-01-a09-p51-a38-readiness-report-result.md`。
- 2026-10-30 P51-A37：新增 Windows Pilot 非秘密输入登记器、空白JSON模板及操作约定。只接受固定格式的公钥SHA指纹、License/证据引用、固定DB Credential Manager目标、Windows服务身份引用和TLS元数据；未知字段/无效值拒绝且不回显。完整登记也只标记需独立验证。Windows 11 Python 3.13合成测试6/6通过，未读密钥或接入启动放行。PASS_LIMITED，Pilot/Gate/Release不变。见 `docs/progress/plt-pkg-01-a09-p51-a37-input-register-result.md`。
- 2026-10-30 P51-A36：盘点 Windows 11 Pilot 正式信任前置自动化。固定公钥/License、限定数据库凭据、服务身份/ACL、真实TLS链尚缺实际输入；现有工具只提供缺项守门或材料到位后的部分检查。无前置被虚假关闭，Pilot/Gate/Release仍NOT_READY。Windows 11本机启动前置单测2/2通过；另一模块导入依赖未装，不写C盘安装。详见 `docs/progress/plt-pkg-01-a09-p51-a36-windows11-trust-prerequisite-audit-result.md`。
- 2026-10-30 P51-A35：Windows 11 Home 中文版 build 26300 实机 D 盘隔离完成两份父包初装/替换、失败隔离和显式恢复；旧/新20,119项、4类持久标记保留，16/16分块Artifact摘要复核，launcher继续BLOCKED/exit 1且无service/API/listener。hosted run 41026213054全12 jobs success；只PASS_LIMITED，不代表正式安装、其他Windows 11 edition或Pilot/Gate/Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a35-windows11-package-rehearsal-result.md`。
- 2026-10-30 P51-A34：hosted Windows Server 2025 D盘隔离完成父包初装、整包替换、失败候选隔离及显式手动恢复；旧/新候选各20,119项，4类持久数据标记保留。launcher持续BLOCKED/exit 1，无service/API/listener启动。GitHub Actions run 41020308619全11 jobs成功，A34证据Artifact SHA-256 `d284a29542f01825da7375151449030c754f7a8cf63a48c37f897f9758b5e325`。A34仅PASS_LIMITED；不代表Windows 11实机安装、正式信任、Pilot、Gate或Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a34-cloud-install-rehearsal-result.md`。
- 2026-10-30 P51-A33：父包启动入口在受信任前置缺失时复用只读诊断并输出六项BLOCKED JSON，仍以exit 1拒绝启动；缺诊断脚本/损坏manifest回退、无listener、A29/A30篡改矩阵及同run PG18/A17均通过。Hosted run 41008231772全10 jobs success；后端3,849项；A17 PlanVersion 29 API调用。父包SHA-256 104b8559...55cf6。采用.NET流式SHA-256兼容PowerShell 5.1；多轮偏差及PR #60远端并发合并事实已记录。无API/Schema/Migration变化；仅PASS_LIMITED，Pilot/Gate/Release仍NOT_READY。详情见 `docs/progress/plt-pkg-01-a09-p51-a33-launcher-feedback-result.md`。
- 2026-10-30 P51-A32：精确将父包级payload/check-startup.ps1排除在当前应用布局投影之外；全源清单仍校验、其他未知文件仍拒绝。新增投影单测5/5、后端3,849项通过；A31父包诊断+PG smoke和A17 PlanVersion Edge/HTTPS/PG（29 API）同run通过，详情见A32结果文档。无API/Schema/Migration变化；候选仍非发行，Pilot/Gate/Release NOT_READY。
- 2026-10-30 P51-A31：hosted父包实际解包根目录README诊断命令专项PASS_LIMITED；清洁父包20,119文件，SHA-256 10eca56d...57acc6，命令固定BLOCKED/exit 2/无监听。后续A17组合检查发现新增父包级诊断脚本未列入应用投影白名单，已登记P51-A32；此workflow整体未全绿。无API/Schema/Migration变化；Pilot/Gate/Release仍NOT_READY。
- 完成 P51-A28 受限 Windows 启动协调器正式信任/凭据/ACL/TLS前置显式守门；hosted run 40981581644全10 jobs通过。真实父包仅固定拒绝，A17 PlanVersion Edge/HTTPS/PostgreSQL闭环PASS_LIMITED；不代表Windows 11设备或正式发行。
- 完成 P51-A29 启动manifest严格类型检查及7种篡改清单hosted负例；run 40983612763的PG smoke job通过，stdout为空、无listener、源manifest未变。未接入正向生产启动。
- 兼容性/升级：仅内部非发行候选及启动诊断守门变化，无API或数据库迁移；不得覆盖已有安装。
- 已知限制：正式产品公钥/License trust、服务账户数据库凭据/ACL/TLS配置与Windows 11设备安装升级仍未齐备，Pilot/Gate/Release保持NOT_READY。
- P51-A30新增父包只读启动前置诊断命令：仅读非秘密manifest，输出BLOCKED及缺少项，不启动服务或读取凭据/私钥。hosted run 40988858723的D盘父包PG smoke验证当前报告及4类篡改输入，A29七类守门矩阵同轮通过。
- 版本/升级：仅非发行包增加一个PowerShell诊断脚本与README说明；无API/Schema/Migration变化，不对已有安装执行升级。
- 已知限制：该命令只说明当前候选未具备的启动条件，不会使包具备正式信任/安装资格；Pilot/Gate/正式Release仍NOT_READY。



## Unreleased · 2026-10-30（内部云端验证，不是发行版本）

- 修正 PlanVersion 固定历史读取 Client 对浏览器原生 fetch 的接收者调用方式；增加 this/globalThis 回归覆盖。没有改变冻结 API、数据库、Migration、权限或状态机。
- 完成 A17 父包中 PlanVersion Edge/HTTPS/PostgreSQL 合成闭环 hosted 验收；详情见 [A27 验收记录](docs/progress/plt-pkg-01-a09-p51-a27-planversion-cloud-result.md) 与 [GitHub Actions run 40841364426](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40841364426)。
- 兼容性：本次前端修复不要求数据库或API升级；hosted Windows Server 2025 验证不是 Windows 11 设备验收。
- 升级说明：仅内部代码候选，不能作为正式安装包；后续同源候选应从该提交重新构建，不对既有安装执行升级。
- 已知限制：manifest 保持 release_eligible=false/legal_clearance=false；正式License信任、服务账户凭据/TLS、离线安装升级和 Windows 11 实机验收仍未完成，Pilot/Gate 3/正式Release NOT_READY。


## Unreleased · 2026-11-04（云端验证待完成，不是发行版本）
- A08新增Windows Plugin package verification Worker CLI组合入口：显式读取Bootstrap/当前账户数据库凭据，检查数据库schema与License后执行一次处理或常驻轮询，并登记诊断进程角色。Worker不安装、不执行插件；未接默认API，也未自动安装服务。
- 新增Worker诊断角色测试。该提交的后端/前端回归、wheel、Windows父包和集成验证待GitHub Actions；A08仍未关闭，Pilot与正式Release仍NOT_READY。
- 所有代码与验证均计划在GitHub托管runner执行，不占用用户本机C盘。


## Unreleased · 2026-11-04（A08 Worker CLI云端结果与集成验收）
- Worker CLI/诊断角色提交 `bcb69866` 的GitHub hosted workflow [41673992094](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41673992094) 全13 jobs成功；不代表新加入的PG18 Worker端到端smoke已通过。
- 新增PG18真实Worker claim/fencing、无信任签名失败关闭、synthetic Ed25519有效包只登记元数据、短暂staging故障与bounded retry恢复的验收代码，并新增Windows入口模块导入保护。验证待本轮hosted workflow。
- 全部运行保持在云端，不使用用户本机C盘；无客户数据外发。


## Unreleased · 2026-11-04（PLG-01-A08受限完成）
- A08 Worker CLI与PG18端到端smoke提交 e37e668e 已通过GitHub hosted workflow [41678551589](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41678551589) 13/13 jobs。任务结论PASS_SCOPE_LIMITED；无插件执行、真实publisher trust/Windows 11设备验收。Pilot/Gate/正式Release仍NOT_READY。
- 下一项转为OUT-01-A01-P04前置核查，调查Output固定来源和模板/策略/插件Registry真实接线，不改变冻结API或Schema。


## Unreleased · 2026-11-04（Output Source 生产接线前置）
- OUT-01-A01-P04源码盘点完成；下一项P05为Requirement固定版本Source Owner读取与组合根映射。实现边界和验收计划已在CR-OUT-005先行记录，尚未修改代码。


## Unreleased · 2026-11-04（Requirement固定版本Source接线）
- OUT-01-A01-P05提交 [188a2ca0](https://github.com/yanglu0928/PLM-ProjectTool/commit/188a2ca0036acedfeb95b77883446a2315c90255) 的GitHub hosted run [41684956861](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41684956861) 全13/13 jobs成功。后端全量测试/wheel、前端构建、PG18/pgvector、Windows父包、A35、临时PG smoke、A17及A34均通过；A17 Artifact明确包含 `OUT_01_A01_P05_REQUIREMENT_FIXED_SOURCE_PG_PASS`。
- PG18合成烟测验证ProjectId+固定RequirementVersionId精确读取、`APPROVED`状态保真及非成员拒绝；无Schema/API/Migration变更、无外发数据。仅GitHub hosted Windows Server 2025，不构成Windows 11设备/Pilot/Gate/正式发行结论。
- Output文件模板/Policy Registry、Plugin启用/正式信任仍未实现，真实Output Create继续失败关闭。下一项为P06模板固定版本Registry编码前核查。


## Unreleased · 2026-11-04（Output模板Owner编码前核查）
- P06源码及冻结基线核查确认：OutputTemplate不属于冻结65个Aggregate Root；PrototypeTemplate是独立的原型布局/组件合约，不能冒充DOCX/PPT/Flow文件模板。决定在CR-OUT-006下实现只读、内置、固定版本OutputTemplate Registry，不加客户数据库表/API/Migration，不支持项目自定义模板。
- P06结论PASS_SCOPE_LIMITED；P07仅实现内置模板Registry与严格契约验证。Output Policy、Plugin启用/信任及生成/Artifact链未完成，因此不开放真实Output Create。


## Unreleased · 2026-11-04（内置Output模板Registry代码候选）
- P07新增固定版本只读内置DOCX模板metadata Registry，限REQUIREMENT_VERSION来源；无客户DB/API/Migration、自定义模板或渲染逻辑。A17 packaged runtime新增专用标记；本提交GitHub hosted验证待完成。
- Output Policy、Plugin enable/trust、文件生成与Artifact链仍缺；当前不支持真实Output Create。


## Unreleased · 2026-11-04（内置Output模板Registry受限完成）
- OUT-01-A01-P07提交 ab23b77e 的GitHub hosted run [41688934347](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41688934347) 13/13 jobs成功。后端全量/wheel、前端、PG18/pgvector、Windows父包、A35、临时PG、A17、A34全部通过；A17 evidence明确记录 OUT_01_A01_P07_BUILTIN_TEMPLATE_REGISTRY_PASS。
- Registry只提供固定ref的内置DOCX/RequirementVersion模板metadata；不含DOCX渲染内容，不支持自定义，不接真实Output Create。无数据库/API/Migration依赖变化。仅GitHub hosted Windows Server 2025合成验证，非Win11设备或发行证明。
- Output Policy、Plugin启用/正式信任、渲染与Artifact发布链仍缺；Pilot/Gate/正式Release保持NOT_READY。下一项P08先做Policy Registry编码前核查。


## Unreleased · 2026-11-04（Output Policy Owner编码前核查）
- P08确认冻结模型没有OutputPolicy Aggregate Root、DB表或管理API；插件operation registry的trusted/enabled生产事实缺失。依据CR-OUT-007，P09只实现一条内置不可变策略：P07固定DOCX、RequirementVersion/APPROVED，字段title/statement/acceptance_criteria，最多4来源/8192 bytes。word.generate允许列表不能替代plugin信任或启用。
- P08 PASS_SCOPE_LIMITED；本轮不新增Schema/API/Migration、不生成文件、不外发客户数据。


## Unreleased · 2026-11-04（内置Output Policy代码候选）
- P09新增只读固定ref内置OutputPolicyVersion Registry，严格限制P07 DOCX/REQUIREMENT_VERSION/APPROVED、字段title/statement/acceptance_criteria、4来源及8192字节Context；Resolver集成单测使用显式synthetic operation事实，不能视为生产Plugin信任。
- A17新增随包Policy metadata marker；云端验证待本提交。无DB/API/Migration变化，不接生产Resolver、不生成文件或外发数据。


## Unreleased · 2026-11-04（P09首轮云端失败记录）
- run [41692180197](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41692180197) 后端测试单项失败：测试误将空Policy目录的精确错误期待成通用目录无效消息。已先记录CR-OUT-007/P09进度文档，待修正测试断言后重跑全链；P09尚未通过，不是发布版本。


## Unreleased · 2026-11-04（内置Output Policy Registry受限完成）
- P09首轮run 41692180197仅因新增测试对空目录错误文本断言不匹配而失败，偏差先记于CR-OUT-007；产品逻辑未改，后修正测试并重跑。
- 修正提交 ac7cae27 的GitHub hosted run [41693364068](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41693364068) 13/13 jobs成功。后端全量/wheel、前端、PG18/pgvector、父包、A35、PG smoke、A17、A34成功；A17证据含 OUT_01_A01_P09_BUILTIN_POLICY_REGISTRY_PASS。
- Policy仅允许固定DOCX/Template/RequirementVersion APPROVED及有限字段/来源/上下文大小；word.generate allowlist不意味着Operation installed/enabled/trusted。无Schema/API/Migration变更，不接生产Output Create。仅PASS_SCOPE_LIMITED，无Win11新设备/Pilot/Gate/正式发行结论。


## Unreleased · 2026-11-04（PLG-02-A01内部云端验收，非发行版本）

- 版本：内部候选；不是安装包或正式发行。
- 变更：新增冻结PluginInstallation根及EnabledOperation/RuntimeValidation ORM与Migration 20261104_0225。初始Owner写入口保持关闭；不新增API、信任来源或插件执行。
- 验证：GitHub hosted run [41711045048](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41711045048) 13/13 jobs成功。PG18.6隔离合成库验证全新/既有库升级、空库回退重升、复合FK与唯一索引、Owner写入及TRUNCATE拒绝、有安装历史降级拒绝和记录保留；后端全量/wheel、前端、父包、A17/A34通过。
- 兼容性：PostgreSQL schema head推进至20261104_0225；父包候选限GitHub hosted Windows Server 2025验证。没有新的Windows 11实机/正式发行验证。
- 升级说明：升级运行数据库至0225；不对用户现有安装执行升级。降级在PluginInstallation相关历史存在时会拒绝。
- 已知问题：无正式插件安装Owner/API或可信Publisher来源，插件未运行；候选包不具备法律放行。Pilot、Gate、正式Release保持NOT_READY。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- 完成OUT-01-A01-P11编码前检查，登记CR-OUT-008：下一项实现只读PluginOperationCapability投影，依据PLG-02持久Owner事实校验安装、启用与最新运行兼容状态；无正式publisher key时trusted始终为false，不修改API/Schema、不执行插件。详见`docs/progress/out-01-a01-p11-plugin-operation-capability-precheck.md`。
