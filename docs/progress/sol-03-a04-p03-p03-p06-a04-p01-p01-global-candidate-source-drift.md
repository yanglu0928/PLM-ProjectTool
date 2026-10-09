# SOL-03-A04-P03-P03-P06-A04-P01-P01：项目 GLOBAL 候选后物理来源漂移直接拒绝

日期：2026-10-09。结果：Win11 可弃 PostgreSQL 18.6/真实 FastAPI/Edge 合成链通过；只验证物理文件内容漂移，不推定修订或确认过期情形已直接覆盖。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate2 API-04、CR-SOL-018、DEC-1160/1161、P03 浏览器正例与现时 ReferenceUseProof。
- 单一问题：客户端在看见已发布 GLOBAL 候选后，底层受控文件改变时，候选读取与 OutlineVersion CREATE 均不得沿用旧选择成功。
- 模块/实体/API/权限：仅扩展可弃验收脚本；复用项目候选 GET、OutlineVersion CREATE、PM Session/License、实际 Document 物理证明；不改运行 API、ORM/Migration、角色或依赖。
- 验收：GET 原可见→等长文件篡改后空项，旧固定引用新操作号 POST 拒绝且不新增版本/Audit/收据，finally 恢复源文件后重新可见，脚本正常清理临时 PG/Edge。
- 风险：测试误改用户文件、失败留下篡改或部分正式数据。只用夹具受控根/唯一合成 FileObject，解析绝对路径并验证仍在根内；`finally` 恢复原字节，全部数据保存在可弃 PG 与临时文件根。

## 验证

扩展 P03 验收资产，在 Edge 正例提交 DRAFT 后，用同一运行服务和原项目 Session 验证旧候选的失效 TOCTOU 边界：可弃文件改为等长不同字节，项目候选 GET 200 但 `items=[]`，原固定 GLOBAL 引用的新 CREATE 返回 503；恢复文件后 GET 200 再次见同一根。SQL 复核版本、`SOL_OUTLINE_VERSION_CREATED` 审计及 `V1_SOL_OUTLINE_VERSION_CREATE` 收据计数均保持不变。脚本运行两轮均退出 0，第二轮增加收据断言；输出 `GLOBAL_CANDIDATE_SOURCE_DRIFT_PASS`，原 P03 Edge/PG 及上游来源验证继续通过。

兼容/升级/回滚：仅验证资产改动，无应用代码、Schema/Migration、API/权限/依赖变化；删除新增检查即可回滚脚本，数据库与业务历史不变。下一项 P01-P02 单独覆盖确认撤销/过期，P01-P03 单独覆盖版本修订；CR-SOL-018/Gate3 仍不关闭。正式服务账户、Server2025、性能/发行未验；Debian13 实机依用户指令跳过。

TraceLink：CR-SOL-018 → DEC-1160/1161 → P03 浏览器正例 → 本来源漂移直接负例 → P01-P02/P03 → Gate3/Release。
