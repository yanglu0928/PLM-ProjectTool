# PLT-PKG-01-A09-P42：随包生产写模式经合成 HTTPS 验证

日期：2026-10-01；状态：`SYNTHETIC_PACKAGED_PLATFORM_WRITE_HTTPS_PASS / FORMAL_RELEASE_BLOCKED`。固定输入为 P33 非发行 ZIP（SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`）、P22 父包、P34 清洁暂存及 P41 新装演练。未变更 Gate 2 冻结架构、Schema、API 或 License 签名载荷。

编码前检查：正式产品公钥、目标账户凭据、域名证书、ACL/SCM、法律声明及目标平台验收尚不满足；不得在正式根安装或将合成密钥当发行信任锚。本项只验证随包 Python 进程自身的 `--platform-write` 入口，不再以仓库构造的 API 对象替代；只使用新 ASCII Temp 布局、合成公钥、当前测试账户内预先确认为不存在的固定 Vault 目标和临时 PG18。验收要求为固定候选不变、21,115 件初始布局重验、生产入口实际启动、Caddy HTTPS 登录/Session/失败关闭、测试资源清理；不以该结果关闭发行 Gate。

发现并修正既有诊断偏差：P27 生产启动预检脚本把公钥资源路径写成 `runtime/python/Lib/site-packages/...`，而 P33 实际嵌入式包位于 `runtime/python/packages/...`。本项修正预检常量并增加路径断言；此前“当前固定候选缺正式公钥”的结论仍成立，但旧路径不能用于证明未来供给是否正确。固定 ZIP 不修改，合成公钥仅注入另建的测试布局，另加 `SYNTHETIC-TRUST-NOT-FOR-RELEASE.txt` 标记。私钥只在测试进程内短暂生成，不写文件或打包。

Windows 11 真实隔离运行：P41 将固定包 21,115 件复制/Hash 复核至独立 Temp 布局；包内 PG18.6 建唯一临时角色/库，由临时管理员安装 vector，包内 Alembic 升至 head 并放入纯合成账号。当前 Windows 账户 12 个固定 SecretKey 目标及默认数据库 URL 目标在写入前全部确认为不存在；随机测试密钥按归属跟踪，测试后逐项比较、删除并回读缺失。包内 Python 3.13 以 `-I -B -m plm_assistant.entrypoints.serve_windows ... --platform-write` 独立启动，包内 Caddy 使用合成 localhost 证书：错误 Host 返回 421、错误 Origin 登录返回 403、正确登录返回 200 且 Cookie 带 Secure/HttpOnly/SameSite=lax、Session 返回 200、无正式 License 的受保护 Project 返回 403。没有安装或伪造有效 License。

首轮真实运行在普通角色安装 `vector` 扩展时失败；脚本清理后改由临时 PG 管理员执行，再完整重跑。最终完整重跑退出 0，报告 `SYNTHETIC_PACKAGED_PLATFORM_WRITE_HTTPS_PASS`、`fixed_candidate_unmodified=true`、`synthetic_layout_file_count_before_injection=21115`、`vault_key_count=12`、`formal_trust_provisioned=false`、`release_eligible=false`。随包 Python 与 Caddy、临时 PG 均实际启动；三类进程停止、临时文件删除和 13 个固定 Vault 目标不存在均由脚本断言。随后独立读回确认 `C:\PLMTool`、P42 测试布局、P42 运行目录不存在，`postgres.exe`/`caddy.exe` 无残留，13 个凭据目标均为 false。

定向测试：新烟测 2/2，修正后的生产预检 2/2，正式安装门禁回归 4/4；均由随包 Python 3.13 运行。普通系统 Python 3.14 未配项目 `httpx`/`cryptography`，其直接发现测试失败仅是解释器环境不符，不作为产品失败或 PASS 证据。

兼容性：只证明 Windows 11 本机隔离合成链；Windows Server 2025 未跑，Debian 13 按用户要求暂缓实机。无产品业务代码、API、Schema、Migration、SCM、正式根、正式证书或固定发行候选变更。升级说明：无数据迁移，不适用于已有安装升级。回滚可撤此验证脚本及预检路径修正；但若撤路径修正，未来真实公钥供给会被误判，因此建议保留。正式目标账户的公钥/证书/凭据供给、有效 License 激活、服务恢复、Ghostscript/NOTICE 法律义务、质量 Gate、UAT 与目标平台验收仍独立阻断；不得据此称可交付。

下一项 P43：针对固定候选收敛第三方发行声明与 Ghostscript 对应源码缺口，只做有来源、有证据的清单与可执行修复，不预判法律放行。
