# PLT-PKG-01-A09-P51-A17：当前 PlanVersion 闭环包内验收前置

- 日期：2026-10-26
- 状态：`PRECHECK_PASS`
- Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P51-A17`
- 依据：`CR-EXEC-002`、`CR-PKG-011`、A02源码级 Edge/PG闭环及当前状态中的P51候选路线

## 唯一问题与范围

验证本轮已通过的PlanVersion Create→固定读取→Validate→原子SubmitReview→Review只读前端，是否已集成到一个由当前HEAD派生的新Windows11非发行候选中，并能在候选包自带的Python/PG18/HTTPS布局及真实Edge内端到端工作。

仅新增/更新当前应用非发行包和独立包内验收器/测试/记录。无产品Owner、API、Schema、Migration、正式信任或服务安装变更；不使用旧固定候选冒充当前源码，不修改/覆盖已有候选与测试目录。

## 输入基线与前置证据

- 当前源提交：`0f24daf8daa88bf805628f58b0755e43b3050e08`（P09-P05-A02与CR-PLAN-011/012已同步）；本前置记录将先行提交，随后以该记录提交形成的新HEAD作为候选 `source_git_commit`，确保包对应的完整可追溯源码状态。
- 保留父候选：P45非发行候选SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`；P51-A02已有生成器和全量清洁Stage证据。
- A02源码真实浏览器证据：Win11 Edge→HTTP→PG通过，需求映射到两个WBS、Validate零未覆盖，Review/Round=`IN_REVIEW`、Audit=2、Receipt=1、Decision=0。A02的授权、License、Approved来源及Reviewer皆为合成数据。
- 最新P51包路线A16已证明同一安装布局切换后包内HTTPS/API启动与显式人工恢复，但仅对旧候选；A17必须派生新候选并单独包验。
- 当前D盘剩余空间只读检查约382 GB；本项构建、Edge Profile、PG数据与日志全放D盘。已存在D盘历史stage/安装根不做清理或覆盖。

## 模块、实体/API与权限

- 模块：`tools/package_windows_current_app_candidate.py`与当前后端wheel/frontend dist生成；当前候选stage工具；仅`validation/plt-pkg-01-a09-p51-a17-planversion-packaged/`一次性包验收工具。
- 数据实体/API：沿用冻结PlanVersion Create/GET/Validate/SubmitReview、Project Member读取及Review GET；不新增接口。PlanVersion Review只读解析接受严格`PLN-02`/`PLAN_VERSION_ALL_V1`配对；Review GET没有PlanId，页面只展示固定版本ID，不伪造详情链接。
- 权限：测试项目、Project Manager、Customer Manager、License、批准Outline/Requirement来源均为合成。负责人只提交Review；合成Reviewer只读取，验收后DB决定数为0。不外发资料，不执行真实客户确认。

## 验收标准

1. 从固定父ZIP和固定pgvector wheel派生新的ZIP，manifest源提交必须等于本次记录的完整HEAD；后端wheel与前端dist来自同一HEAD；全量inventory/hash复核，候选标志`release_eligible=false`、`legal_clearance=false`。
2. 新候选清洁解包至新建、唯一、ASCII D盘路径，逐件sha验收；candidate ZIP前后哈希不变。禁止拿P51-A02的旧stage替代新候选。
3. 只在本次拥有的临时安装布局启动包内HTTPS、Python和PG18组件；不用正式根、不注册SCM/服务、不触碰已有数据库/Vault/凭据目标。完成登录、2-WBS需求映射创建、固定GET读回、Validate、PM原子送审以及合成Reviewer Review读取。
4. SQL核对PlanVersion/Review/Round为`IN_REVIEW`，需求/WBS固定引用及Validation结果、唯一START事件、2条Audit、1条送审Receipt、0条Decision；浏览器无未捕获异常。
5. 停止本次拥有的Edge/API/HTTPS/PostgreSQL，回收本次明确拥有的PG/安装/profile临时资源并验证候选SHA不变；任一未拥有/历史目录保持不动。记录异常注入与清理结果。

## 风险、兼容与回滚

- 父ZIP和pgvector wheel必须匹配固定SHA；源代码wheel与frontend dist必须与同一Git HEAD绑定。任一摘要不符即停止，不能重写父包或历史attestation。
- 本项包验可能发现包内Source依赖与源码HTTP harness差异；先保留具体失败证据，再修验收器或提交新CR，不降低授权/License/来源/合同检查。
- 回滚只需保留旧候选并放弃新唯一候选/stage；不删除已保留历史版本，不涉及数据库迁移。候选法律、正式信任、三平台、Gate/Pilot/Release仍保持未通过。

- 精确pgvector输入：`artifacts/poc-01/windows/wheelhouse/pgvector-0.5.0-py3-none-any.whl`；PoC登记的固定SHA为`fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。构建前须重算核对；不从既有候选反向提取依赖。

## 编码前检查结论

基线、前置、范围、模块/API、权限、验收及D盘资源上限均已核实，`PRECHECK_PASS`。开始操作前重新确认当前HEAD与stage目标空缺；新构建与验收产物全部使用D盘独立新路径。
