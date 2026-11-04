# OUT-01-A01-P26 输出作业 claim 隔离结果

- 日期：2026-11-05
- Change Request：CR-OUT-022
- 结果：**PASS_SCOPE_LIMITED**
- hosted run：[41931429638](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41931429638)
- 运行环境：GitHub hosted Windows Server 2025；项目输入、临时PG、验证工作区均位于runner D盘；未在用户本机/C盘运行项目代码或测试。

## 验收结果

该run共14个jobs：13个成功，P25真实Output Create HTTP + Edge集成job失败。后端全量 **4,023 tests** 与wheel、前端测试/typecheck/build、PG18/pgvector sidecar重建、父包组装、父包PG lifecycle smoke、A17、A34、A35、A50及P24 Edge均成功。

父包PostgreSQL smoke中的P26验证摘要为：

- generic_claimed_non_output_jobs=3
- generic_left_output_job_pending=true
- output_specific_claimed_output_jobs=2
- fencing_tokens_verified=true
- schema_changed=false
- plugin_executed=false
- output_files_generated=false
- external_api_calls=0
- customer_data=false
- runner_drive=D:

这证明专属claim只领取 owner_module=output 且 job_type=OUTPUT_GENERATE 的合成作业；generic claim继续处理不匹配的其它合成作业，同时不会越过Owner边界获取Output Generate。Output作业无消费者时保持排队，不会由其它Worker代执行。

## 偏差与限制

首轮run 41929416448 的专项断言执行到资源清理时调用了不存在的 DatabaseRuntime.engine。偏差先记录在CR-OUT-022；验证器改为使用公开的 DatabaseRuntime.dispose() 后，本run完整生成PASS摘要。该偏差位于临时验证器清理，不是产品DB/API故障。

本run中的P25仍在 initdb.exe 数据目录创建前以 3221225781 / 0xC0000135 失败，因此未启动真实Output HTTP、Edge或数据库计数复核。P25仍为未通过，不影响P26的独立限界claim结果，但也不能被P26结果替代。

## 兼容性与交付边界

- 变更仅是内部Jobs claim过滤/专属入口，无ORM/Migration、公开API、安装包升级合同或冻结基线变化。
- 验收仅覆盖GitHub hosted Windows Server 2025 runner上的合成PG18.6/pgvector0.8.6数据；不是Windows 11实机、正式信任链、Output Worker渲染、文件发布或客户数据验证。
- 未执行插件、AI/外部API、客户数据、正式Publisher密钥或生产操作。
- Pilot、Gate 3～7和正式多平台Release保持未通过；P25继续阻塞真实HTTP/Edge路径。

## 后续

下一WBS先做Output Worker剩余消费边界的编码前检查，明确可信请求/快照绑定和无消费者失败关闭条件；在Publisher信任链未成立前不接入插件执行或输出文件生成。
