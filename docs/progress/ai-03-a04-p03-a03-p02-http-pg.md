# AI-03-A04-P03-A03-P02：PromptVersion HTTP/PG18 合成整链

版本：0.1.0；日期：2026-10-02；状态：Windows 11 隔离 PostgreSQL 18 合成整链 PASS；正式生产装配仍阻塞。

依据：冻结 `AI_PROMPT_CREATE_VERSION`、P03-A03-P01 可选 HTTP 合同、CR-AI-007。新建随机隔离库，迁移至当前 head，植入纯合成管理员/普通用户/PromptTemplate；临时进程内 Ed25519 签名清单和受信发行元数据由测试注入 `PackagedPromptAdmission`。经实际 HTTP → Session/授权 → `PromptVersionAppendService` → PostgreSQL 同事务版本/审计/幂等收据：默认应用与普通用户均404，未列正文422且无版本/审计写入，列入正文201、ETag v1，原 Key 重放仍201但外层 trace 为新请求，改正文同 Key 409，许可失效403。库内恰一版本、一成功 Audit、一收据；随机数据库已删除，临时 PG 集群已正常停止。

Changed/Files：`validation/ai-03-a04-p03-a03-p02-http-pg/verify.py`、决策/本进度/状态。Migration：无新 Migration，仅临时库运行既有 head。API：无新变更，P01 的可选 Router 仍不挂生产。兼容与升级：默认404不变；未执行生产数据库升级。Tests：隔离 PG18 合成脚本 exit0；P01 后端全量2082项通过/3项既有跳过及开发 wheel PASS，本项未重跑全量（程序包源码未改），Golden Dataset 未运行（无模型推理）。

Known Issues：信任材料为纯合成且由测试注入，不代表真实内容审查、正式密钥/离线备份、安装包完整性或目标运行账户。`AI-03-A04-P03-A03-P03` 正式生产挂载前置未满足，仍保持关闭；Windows Server 2025/Debian 13、Gate 3/UAT/可用包未验。Next：转向不依赖正式签名仪式的 `AI-03-A05-P01` PromptVersion 激活前置/首次响应设计，正式挂载待受信材料和真实验收。
