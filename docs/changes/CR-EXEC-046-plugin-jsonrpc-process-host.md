# CR-EXEC-046：PLG-03-A01 最小 JSON-RPC 子进程 Host

日期：2026-11-07  
状态：编码前检查通过；实现与Hosted验收待完成。

## 当前阶段与WBS

Phase 2 Platform Core / 受控Windows 11 Pilot准备。WBS：PLG-03-A01。

## 编码前检查与依据

- 目标架构要求插件独立子进程、JSON-RPC over stdio；插件不得直连数据库或管理AI Key。
- 仓库已有Plugin包导入、签名校验、安装/启用、运行时验证、Operation capability读取与退役Owner；Plugin模块当前尚无统一JSON-RPC子进程Host/Invocation Transport。Output已持久化Request/Context/Job/Outbox/Artifact并提供读取/下载契约，但尚不能安全调用 `word.generate` 进程。
- `developer_keys.json` 的publisher key清单为空；CR-EXEC-042/043要求正式Publisher trust缺失时fail closed。CR-PLG-003规定真实密钥仪式仅在受控开发者工作台进行、Hosted测试只使用临时合成密钥；本WBS不填正式清单、不生成真实密钥。
- 因正式Plugin trust与Operation capability尚未配置，当前不得连接生产Output/Jobs消费流程。本WBS仅建立默认不可被生产组合引用的transport基元，并用仓库内一次性synthetic child验证。

## 范围与验收

- 新增最小插件子进程调用抽象：固定JSON-RPC 2.0单请求/单响应契约、稳定request id、shell关闭、显式executable/argv、owned工作目录、有限超时与输入/输出上限；child stdout仅承载协议，stderr不回显原文。
- child环境变量由显式allowlist构造；不得继承API Key、数据库密码、License、Windows credential或其他父进程秘密。Host不传数据库对象或AI服务客户端。
- 不承诺OS级沙箱；进程隔离不代表任意或第三方插件安全。Host后续只能由签名、Active安装及Capability已验证的调用者使用；本WBS不提供调用组合。
- Hosted Windows Server 2025 D盘RUNNER_TEMP只运行一次性synthetic child；覆盖合法响应、格式/ID错误、超时、超大输出、非零退出/无效JSON、秘密环境未继承与工作目录/清理边界。失败关闭且不输出原始请求或子进程文本。
- 仅增加新的Host、定向测试/验证Harness及文档；不改API/Schema/Migration、Publisher trust manifest、License、Output worker、安装/审批事实或发行配置。无客户数据，不执行真实插件。
- 提交前执行Secret scan；所有代码验证在Hosted D盘，不在本机/C盘运行，同步PR #61正确分支。

## 风险、回滚与关闭条件

如果不能保证owned cwd/temp、超时后进程终止及秘密环境剥离，先记录偏差并停止；不得把本项描述为沙箱或信任通过。回滚仅撤销新Host及定向测试，不影响既有插件导入/信任与Output Owner。无客户数据、付款或不可逆生产操作。
