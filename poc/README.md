# Phase 0 PoC 工作区

每个 PoC 使用独立目录，保存输入、脚本、非敏感证据及正式结论。仅在进入对应 WBS 后创建目录，避免产生无结论的空工作区。

## 当前 PoC

- `poc-01-python-313-dependencies/`：Python 3.13 三平台依赖与离线安装验证。
- `poc-02-postgresql-18-pgvector/`：PostgreSQL 18 + pgvector 离线部署与功能验证。
- `poc-05-document-ocr/`：Document + OCR 六类输入统一解析验证。

## 证据要求

- 命令和脚本必须可重复执行。
- 原始日志不得含密码、API Key、客户数据、MAC 地址或其他机器身份信息。
- 大型 wheelhouse、安装包、虚拟环境和模型文件不得提交 Git；只提交清单、Hash、执行日志和结论。
- 目标环境结果与本地预检结果必须分开记录。
