# OUT-01-A01-P10：Plugin Operation生产能力事实Owner编码前核查

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED（只读源码盘点完成；确认真实安装/启用/信任Owner缺失）
- WBS：OUT-01-A01-P10
- 依据：CR-OUT-004/007、P09 PASS_SCOPE_LIMITED、冻结API-03、DATA-MODEL-CANDIDATE-V1、SC-01/02

## 问题与结论

OutputPolicy中的 word.generate 仅是策略允许标签，不能证明插件包已安装、操作已启用、发布者受正式信任或运行环境有效。P09 resolver仍要求显式enabled/trusted事实，否则失败关闭。

本次完成只读源码盘点。已证明当前没有可消费的生产Plugin Installation/Operation事实Owner；故本WBS不新增伪造适配器，不把Output创建标为可用，并转向实现冻结PLG-02安装根的持久化基础。

## 核查证据

- PLG-01当前仅有Package、Manifest operation/dependency、Verification和异步Import staging ORM；对应Migration到20261103_0224。没有PluginInstallation ORM、安装/启用业务Owner、Operation enabled事实读取Owner或公开安装/启用路由。
- GitHub hosted Worker只校验签名包、解析Manifest、执行静态兼容评估并登记Package VERIFIED元数据；没有安装、启用或执行插件代码。VERIFIED不等于INSTALLED/ENABLED。
- packaged_signer_resolver.py的正式publisher key清单目前为空；测试用内存密钥仅服务合成验收，不属于客户部署信任来源。
- 冻结数据模型已定义PLG-02 PluginInstallation；SC-01已映射plg_installations、plg_enabled_operations、plg_runtime_validations。SC-02将PLG-02分配到M-DEP。
- ADR-005要求开发者签名包、独立Python子进程与JSON-RPC stdio；其故障边界不代表任意代码沙箱。

## 验收边界

本WBS只验收“源码盘点完成，Owner事实缺失得到证实”。不改程序、DB、API或测试；不连接客户数据、不运行插件、不写安装/启用记录、不生成文件。Output Create仍失败关闭；Pilot、Gate、正式Release结论不变。

## 下一步

进入PLG-02-A01：按已冻结Schema实现Installation root和两个owned表的ORM/Alembic持久化基础。新CR-PLG-007及编码前检查先于代码提交。安装/启用Owner、信任源、插件执行和Output Operation resolver保持后续独立WBS。
