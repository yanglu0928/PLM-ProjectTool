# CR-AUT-004：受控 Worker 系统身份来源

日期：2026-09-26；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION。
来源：用户持续授权、冻结64cdf09、ADR-007第7项、安全运行边界、CR-AUD-002。

## 证据与选择

AUD-03-A06-A04-P03-A04-P03前置核查发现运行代码没有SystemActor来源。0042仅检查SYSTEM/nonzero actor及原actor/trace，不证明该系统身份是本部署可信来源。不能以请求UUID、每次随机UUID、普通User或合成测试身份代替。

- A：新建系统登录User/角色。拒绝；扩大认证数据模型，可能引入不必要的密码或权限旁路。
- B：使用现有Windows当前运行账户Vault和既有加密备份生命周期，专用`worker-system-actor-v1`的32字节材料经域分隔SHA-256稳定派生非零UUID。选择B；不复用Secret/License/游标密钥，不增加依赖。
- C：把请求参数或随机UUID当系统身份。拒绝；没有部署来源或可追溯稳定性。

本补充精化来源，不改原冻结版本。材料只用来稳定标识，不用作签名、登录凭据或授权Token。UUID公开不授予任何业务权。Windows账户/Vault保护是信任边界，不承诺防同账户恶意代码或系统管理员。

## 差异与边界

前置拆为`AUT-04-A01`只读来源与本机恢复验证，再恢复原子发布。Platform公开Application Port返回当前受控UUID；基础设施读取材料，entrypoint固定生产引用。启动时固定完整派生摘要，每次使用重新读取并核验未变；缺失/异常/变化失败关闭，不自动生成或替换，不接受Job/HTTP提供身份。只保存非秘密摘要，不保留原材料。最终Owner发布调用仍须核原Root/actor/Scope/trace/purpose、当前权限/License/Lease/取消及全部文件/result事实；此Port绝不替代它们。

无Schema、API、User/Project角色、License载荷变更。默认应用不新增入口，不自动装配Worker或创建正式材料。正式供给使用已有本地`secret_key_recovery`CLI provision/export/restore和专用引用，密码由实际保管者持有，不写命令参数/仓库。

## 风险、迁移与回滚

丢失后必须从独立加密备份恢复原材料，不能重新provision来冒充原身份。进程中变更即拒绝；先停Worker，恢复原材料后重启。若需要真正换部署身份须另行可追溯迁移，不修改既有Audit。运行账户改变需在目标账户恢复并验证，Vault条目不是跨账户灾备。

无生产迁移；撤未装配的来源停止发布，不删除Vault、备份或历史。测试仅唯一临时引用和临时加密文件，清除自身测试条目，不访问正式凭据/客户数据。

## 验收计划

执行证据：AUT-04-A01 Windows11临时Vault真实丢失/错误口令/恢复保原身份与换材料拒绝PASS；934项无失败（2既有环境跳过）及开发wheel成功。详见`docs/progress/aut-04-a01-controlled-system-actor.md`。正式材料未供给，原子发布尚未接入，不改变下列剩余验收范围。

固定域/固定引用/稳定UUID；缺失、错型长度、异常、替换均拒绝且错误不泄材料。Windows11当前账户真实临时Vault provision→丢失拒绝→错误口令拒绝→恢复保持原身份，同引用重复安装拒绝。全后端与开发wheel回归。正式账户供给/异账户恢复/Server2025/Debian及完整Owner原子发布未验证，不标Gate或发行PASS。
