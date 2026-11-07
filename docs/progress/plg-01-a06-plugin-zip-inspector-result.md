# PLG-01-A06：Plugin ZIP安全只读解析与签名Manifest联合验证结果

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- Phase/WBS：Phase 2 / PLG-01-A06
- 实施提交：`994a39a6644f247e95bd4c26950a14fe54748a3`（初始实现）、`80edd9f2cfe166c2b3cf9ff5e87ad7b780db5f41`?（EOCD边界补充见CR）、`dacd018ae5bde584ed1f16d0211ce19d8617c2ca`（A06测试fixture）、`6c3fbbe5c263f773a869bf19a4283eb49c7aecfa`（既有随机UUID测试稳定化）
- 验收提交：`6c3fbbe5c263f773a869bf19a4283eb49c7aecfa`
- GitHub Actions：[run 41582564698](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41582564698)

## 验收证据

本次全量验收在 GitHub hosted Windows Server 2025 runner 上完成，runner 工作区及任务临时目录在 D 盘；没有在用户本机或 C 盘运行。

- 13/13 workflow jobs 成功。
- 后端全量3,902项通过；后端wheel构建成功。
- 前端测试、类型检查/生产构建、PostgreSQL 18/pgvector sidecar重建成功。
- 同一提交构建Windows父包候选，并完成清洁解包、临时PostgreSQL生命周期smoke。
- A35候选分块交接成功。
- A17包内PlanVersion Edge/HTTPS/PostgreSQL flow成功；验证候选归档SHA-256：`ff223e20679361a37d33a6b215d0dc423d69b0f8c7de1e30830d66004bc74ba1`。该候选是非发行包，flow使用合成数据。
- A34离线包替换及显式人工恢复演练成功；旧/当前候选摘要和演练标记见对应run evidence artifact。没有在用户机器实际安装或启动产品服务。
- A06专项测试包含Manifest/entry_point匹配、完整归档签名绑定、路径与ZIP恶意结构/资源边界负例；它们随3,902项后端全量通过。

## 偏差与修正记录

- 首轮run 41581198290的两个失败来自Windows ZIP测试fixture路径被写入器规范化及EOCD字节字面量过度转义；修正方法与复验边界已在CR-PLG-004记录。
- 第二轮run 41581853457的唯一失败是既有能力证明测试随机UUID偶然包含禁用子串，导致敏感repr断言误报。以确定性UUID fixture消除随机碰撞；没有改变产品逻辑。此前各轮失败均在修复前先登记。
- 本次run 41582564698完成全量及下游集成链复验，上述失败条件已消除，A06在本WBS范围内关闭。

## 范围限制与未覆盖事项

- 只读检查归档字节、根Manifest、EntryPoint成员关系及整包detached签名；无磁盘解压或业务持久化。
- 不导入、保存、安装、启动或执行插件；不创建正式发布者密钥或生产信任材料。
- 不包含实际Windows 11设备验收、正式License/发布信任、Server 2025生产账户/服务验收、Debian 13验收、Gate 3、Pilot或正式Release证据。
- 结果只能表述为本WBS的PASS_SCOPE_LIMITED；不会解除上述阻断。

## 下一项

依据CR-PLG-004中持久注册留待后续独立WBS的边界，继续PLG-01-A07：包元数据原子登记Owner。此前指向OUT-01-A01-P03的路线已纠正；P03实际上已由提交e0b69bdc、run 41417503109完成。A07仍使用GitHub hosted runner D盘与合成包/签名，不接公开HTTP/Job，不持久化ZIP正文，不安装或执行插件。
