# P03-A06-P03 Windows 显式平台结果/内容装配

日期：2026-09-26；状态：PASS（Windows11合成信任源显式组合；非正式材料/三平台发行）。

编码前检查：Phase2，WBS P03-A06-P03；输入CR-AUD-003/增量契约、P01/P02真实授权HTTP与资源生命周期PASS。单一问题为Windows两显式平台模式装配既有结果/内容GET；默认/login-only仍404。涉及entrypoint/Audit Application与各Owner公开Port，无新实体/Migration/角色/依赖，不修改冻结API。

装配：当前Session Auth read access、ProjectAuthorization、现有License Guard、Audit own root/results/plans、Document owned metadata/storage、Jobs owned queue/completion/lease repository。仅读取已成功成果，不装配Worker/SystemActor来源，不要求历史提交者当前enabled；系统身份不是读取权限。结果故障关闭；初始化失败由现有外层dispose，不把半装配应用交付。

验收：真实隔离PG完整发布双Scope和实际文件，在两个正式组合factory请求详情/内容，当前权限/License/跨Scope/坏文件拒绝；default/login-only404，四路由完整挂载，构造异常安全StartupError+dispose，关联Windows组合回归。生产Credential/License和cursor供给使用明确合成注入，只验证装配/实际业务来源，不冒充正式信任仪式。

风险：错误数据根、跨Owner私有表、启用POST或误开放普通应用；用实际临时文件根和Owner公共Port，检查路由。下一项真实提交/Jobs HTTP与Worker主循环/心跳，质量/Gate/正式账户/三平台/可用包仍待。

## 结果与验证

- Changed/Files：`entrypoints/production_login.py` 在两种include_secret_read平台模式装配现有公开Application服务和Owner Port，两详情及两内容GET；独立真实组合validator、1新增契约测试（两factory×三故障构造点）、配套CR/API/状态/决策/版本记录。
- Migration/API/升级：无DB变更，head0042；按既有CR-AUD-003仅增加四个GET，原冻结响应不改。无需数据迁移/新密钥/依赖，重启选择显式平台模式；撤装配可回滚，所有文件/历史保留。当前GET不需要生成Worker SystemActor/私钥/新User。
- Tests：真实PG18临时库完整受理/claim/capture/render/publish，PROJECT/DEPLOYMENT各260条成果，从两实际production factory到Session授权/详情摘要/完整文件SHA256和字节长度PASS；未知会话401、项目Admin无旁路/跨Scope404、许可403、损坏文件503 FILE_CONTENT_UNAVAILABLE、安全错误与ready200；default/login-only404，POST仍404。三构造故障不发布app；新增unit证明两模式均dispose一次、不泄漏内部异常。
- 回归：AUD-02-A05旧Windows审计列表/分页/实际Scope/失钥关闭通过；DOC-03-A04-A04旧Windows完整上传Commit/Abort/幂等/许可和Actor拒绝通过；附带旧原子发布/故障回滚/取消两锁顺序通过。
- Windows11/Python3.13全后端963项无失败，2既有符号链接权限跳过。开发wheel成功，577427字节，SHA256 `174af36067de090ee4534389414155e6dc6808083040fca0499475b1d5ee4e8a`。不是安装交付包。
- Result：P03/P03-A06只读接口增量Windows合成组合PASS，不代表能够由客户端提交和异步生成成果。Credential/License/cursor/write信任注入合成；SystemActor发布采用当前账户唯一临时Vault，非正式工作台仪式。
- Known Issues：正式目标账户/材料/ACL、真实代理、Server2025/Debian、性能/质量/Gate3/UAT/完整可用程序包仍待。不宣称部署名称含production即生产验证。
- Next：AUD-03-A06-A04-P03-A07-P01 审计Worker协调/心跳前置检查，之后实际受控Worker循环/失败取消恢复与提交/Jobs公开接口按依赖推进；不开放没有完整Worker验收的POST。
