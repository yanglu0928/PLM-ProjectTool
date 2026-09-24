# 打包、部署与发行约束

## 目标环境

- Windows 11。
- Windows Server 2025。
- Debian 13。
- x86-64 / AMD64。
- 完全离线安装与升级。

Windows 建议目录：`C:\PLMTool\{app,runtime,plugins,config,data,logs,license}`。

Linux 建议目录：`/opt/plmtool/{app,runtime,plugins,config,data,logs,license}`。

## 安装验收

三个目标系统都必须在断网环境完成 clean install、restart、license、create project、AI 配置、OCR 和 output 验证。

## 升级

固定流程：人工备份 → 维护模式 → 离线升级 → Migration → 启动 → 健康检查。

- 实施团队在升级前备份 PostgreSQL、data、config 和 license。
- 系统不提供自动回滚；失败后由实施团队人工恢复。
- 验证受支持旧版本、不支持版本、migration error 和 plugin update。

## Release Gate

发布前必须通过 Regression、Installation、Upgrade、Permission、Performance、License、Plugin、AI/RAG 测试。任一阻塞项失败不得发布。

## 版本说明与同步

- 发行内容从 `release/*` 分支同步到 `origin`，不得直接在 `main` 开发。
- 每个版本必须提供版本说明，至少包含版本号、发布日期、变更摘要、兼容性、安装/升级要求、Migration、已知问题和验证结果。
- 代码、Migration、配置模板、插件包清单、交付文档与版本说明必须对应同一版本，禁止仅发布二进制而缺少版本记录。
- 推送、合并或打标签前先确认远端状态；发生非快进或未知修改时停止并报告，禁止强制覆盖。

## 最低交付物

```text
Windows 11 / Windows Server 2025 离线发行包
Debian 13 离线发行包
数据库初始化包
数据库升级脚本
Plugin 包
License Request Tool
License 文件
安装工具
升级工具
配置模板
管理员手册
安装手册
升级手册
用户手册
Release Notes
Third Party License 清单
验收测试报告
PoC 报告
```

源码不交付客户，保存在本地 Git 和 GitHub Private Repository。
