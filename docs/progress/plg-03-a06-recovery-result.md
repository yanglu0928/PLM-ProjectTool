# PLG-03-A06 已验收实现恢复记录

- 日期：2026-11-07
- Change Request：CR-EXEC-055
- 结果：PASS_SCOPE_LIMITED（源码恢复与A06专项复验；workflow aggregate未据此宣称全绿）
- 恢复源：e51389455c165e5081a9d72f61b800c13dbe549a
- 恢复提交：1bf3eb8e19d72ed4b37ca64c305eb35709296791
- Hosted run：[42350824543](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42350824543)
- A06专项Job：[128340182737](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42350824543)

A06 Owner、Repository、单元测试、PG18验收器和独立workflow job均按已验收源提交恢复。Hosted Server 2025 D盘运行同轮Windows候选包内PG18.6真实迁移与SQLAlchemy UoW；验收marker PLG_03_A06_PG18_PASS。PENDING→RUNNING、state event/Audit原子提交、Audit异常回滚、重放无重复写、stale fence/错worker/retry/terminal零写拒绝通过。Backend全量测试/wheel和Frontend/build通过。

该run中P25/P40/A08等其他工作仍在运行或未得出总结果，不将整run记为全绿。未启动插件、未接Worker、未触碰客户数据、无外部调用、无Schema/API/Migration变化；不构成Windows 11实测、Gate、Pilot或Release通过。项目代码只在GitHub Hosted Windows Server 2025 runner D盘运行。