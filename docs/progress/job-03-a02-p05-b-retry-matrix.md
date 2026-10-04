# JOB-03-A02-P05-B：Windows重试边界矩阵

2026-09-27 / Phase2；编码前PASS。输入CR-JOB-006、API增量、0045及P05-A实证；仅补验收脚本/夹具复用，不变生产逻辑、实体、权限或API。

目标：真实PROJECT/GLOBAL Document上传Commit来源通过现Windows Owner读取、retry明确409且全业务表无写；PM变实施成员/客户角色只提示false且写拒绝，未知客户不能借原actor身份读取；归档Audit Export维护例外实际执行新generation；实际Attempt非临时分类及故障来源区别不得伪装false。

计划：复用原真实Document文件/Commit helper，Parser available_at未来值仅夹具防误领取；补P05客户端回调进行当前Session/CSRF/Scope/强版本拒绝；故障来源若只能注入应明确标记，不能冒充库损坏实证。归档夹具须恢复以不影响原发布回归。无Migration，回滚撤验证脚本，不触碰生产；正式信任合成、三平台/性能/完整包/Gate保持未通过。

## 执行结果：WINDOWS_INTERNAL_MATRIX_PASS

- 真实PROJECT/GLOBAL Document文件staging→Hash→Commit→原Job/Outbox/Upload审计/固定版本。Windows当前Owner GET retryable=false，使用GET真实ETag及当前Session/CSRF提交retry均精确409 JOB_NOT_RETRYABLE；请求前后20表全行无写。Parser可用时间仅夹具延后，未运行Parser。
- 原实际第三失败Attempt在隔离库可逆技术注入：error_code改非临时LICENSE_OPERATION_DENIED，GET false/POST409；completed_at改与Job/Lease不一致，GET/POST503 SYSTEM_UNAVAILABLE。每次HTTP无写，恢复原字段后GET true。非临时错误是技术fixture分类验收，不冒充实际Worker产生永久失败；坏时间为实际库事实不一致，不是Mock读异常。
- 当前原creator降IMPLEMENTATION_MEMBER、CUSTOMER_MANAGER、CUSTOMER_MEMBER，GET仍受权但retryable=false、retry404；另建实际当前客户非creator，GET/retry404。Scope/Session/License沿P05/P04矩阵不放宽。
- 项目归档夹具下PM提示true，实际POST新generation→真实Worker capture/render/publish→GET SUCCEEDED/false；证明冻结Audit Export维护例外未误当一般归档写禁止。恢复ACTIVE后原双Scope命令/HTTP/Worker回归通过。
- 首次异常断言误写内部JOB_UNAVAILABLE；核对现GET/retry映射后改为公开SYSTEM_UNAVAILABLE，完整真实隔离链重跑通过，生产代码不变。
- 后端1247无失败/2既有符号链接权限跳过；重构Document夹具后的旧Windows混排/原发布验证通过。生产代码未变，本轮不重建wheel，沿P05-A开发wheel682697及原SHA，仅为开发产物。

P05-A+B实现与内部验收完成，不外推正式密钥/目标账户、三平台、吞吐性能、其他未来Owner、安装升级或完整包/Gate。无Migration/API生产修改/依赖/角色/升级动作；回滚撤新增验证并恢复旧fixture函数形式，历史保留。Next：Phase2尚缺User管理面，先AUT-04-A01安全User读模型/实际当前Admin授权前置。
