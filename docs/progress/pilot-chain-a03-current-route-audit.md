# PILOT-CHAIN-A03：Windows 11 内部 Pilot 当前纵向路线复核

日期：2026-10-26。结果：`PILOT_CHAIN_ROUTE_REFRESH_COMPLETE / PILOT_NOT_READY`。本项为基于仓库/进度/已记录 Edge-PG 包内证据的只读路线复核，不是 Pilot 验收。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PILOT-CHAIN-A03`；更新 A02 过时路线并选出一个当前未完成的纵向阻断项。|
|输入基线|CR-EXEC-002、Gate 2 冻结 API-04/DM-05、STATUS、P51-A16同目录升级启动验收、HND-05-A05-P06、SUR-07-A12-P02/P05/P06、SOL-03 Outline/Section Review进度、PlanVersion WBS进度。|
|范围|只读核对真实Owner/HTTP/UI/Edge/PG/包内报告与状态记录；不更改产品代码、Schema、API、权限、用户数据或审批事实。|
|验收|纠正已完成/已被替代的旧路线；按用户目标“项目→交接→调研→需求→原型→方案→实施WBS→输出文件”指出当前可执行的最短下一片及独立阻塞；不将合成批准称为客户事实。|
|风险|将源代码合同误认为包内可用；把合成Reviewer或测试License当真实客户/生产信任；重复已完成任务；把只读Trace图误作PlanVersion业务Owner。|

## 路线事实

1. **安装与启动**：P51-A16 已把固定 Windows 11 非发行候选从旧目录映射升级到新目录，并在同一个新版目录运行包内 HTTPS/API/PG健康链及独立人工恢复演练。它是隔离合成验收，不具备产品安装器、维护锁、服务账户ACL、正式信任或正式数据库migration；Pilot仍 `NOT_READY`。
2. **交接**：HND-05-A02 有来源问题卡片 DRAFT 创建；HND-05-A03 校验；HND-05-A04 原子送审；HND-05-A05-P06 固定候选包内完成 Edge/HTTPS/PG Review批准链。但客户身份、问题与批准均为合成，不等于真实客户签署。
3. **调研**：SUR-07-A08/A10/A11 具备调研版本创建、校验和送审；SUR-07-A12-P05/P06 固定包证明当前项目成员可读、受指派Reviewer看到决定控件和准确固定版本。没有本轮证据证明真实客户已决定；不得替客户批准。
4. **需求/原型**：Requirement、Evidence、Prototype 已有Owner/UI/HTTP/PG及分项浏览器验收，但本轮未发现当前P51候选对整条“已批准调研→Requirement→Prototype→Solution→Plan→Output”做过完整包内UAT；模块局部PASS不能拼为纵向PASS。
5. **方案**：Section Version正式固定Spec/Review批准、Outline覆盖现时证明、Outline送审/Review及Windows Edge/PG链后来完成；因此 A02 与 `PLAN-02-A04-P04-A04-P03-P01` 旧文中“缺Outline/Section Review Owner”的陈述已经过时。当前实际Outline/Section内容仍只能由有权用户形成并确认。
6. **实施WBS**：Plan身份已包内创建/读取；WbsItem/依赖/Milestone/固定来源与Trace主要停在Schema/只读Trace证明。未找到 PlanVersion 创建/校验/送审业务Owner、HTTP/UI及包内工作链，不能从Plan身份或Trace图推定可制定/批准WBS。
7. **输出**：当前无正式 OutputArtifact 受权发布/下载Owner与业务流程；无法把任意文件或临时脚本视为正式交付成果。

## 选择的下一项

下一项为 `PLAN-02-A04-P04-A04-P03-P02`：在重新确认 Outline/Section/StructuredSpec 的当前批准固定版本证明和 Requirement/Evidence/Trace来源边界后，设计并实现 PlanVersion 的最小同事务业务Owner/写路径前置。先在对应编码前检查中阅读冻结 API-04 与各来源Owner合同；仅接受服务端现时 `APPROVED` 固定版本，失败关闭、同Key重放有界，禁止以合成夹具状态生产化。后续再分离校验/送审、WBS写入/UI/Edge包验收及Output owner，不跨层顺手扩项。

选择理由：这是从已存在批准方案链通往实施WBS、再通往Output的首个确定缺口，且属于冻结范围内剩余的业务Owner工作。此前依据的Outline/Section审批缺口路线已被后续实现取代；当前不能跳过PlanVersion直做正式WBS/Output。

## 独立未解除条件

- 用户真实客户资料/批准仍须真实授权参与者处理；本路线不制造客户确认。测试夹具只使用清楚标记的合成身份/数据。
- 正式产品公钥、License生产信任源、操作员仪式/备份、目标服务账户/CA及Windows正式离线安装仍未证明；测试信任不得伪装正式Pilot成功。
- Windows Server 2025未由本轮证明；Debian 13仍按用户要求跳过；Gate 3～7、性能、完整UAT及Release均保持未通过。
- A16两处调试遗留旧版硬链接Temp备份尚未移除，已在A16记录；不得纳入源码或Git。

验证：静态交叉核对列出的进度文件、代码模块、固定API合同和STATUS；无功能测试（本项不改运行代码）。Next：上述PlanVersion业务Owner前置与实现片。
