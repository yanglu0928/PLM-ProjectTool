# OUT-01-A01-P27 Output Job 执行准入结果

- 日期：2026-11-05
- Change Request：CR-OUT-023
- 状态：**PASS_SCOPE_LIMITED**
- Hosted run：[41940381378](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41940381378)
- 运行环境：GitHub hosted Windows Server 2025，项目验收工作区与PG数据位于D盘临时区；未在用户本机/C盘运行。

## 实现内容

增加Output-owned只读准入Owner及SQL Repository。准入前精确校验Claim Job类型、Project和payload refs；在同一Output事务核对Request绑定的job、project、ContextSnapshot，比较Request与Snapshot的来源引用，重算Snapshot fingerprint和创建时的Request总input_fingerprint，并重新读取当前Plugin operation capability。插件未启用、不可信、输出格式不兼容或数据缺失时拒绝。成功只返回身份、版本、策略、操作和指纹等最小事实，不返回Snapshot正文。

没有运行Worker、插件子进程、文件生成或外部API；没有修改Schema、Migration、公开API或默认启动组合。

## 云端验证

Run 41940381378 的后端 unittest discover 执行 **4,027 tests**，结果OK；backend wheel、前端测试/typecheck/build、PG18/pgvector构建均成功。父包PG smoke摘要：

- output_job_admission_validation.status=PASS_SCOPE_LIMITED
- 正确的Job/Request/Context绑定通过准入
- 错误Snapshot引用被拒绝
- disabled、untrusted及不支持当前输出类型的Plugin capability均失败关闭
- 输出中没有Context payload
- schema_changed=false、plugin_executed=false、output_files_generated=false、external_api_calls=0、customer_data=false、runner_drive=D:
- Snapshot fingerprint篡改单测通过；PG负例遵守不可变快照约束，未尝试修改数据库保护的数据

Run中P25仍在initdb阶段以0xC0000135失败，真实Output HTTP/Edge未执行。该独立失败不覆盖P27的准入结果。

## 验收边界与后续

结果只证明合成PG数据和hosted runner中的准入判断；不代表真实Worker、真实Publisher信任、渲染/发布、Windows 11实机或Pilot已通过。准入结果不等同活动租约或永久执行授权，未来Worker仍需在副作用边界复验当前fencing lease和信任。

后续WBS：实现真实Output Worker副作用前的活动租约/fencing证明及状态推进Owner；该项继续保持无插件执行，直到正式信任链和可验收渲染/发布边界齐备。Pilot、Gate 3～7与正式Release继续NOT_READY。
