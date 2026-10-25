# SOL-05-A04-P12-P05-P01：Section Spec 现时证明前置检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`PRECHECK_PASS / DESIGN_ONLY`。

|检查项|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P05-P01`，核对六维VALIDATE Spec现时事实来源与失败关闭边界，不在本片开放PASS|
|输入基线|Gate 2冻结六维合同、CR-SOL-022/023、0180固定引用Owner、0182逐引用作者依据Owner；原冻结提交64cdf09保留|
|当前实现|`SectionVersionCurrentValidator`把`spec`恒设UNAVAILABLE；CREATE已按现时SOL-06批准、精确Review快照、章节祖先和共同需求做资格证明，但该创建时证明不能替代验证时重新观察|
|`UNDECLARED`|永远不能得Spec PASS；旧历史不补填、不推断为无需专项|
|`NONE_REQUIRED`|只在原版显式理由规范、零固定引用且历史结构一致时，给“具备送审依据”PASS；理由不是客户确认|
|`FIXED_REFS`|要求至少一条固定引用、数量/序号/唯一性完整，每条有规范作者依据；同一验证事务重证每条Spec当前批准唯一版本、精确Review已批准快照、同项目章节祖先与共有固定需求；失效/错源/异常均不得PASS|
|正文/状态边界|Section目标必须是受权固定DRAFT现时读；正文DocumentVersion当前资格沿现有content维重查，Spec PASS不得覆盖content/trace失败；旧Key回放首次观察，新Key重新取现时事实|
|含义|Spec PASS仅表示作者逐条依据和现时资格齐备，可供后续正式Review；不证明自然语言语义正确、AI结论或客户批准|

## 实施切分与风险

后续P05-P02先定义可注入只读Spec现时证明端口与负例合同，不修改既有冻结路径/状态值；P05-P03再做真实Windows/PG组合。CREATE用`CurrentSectionVersionBase(next_version_no, supersedes)`判断来源祖先，VALIDATE不能机械重用“准备创建下一版”的参数；必须以正在验证的固定版本号和其前驱为参照，并独立核对当前批准事实。旧无依据固定引用保持UNAVAILABLE，不能因已有Spec批准而PASS。任何端口缺失、数据不完整或异常均失败关闭。

本片仅静态交叉核对`validate_section_version.py`、六维合同、现有CREATE资格证明与P04验收；无程序/Schema/API/数据变化，未运行本片功能测试。Pilot/Gate/正式发行状态不变。
