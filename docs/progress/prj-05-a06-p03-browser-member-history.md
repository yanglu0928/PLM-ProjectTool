# PRJ-05-A06-P03 Windows11 隔离浏览器成员历史联调

2026-09-28 / 0.1.0.dev0 / PASS（一次性合成账户、loopback、隔离PostgreSQL；非正式发行）。

编码前检查：Phase2、Gate2/Phase1通过；冻结`PROJECT_MEMBER_LIST`、P01客户端/P02页面、后端Windows显式只读组合已具备。DEC-433先记录测试结构、风险、回滚。只扩原自有夹具的互斥`--member-api-only`/`--member-browser`模式；不改生产实体、API、权限、Schema/Migration或依赖。

环境事件：本轮开始原 PostgreSQL 18 数据目录服务未运行；核目录后重新启动，日志显示WAL自动恢复并就绪，测试前`prj05a04_%`临时库0。服务再次停机原因未证实，不能归因于产品。

夹具为OWNED项目合成负责人、实施成员与50个额外历史成员，最后一条为REMOVED。独立真实HTTP模式exit0：实施成员可读项目详情但成员历史404，部署管理员无项目成员权限也404；负责人历史列表首页50/续页2，唯一52条包含1条移除；外项目404；原游标更换`page_size`为20时400。终态SQL为52历史/51 ACTIVE/3测试Session，服务、库、角色、Vault测试凭据自动清理通过。

实际浏览器模式：合成实施成员登录→OWNED详情可见→成员历史页面仅显示“项目不存在或无权查看成员”；退出后合成负责人登录→项目详情→成员历史首页出现50条并可点“读取下一页”→第二页追加`Synthetic History 48`与已移除的`Synthetic History 49`。`VERIFY` exit0：52历史/51 ACTIVE/2测试Session，自动清理通过。原`--api-only`只读项目模式另回归exit0，独立查询`prj05a04_%`临时库为0。

现有前端P02的418测试/typecheck/build证据仍有效，本项仅改测试夹具未重跑前端。仅本机合成License/游标签名密钥和HTTP，不替代正式TLS、公钥/目标账户密钥、Windows Server2025、Debian13、20并发/质量、Gate3或可用包。兼容DB head0049，无升级步骤；回滚撤夹具新模式，不涉及生产数据。
