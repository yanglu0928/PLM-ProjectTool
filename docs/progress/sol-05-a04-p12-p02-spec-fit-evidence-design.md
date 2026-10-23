# SOL-05-A04-P12-P02：Section Spec 适配依据方案

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`DESIGN_PASS / IMPLEMENTATION_PENDING`。

|编码前检查|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P02`，只确定 Spec 维送审依据的可信含义与最小落地方案|
|输入基线|Gate 2 DM-05/API-04、Section VALIDATE V1 六维合同、CR-SOL-022、DEC-1204/1205、P12-P01 缺口核查|
|前置任务|0180 固定引用同事务写入和 Review 当前快照读取已验；正文 DocumentVersion 当前证明已存在|
|涉及模块/实体|Solution SectionVersion 固定 SpecRef 与现时 Validator，Review/Document 仅调用公共 Application Interface|
|涉及API/权限|原 CREATE/VALIDATE 路径及项目角色不变；可选引用级适配依据由当前授权作者提交，不增加免审权限|
|验收标准|区分 `UNDECLARED/NONE_REQUIRED/FIXED_REFS`、旧历史不变、依据与正文/Spec 指纹绑定、现时资格重证、客户 Review 仍独立；数据库/HTTP/PG/权限/回归逐片验收|
|风险|把作者依据当客户签署、AI 建议当正式事实、对旧行静默补填或将已批准 Spec 直接转化为新正文适配 PASS|

比较三方案后按 `CR-SOL-023`/`DEC-20261023-1206` 选择“逐引用作者适配依据 + 现时资格重证 + 后续客户 Review”。本片只记录设计与迁移/验证计划，未修改程序、Schema、API 或已有业务历史，未运行功能测试。后续 P12-P03 先建立闭锁兼容 Schema，再分输入/Owner、现时 Validator 与 UI/真实 Windows 验证片。Gate 3/Pilot/发行状态不变。
