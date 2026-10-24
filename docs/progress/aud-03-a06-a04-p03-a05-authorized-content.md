# P03-A05 当前Session导出结果访问与受控内容

## 编码前检查

Phase：Phase2；WBS：AUD-03-A06-A04-P03-A05。前置真实发布/恢复已验；输入0042/CR-AUD-002/ADR010、冻结API02/03的Session+License/PM或Admin权限。
涉及Audit访问编排、Document内容公开Port、Jobs成功只读Port；实体为原Root/result/plan/File/Job，无Migration/依赖。
API：内部当前Session查询与prepare下载；冻结API仅定义POST导出/JobView的result ref，未定义专用结果下载路径，本项不擅自挂HTTP，后续以非Breaking补充契约明确。
权限：读取按当前请求Session/Scope授权，PROJECT当前PM、DEPLOYMENT当前Admin；原提交actor仅来源，不要求其仍enabled，不让Admin旁路PROJECT。读取封口结果不写源，不重finish Job。先授权再源读取，copy/hash在所有UOW外，快照完成再当前Session/权限/License核验。
验收：真实发布文件→实际Session/元数据/成功Job/完整Hash私有快照、双Scope/空与非空；跨范围/未知结果/失效Session/撤权/许可/坏Hash及copy后撤权关闭流，错误不泄Locator/材料；保普通100MB，审计128MiB完整支持。
风险：快照不是永久权限，HTTP生命周期/断连/资源限额与公开路径后续验收；目标ACL/账户/三平台/性能/Gate仍待。

## 执行结果

内部能力PASS：实际当前Session+License及Scope PM/Admin授权先于源读取，原Root/accepted/result/plan、Jobs实际成功Lease/Attempt与Document AVAILABLE/登记摘要来源完整核验。原actor仅历史来源；当前新PM可读原actor停用后的项目审计，Admin无项目旁路。安全source DTO不含Locator，亦不是复用权限凭据。

Document仅从内部AuditFileCoordinate构造私有final Locator，独立审计快照入口上限128MiB，普通open_verified_snapshot仍100MB。共享实际copy/hash/单link/重解析点/文件变化检查、1MiB内存spool与有界落盘，无数据库UOW持有。完整快照完成后重新实际Session/Scope/License/全部源核验，撤权则关闭流；成功返回固定JSONL MIME/Size/SHA256/ExportRef和需关闭的私有stream，不返回路径/Lease/worker。内容未能证明时，在当前受权source同UOW追加最小失败Audit，不改成功历史/不造文件。

## 实际验收

Windows11/Python3.13/PostgreSQL18唯一临时DB/中文目录/独立临时Vault，License Guard合成。`validation/aud-03-a06-a04-p03-a05-content/verify.py`实际受理/发布→当前Session读取/真实文件snapshot，PROJECT/DEPLOYMENT empty/260验证完整Hash、close与读无写；未知Session、Admin无项目membership、跨Scope/未知Export、License拒绝先于文件I/O。实际snapshot完成后撤销专用测试Session，二次授权拒绝且stream关闭；不复活撤销记录。另建当前PM读取停用原提交者的历史成功文件，来源不改。真实文件损坏安全拒绝且追加一条实际当前用户内容失败Audit，原结果与文件登记Hash不改。

6项新增unit：严格查询/隐藏Session、source摘要绑定、二次授权/close、复制失败最小审计调用与真实128MiB物理文件读回Hash/有界copy，普通100MB不放宽及非audit路径/超上限拒绝。128MiB测试为Storage层合成字节，不冒充大规模Worker JSONL/性能验收。

后端951项无失败（2既有Windows符号链接权限跳过），最终source合同加固后重复通过；真实内容验证、原普通下载prepare与审计恢复/完整发布回归PASS。首轮专用Session撤销测试漏revoke_reason被DB CHECK拒绝，修正合成夹具为合法不可逆撤销后通过；没有弱化数据库约束或隐去失败。

开发wheel0.1.0.dev0构建成功，573260bytes，SHA256 `3facfc8e77a6fbefd037d0359d166e48bedfb1b1dccc377846497028f5ee168b`。无Migration/API/依赖/升级动作，head0042不变，不是安装包。

## 遗留 / 下一项

内部prepare未挂HTTP，仍需明确非Breaking结果/下载契约、安全公开投影和状态错误映射、响应前确认/断连关闭/线程与快照资源限额、组合根与实测。当前没有自动修复坏文件、普通静态文件暴露或生产删除入口。

正式账户/ACL/License信任、Server2025/Debian、大数据性能/质量Gate/完整发行仍未验证。Next：AUD-03-A06-A04-P03-A06，先记录增量下载契约，再实现受控结果/内容HTTP及生命周期验收，不修改原冻结API内容。
