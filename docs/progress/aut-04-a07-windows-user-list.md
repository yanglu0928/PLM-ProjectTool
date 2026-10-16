# AUT-04-A07：Windows User列表装配

2026-09-27 Phase2编码前PASS，A04～A06安全列表/HTTP/独立KeySource已验，当前0045/冻结AUTH_USER_LIST。仅两显式platform挂列表，default/login仍404；原Session/Admin/License与独立user-list-cursor-v1强制来源，无自动fallback。

DEC292：新增此必需KeyRef会使未供给的旧显式平台配置启动拒绝，升级前目标运行账户应交互供给/独立加密备份；不替代其余已有信任。回滚撤列表接线可恢复旧启动依赖，数据历史保留。无Schema/API Breaking/依赖/角色变。历史正向验证器显式补synthetic User cursor注入并回归，不以生产默认key或跳过异常修复测试。

验收actual两Factory多页/角色SessionLicense/五表无写、构造/key缺失fail closed/dispose、default/login关闭、实际缺正式来源拒绝及相关历史Windows验证回归；正式供给/其他账户/三平台/性能/完整管理面/包/Gate仍待。

执行结果：WINDOWS_COMPOSITION_INTERNAL_PASS。两actualFactory均完成A05真实当前Session/Admin/含DISABLED目标/加密完整多页及每项真实User ETag/Credential版本核验，跨context/篡改/撤会话角色License拒绝五表无写。三依赖fault每Factory实际调用、单位矩阵明确dispose；其他信任正向合成时切回实际固定User cursor来源，证实缺此Key仍拒绝半启动；default/login404，其他正式信任未供给亦拒绝。

1277后端无失败（2既有符号链接权限跳过）；23历史正向fixture显式补合成User cursor，相关25实际验证入口全部exit0，详见`docs/test-reports/aut-04-a07-windows-regression.md`，涵盖User详情/列表、Project/Member/Department、Upload、Workflow、Audit、Job读取/取消/实际重试及发布。不能把机械补注入本身算回归，已逐入口实际执行。

开发wheel691255字节，SHA256 53d61cc2359865acdcfd28af3dd005b01847004319fcf83bb11791a1e106d9fb，非最终可用安装包。无Migration/依赖/角色/Breaking，0045兼容；升级新增目标账户user-list-cursor-v1交互供给/备份前置，未供给不能以测试key启动；回滚撤列表接线保历史。正式账户/其他平台/索引性能/用户管理写/完整包/Gate待。Next AUT-04-A08用户创建HTTP前置：当前旧内部创建无持久幂等/首次UserView snapshot及实际CSRF/License Admin命令装配，必须先设计再实现，不能直接挂POST。
