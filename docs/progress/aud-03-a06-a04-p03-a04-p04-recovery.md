# P03-A04-P04 真实来源恢复与内部成功重放

## 编码前检查

当前Phase：Phase2；WBS：AUD-03-A06-A04-P03-A04-P04。
输入基线：CR-AUD-002/ADR010/0042及已验真实发布/受控系统来源；前置满足。
涉及模块：Audit Owner，Document注册来源读取、Jobs成功事实读取仅公共Port。
涉及实体：已有计划/File/状态来源/结果/Audit/Job/Lease/Attempt；无Migration。
涉及API：内部recover(command)，不新增HTTP/默认入口。
权限：原User当前权限/License/原Root/acceptance/pair；未成功恢复要求当前有效Lease/原代plan与受控系统来源；成功重放只读取原完整结果/真实成功Job/AVAILABLE元数据及完整物理Hash，不重新完成终态Job。
验收：真实数据库/File读取重建staged，不要求失去进程内DTO后猜Hash；stage/final/linked形状真实恢复；缺来源/不完整/坏Hash/撤权/取消/到期旧代拒绝；成功并发重放不写历史。
风险：仅同代有效Lease恢复，过期接管使用原capture新file；不重用旧代路径，不造结果/文件，不删除生产数据。HTTP下载需新Session权限，内部重放不是下载凭据；正式账户/三平台仍待。

## 执行结果

内部范围PASS。新增Document实际注册摘要/大小/来源只读Port及Audit原代plan只读find；缺登记不从路径填值、不新增plan。Jobs新增成功事实公共读取：原pair/Scope/actor/trace/payload、SUCCEEDED/current fence、RELEASED原worker Lease、原attempt/count/完成时点/无error一致；不调用finish、heartbeat或修复状态。

Audit恢复新Owner仅接原command，从实际Root/acceptance/pair/capture/plan/File构造context和规范manifest：未成功需原代有效Lease/STAGED，按真实stage/final/linked完整Hash在UOW外恢复，再调用原子发布；已成功需原不可变结果/AVAILABLE/真实成功Job，事务外验证final全Hash，之后再次当前授权和源核验，仅返回原结果。不把内部Worker返回当HTTP Session/下载授权。旧代过期接管仍新file/原capture，不复用旧最终文件。

## 实际验证

Windows11/Python3.13/PostgreSQL18唯一临时DB、临时中文存储根和当前账户唯一临时Vault。验证脚本`validation/aud-03-a06-a04-p03-a04-p04-recovery/verify.py`复用完整真实发布夹具；PROJECT/DEPLOYMENT实际STAGED、final无结果、真实双硬链接中间态，经新Owner实例与command-only恢复为原file成功。中断是注入故障/重新装配，不宣称实际杀进程或生产服务重启演练。

真实已成功Job/Lease/Attempt来源读取、两线程并发成功重放及全13表快照无写通过；错误owner/actor/trace/Scope、当前User撤权、坏已发布Hash、截断暂存、缺注册来源拒绝并无DB修补。真实取消和旧代过期拒绝；接管无原代plan拒绝恢复，正常渲染建立新代file、保原封口/旧final不变。实际commit成功后注入“确认丢失”，返回安全错误；重启Owner后按真实结果重放不改历史。License是合成Guard，Vault材料是独立临时合成引用，未访问正式材料。

6项新增unit：command/源类型/plan范围、三物理模式与非法形状拒绝、Hash后再次读取/不重完成、不重渲染及Jobs只读终态公共Port。后端945项无失败（2既有Windows符号链接权限跳过）；完整发布随恢复验证通过，旧Jobs完成与Document元数据独立回归通过。首次元数据回归调用路径写错未执行，修正到实际`p03-a02-p02-metadata/verify.py`后运行PASS，无测试失败被隐去。

开发wheel0.1.0.dev0构建成功，570278bytes，SHA256 `7dc55e6d107c93c39df2f6670bb08d8f0559df2b344e3dc4dea886fe3ba093ac`。无Migration/API/依赖/升级动作，head0042不变，不是可用安装包。

## 遗留 / 下一项

当前仅内部同代有效Lease恢复或真实原成功重放；没有调度器/心跳/HTTP/下载或生产异常限制审计入口。正式目标账户材料/ACL/服务重启与三平台、真实License/质量Gate/完整产品包仍待。坏文件保持失败关闭和原历史，不自动删除或造文件。

Next：AUD-03-A06-A04-P03-A05 当前Session/Scope下的结果访问授权与Document受控内容读取；先核冻结Job/导出下载契约，不把本内部Worker权限替代浏览器身份。
