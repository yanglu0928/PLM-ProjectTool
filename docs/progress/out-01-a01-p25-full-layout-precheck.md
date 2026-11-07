# OUT-01-A01-P25 编码前检查：完整父包与 PG-only 提取布局对照

- 日期：2026-11-06
- 状态：编码前检查通过；Hosted差分候选待实现
- WBS：OUT-01-A01-P25
- 依据：run [42164655328](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42164655328) 中P25与parent-smoke两组initdb参数在同一PG-only extraction root、同一二进制和原始PATH下都返回 `0xC0000135`、零输出、无PG_VERSION；但现有parent package smoke在同job完整包提取根成功。两处候选PG payload 1,627项哈希相同，余下已观察差异是完整包布局/其他payload存在性。
- 单一问题：P25 profile在父包完整package extraction root是否可以成功初始化，而在PG-only extraction root失败？
- 实施：保留compare脚本中的PG-only root P25 profile结果。给既有 `smoke_windows_parent_package_pg_cloud.py` 增加显式可选诊断参数，仅由P25 workflow的同作业smoke步骤传入；该helper在既有完整候选解包root中、用相同P25 profile和继承原始PATH执行一次隔离initdb。普通parent smoke job不传此参数。诊断只写新增子目录，不启动服务；只保存固定状态、退出码、stdout/stderr字节数、PG_VERSION布尔。完整PG smoke原有步骤继续执行，诊断失败不误作整个P25通过。
- 变量控制：PG payload版本/Hash、命令profile、runner PATH、平台和job均保持同run/同P25 job；仅执行根目录从PG-only extraction变为完整candidate extraction。两次数据路径均为D盘RUNNER_TEMP新目录。
- 判定：完整根成功而PG-only失败，说明完整包上下文/伴随payload影响装载，可继续分析具体依赖定位；两者均失败则重新审查此前smoke成功证据及流程阶段，不改产品代码；完整根失败且原smoke通过时，保持P25阻塞。
- 安全：只用经同run完整性校验的非发行父包及合成PG初始化；不接入HTTP/生产DB、不写业务事实、不调用外部API/插件，不上传PATH值/环境值/错误文本/DB内容。本机不运行程序。
- 回滚：移除helper可选flag、调用和新增摘要字段；P25 production harness不改。
- Secret检查：新摘要严格白名单；无密码、token、客户数据。
- 结论：PASS_WITH_LIMITATION，可进入该Hosted差分；P25继续BLOCKED_DIAGNOSTIC。
