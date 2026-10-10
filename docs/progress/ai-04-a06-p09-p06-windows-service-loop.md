# AI-04-A06-P09-P06 Windows 真实服务循环验证

日期：2026-10-03；状态：`WINDOWS_SERVICE_LOOP_PASS`；依据 CR-AI-019、DEC-764～769。验证对象为 P05 已完成的生产对象图和实际 Windows SCM 服务入口，本项未修改公开 API、Schema、生产代码或第三方依赖。

Windows 11 / PostgreSQL 18.6 一次性数据库中，以纯合成项目、文档、Prompt、Egress 授权、AI Task、License 与 Provider 凭据启动实际 `AI_PROVIDER_WORKER` 服务循环。Provider Key 通过真实 AES-GCM Secret Store 加密保存并按精确版本解析；业务 Adapter 使用生产 DNS/IP pinning、SNI、TLS 与响应上限逻辑，但连接被测试专用 connector 定向至本机 HTTPS 服务，证书链由临时 CA 验证，未访问真实 Provider、未使用真实 Key、未外发客户数据。

结果：一个业务 Task 仅发送一次并原子形成一个 Invocation、一个 `NOT_FORMAL_FACT` Suggestion 和一次最小 Secret Access Audit；服务收到停止信号后等待当前有界调用完成，不再进入下一周期，运行标记删除、维护准入释放且数据库连接池完成 dispose。验证输出 `AI_04_A06_P09_P06_WINDOWS_SERVICE_LOOP_PASS`。

首轮验证因临时 CA/服务器证书缺少 Windows/OpenSSL 严格链验证要求的 KeyUsage/EKU 而在 TLS 握手阶段失败关闭；只补齐验证夹具的 CA/Server KeyUsage、ServerAuth EKU、SKI/AKI 后，用全新一次性数据库完整重跑通过。没有关闭证书校验、降低 TLS 或放宽生产代码。

回归与构建：后端全量 2307 项通过、3 项既有条件跳过，另有 2944 个子测试通过；wheel 807 项，包含业务 Execution Policy 与 Windows Worker 入口，SHA-256 `1f9a5b903fce940c663e7118912ccf00fd76119f385f6334d8fb2680c817d75b`。首次全量测试分别误用缺 pytest 的运行环境和缺产品依赖的测试工具环境，均未进入测试执行；复用既有产品依赖并加入既有测试工具路径后全量通过。首次构建命令被仓库根 `build/` 包名遮蔽，改用既有 `pip wheel --no-deps --no-build-isolation` 成功，未增加依赖。

兼容/升级/回滚：无新 Migration、配置字段或历史数据变化；P05 的 Probe-only 与业务策略配对行为保持。回滚仍为停止 AI Worker、移除业务策略并保留 Task/Invocation/Suggestion/Audit 历史，RUNNING 必须先对账。Windows Server 2025 尚未执行本闭环，Debian 13 按用户指令不验证但仍为正式兼容目标；正式 Provider、正式 License/Prompt 信任材料、AI 质量/性能、UAT、Gate 3 和可交付程序包仍需后续客观证据。

Next：`AI-05-A01` 核查冻结 AI Task/Job/Suggestion API 与现有前端缺口，规划用户可见的提交、进度、失败/取消/重试、建议定位与人工确认工作台；不得让建议自动成为正式业务事实。
