# PRJ-05-A05-P02 前端项目创建客户端

2026-09-28 / 0.1.0.dev0 / PASS（前端客户端合同；UI/真实写入待后续任务）。

编码前检查：Phase2/PRJ-05-A05-P02，输入冻结PROJECT_CREATE、PRJ-04-A05 Windows显式写组合、PRJ-05-A05-P01私有CSRF桥接与A01项目安全投影；Gate2前置满足。只涉及前端Project API客户端及同模块投影解析复用；实体/Schema/后端API/权限/依赖不变。冻结请求为项目code/name、initial_manager_user_id、可选department；控制为S/L/C/I/A，仅DeploymentAdmin且服务端实时核初始负责人。验收严格本地规范化与零请求拒绝、原调用方Key/单次提交、201信封/ACTIVE/v0/Location/ETag/code/name核对、确定拒绝固定提示、未知结果不自动新建、前端test/typecheck/build。风险/迁移/回滚见DEC-408；撤新增客户端/导出的同模块解析函数即可，无迁移。

Changed：`ProjectCreateClient`只接受调用方Key，不生成、不保存、不自动重试。code/name/部门按NFKC去边空与服务端长度/Unicode控制字符规则预检，负责人必须规范非零UUID；请求通过原SessionClient私有CSRF桥接。201仅返回冻结白名单ProjectView并核响应强ETag、Location、初态和请求一致性。401/403/404/409/422只有状态码与已知错误码匹配才映射固定安全信息；500/503/断线或畸形201均作为可能已提交的`uncertain`，原正文/错误信息不显示。客户端角色提示不是权限判定。

Tests：新增26个参数化场景，前端173/173、typecheck、build PASS。含正常/部门规范化、无效输入/Key与只读会话零创建请求、八种确定拒绝、错误输入映射、非预期响应与传输失败无自动重试；只读测试初稿实际为请求异常，已改为有效只读SessionView重跑通过。未运行本项真实浏览器/PG、后端全量、coverage或性能；此前A04只读联调不可替代写验收。兼容0049，无Migration/后端API/权限/依赖变化。下一 P03：管理员创建页面、负责人选择/提示、同账户原输入原Key恢复与401/409安全阻断，再做Windows11真实PG写链。正式信任/HTTPS/CR-AUT-008性能FAIL/Gate3/可用包仍待。
