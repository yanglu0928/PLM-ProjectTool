# AI-01-A05-P05-A03-P04-P02-A03-P02：探针 DNS／网络时限与租约

日期：2026-10-02；状态：内部限定范围 PASS。依据 CR-AI-002、ADR-007/012、DEC-20261002-661。

## 实施与预算

- DNS 解析使用当前受控 Python 解释器的 `-I -S` 固定标准库子进程，最小环境/关闭 stdin，不传 API Key、Secret、客户正文；3 秒超时后杀死并等待子进程。所有候选地址必须为公网，随后仍钉住一条数字地址，并以原域名 SNI/证书验签。生产真实出站仍须本轮明确授权。
- `PinnedHttpsProbeTransport.open` 起使用 20 秒单调截止；连接、TLS 握手、发送和每次接收共用剩余时间，不因响应每次滴流重置。只接受有界单义的 JSON 200、有效 Content-Length 和固定 `choices` 最小形状；禁止重定向、chunked、压缩/含糊响应，清零请求及响应可变缓冲。
- Provider Test 专属领取租约 120 秒，覆盖 20 秒网络与多次受限数据库事务的预算；不改变通用 Job 租约、fencing、失败重试或当前事实重验。真实故障切换时间可能增加，需在发行运维验收观察。

## 证据与边界

- Win11 定向16项：公共/私有 DNS 混合拒绝、真实隔离子进程超时、固定请求、重定向/超限/无长度/chunked/重复/长头、滴流截止、密钥清零与120秒租约。
- `validation/ai-01-a05-p04-a03-p02-synthetic-tls/verify.py` 本机 CA/TLS/固定探针及失败路径 PASS；`validation/ai-01-a05-p05-a03-p04-p02-a02-p02-worker-composition/verify.py` 新隔离 PG18 Job/Secret 审计与成功/失败 PASS。后端2023项运行/3跳过、开发 wheel SHA-256 `dc20f3d1b0fb3c9ff3fde9205b9eaff2fdace649fd7b5481607711f42fbe598e`。旧隔离 PG 簇已损坏，使用独立新簇且测试后停止。
- Python `subprocess.run` 的 timeout 覆盖子进程通信与等待，但不严格覆盖 OS 进程创建期；极端 OS 阻塞与真实目标账户/Server 2025 未验。P03 须独立 CR 扩展固定 SCM 角色和运行清单；P04 路由开启、真实外发、Gate 3、UAT 与可用包仍开放。无 Schema/API/依赖变更；未挂载 Worker 可停用，历史 Job/Audit 不删除。
