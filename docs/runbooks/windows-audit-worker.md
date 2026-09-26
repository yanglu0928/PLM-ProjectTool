# Windows 审计后台开发入口

本入口尚不是完整发行包；当前仅Windows11合成验收。正式包内公钥、选定MAC、目标运行账户的数据库Credential Manager、可信时间材料/SystemActor、当前Migration、数据目录ACL必须先由既有安全流程供给。缺任何来源都应失败，不使用环境变量/命令行数据库URL或备用测试密钥。不要将开发验证材料用作客户发行材料。

在已准备好的Python3.13后端环境，由与Web相同的目标账户启动：

```powershell
python -m plm_assistant.entrypoints.worker_windows C:\PLMTool\config\bootstrap.yaml
```

一次有界操作（并非健康或服务就绪认证）：

```powershell
python -m plm_assistant.entrypoints.worker_windows C:\PLMTool\config\bootstrap.yaml --once
```

退出码2：参数不支持；退出码1：配置/来源/运行或生命周期拒绝；退出码0：持续模式实际收到STOPPED，或--once实际达到一轮LIMIT且全部句柄静止后释放本进程数据库。LIMIT不是服务已停止或正式验收通过。

停止信号由原适配器请求不再领取新任务并排空已知命令；不删除临时字节、不伪造取消/成功、不强杀线程。当前仅解释器SIGINT合成进程已验；真实外部Console Ctrl-C/Break、Windows服务SCM/硬终止仍待测试，不将本页作为生产服务安装或停机验收。

发现活心跳时拒绝关闭数据库并返回静态错误；非daemon线程保持其生命周期，不以观察超时猜已退出。数据库升级/备份、正式私钥保管和离线恢复不由本CLI自动执行。完整产品/Server2025/Debian13发行及Gate3仍待。
