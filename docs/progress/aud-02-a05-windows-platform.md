# AUD-02-A05：Windows 显式平台审计查询

日期2026-09-26；Phase2；版本0.1.0.dev0；结果WINDOWS_SYNTHETIC_COMPOSITION_PASS，正式部署信任源未供给。

## 编码前检查 / Changed / Files

输入冻结API-02审计GET、A01当前受权service、A02完整性cursor、A03-P02可选HTTP、A04Windows独立key只读来源。前置满足。一个问题：Windows两种显式平台模式接线及失败关闭。涉及Audit安全读/当前Session/PM/Admin，不新增Schema/角色/依赖或安全算法。DEC-20260926-190。

production_login.py在include_secret_read平台范围明确取得audit-list-cursor-v1，使用同runtime的UOW、真实Auth读Port/Project授权、License guard与AuditReadRepository创建Router并注入app。仅--platform/--platform-write挂载四个冻结GET；缺key失败时dispose并返回安全startup错误，不自动生成。普通default/login-only不读该key或挂载Audit。

contract fixture新增显式合成Audit key和缺key两种模式dispose测试；14个既有集成验证fixture增加同样显式测试供给。回归发现部分老fixture还缺后来添加的Document列表/版本/解析cursor、Upload token信任源，导致已有平台安全关闭；本项仅补这些合成fixture，不降低生产门禁。文件列表以提交diff为准，原主验证语义/数据断言不修改。

## Tests / Result

- Windows11/Python3.13后端794项无失败，2项既有符号链接权限跳过；新增两种模式缺Audit key安全错误/资源dispose测试及挂载401检查。
- validation/aud-02-a05-windows-platform/verify.py：own UUID PostgreSQL至0035，在两种真实组合根下实际User/Session/PM/Admin、PROJECT四条两页无重漏/详情、Admin无项目旁路、DEPLOYMENT列表详情与跨Scope404、License失效403、健康200；缺Audit信任源拒绝构建，普通default/login-only404。组合使用合成License/key，不是正式发行信任锚或账户供给证明。原A03-P02 Scope/撤权/读无写同时回归。
- 14个受影响集成脚本全数实际运行通过：Project create/read/write；Member read/create/patch/state；Department read/create/patch/deactivate；Document upload-platform/finalize-platform；Workflow authorized-initialize。覆盖既有并发、幂等、版本、Scope、迁移/历史、失败回滚和平台安全边界。所有临时库由各脚本finally清理own UUID库；无生产数据操作。
- 开发wheel构建PASS，SHA256 `4aa13ce3862890eacf3aeb1d48f77a30fd80dee978ee2257cb6a42abd9fc9f3a`，不是可用正式程序包。

## Migration / API / Compatibility / Upgrade / Known Issues / Next

无Migration/Breaking API/角色/依赖变化；显式平台升级新增运行前置audit-list-cursor-v1，实际运行账户必须通过既有交互式工具供给并独立保管备份/恢复口令，运行时不生成。未供给则平台拒启，login-only仍可用其原恢复范围。回退组合根不挂Audit，无数据回滚动作；冻结原版本保留。

只Win11实测；Server2025/异账户ACL恢复未验，Debian13暂不验证，三平台目标不变。正式License公钥/目标账户key/离线保管仍缺，不能标生产或Gate3 PASS。AUDIT_EXPORT、完整业务Owner/AI-RAG质量/性能/UAT/可用程序包仍待。

下一项AUD-03-A01：冻结导出范围/用途/当前权限、不可变安全快照与Job生命周期前置设计核查；必要差异先CR再实施，不提前开放POST或借普通File下载暴露导出。
