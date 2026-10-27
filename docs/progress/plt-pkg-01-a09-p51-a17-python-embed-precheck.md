# PLT-PKG-01-A09-P51-A17：Python embedded runtime 云端重建前置检查

- 日期：2026-10-27
- 状态：编码前检查通过，限于构建独立基础运行时组件。
- 基线来源：`STATUS.md`、`CR-EXEC-005`、`docs/progress/plt-pkg-01-a09-p51-a17-source-rebuild-input-audit.md`、Windows embedded candidate 现有 manifest 约束。

## 问题和范围

固定 Python 3.13.15 AMD64 embeddable ZIP 未进入仓库。按官方固定 URL 和 SHA-256 在 GitHub Windows Server 2025 runner 重取、核对并重建一个可作为新父包输入的独立基础运行时组件。

本项不做 app wheelhouse 依赖解析或 106 distributions 许可证汇总，不安装应用、不启动 PostgreSQL、不声称 Pilot 可运行；后续需将同源码提交的依赖轮子与 backend wheel 装入 packages 并完成 clean-path import。

## 输入与约束

- URL：`https://www.python.org/ftp/python/3.13.15/python-3.13.15-embed-amd64.zip`
- SHA-256：`d1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf`
- 目标：Python 3.13.15，AMD64 Windows embeddable distribution。
- 所有临时下载、解包、运行和输出只在 GitHub hosted runner 的 RUNNER_TEMP 中完成。
- 包含 package 目录占位并启用 site 以供后续锁定 wheelhouse 集成；清单标记非发行、未完成依赖集成、法律复核未完成。
- 不上传应用客户材料、Secret、本机缓存或 staging；Actions artifact 仅保留14天。

## 验收

云端验证下载长度非零且 SHA 完全匹配；拒绝危险/重复 archive path 与链接；存在 Python.exe、python313.dll、python313.zip、python313._pth、LICENSE；运行隔离 Python 核对版本、架构并导入关键标准库；清单列出运行时每个文件 SHA；重新打开最终 ZIP 对所有文件逐项读回校验。

## 回滚与后续

新组件不可变地存为 Actions artifact，不覆盖旧 P45 产物。失败时不发布 artifact，保留日志并修复。下一项是在该 verified runtime 中从冻结依赖生成 pinned wheelhouse 并接入当前 backend wheel，最终通过 embedded clean-path app import。
