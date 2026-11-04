# OUT-01-A01-P23 结果：已批准需求版本 DOCX 请求入口

日期：2026-11-04  
结果：PASS_SCOPE_LIMITED  
变更记录：CR-OUT-019

## 交付内容

在需求固定版本详情页增加内置 DOCX 请求入口，仅引用当前已批准的 RequirementVersion。固定 template、policy、operation，不把来源正文复制进客户端请求。前端复用 SessionClient same-origin POST、CSRF 与 Idempotency-Key；操作结果不确定时不自动换 Key 重试，并引导用户查看历史。

服务端仍是 Session、项目权限、License、版本状态及插件Publisher信任的唯一判定方。请求被受理不等于DOCX已生成、可下载或已验收；本项未执行插件、未生成文件，也未调用外部AI。

## Hosted 验收证据

GitHub Actions [run 41869866457](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41869866457) 完成，13/13 jobs success：

- Frontend：204/204 test files通过，typecheck与production build通过。
- Backend：4,022 tests通过，wheel构建通过。
- PG18/pgvector sidecar重建、embedded runtime组装、Windows父包候选及清洁解包/临时PostgreSQL生命周期通过。
- A17 packaged flow、A34 offline replacement/manual restore、A35 handoff、A50 hosted Edge source navigation通过。

首轮 run 41868957522 的前端测试文件存在 TypeScript 断言解析错误，已在 CR-OUT-019 先记录，再仅修复测试表达式并重新完成全链验收。

## 文件 / 兼容性 / 限制

- 无 ORM、Migration、API Contract 或默认后端路由挂载变化。
- 运行范围为 GitHub hosted runner；没有在用户本机或 C 盘运行程序/测试。
- 结果不构成 Windows 11 实机验收、正式Publisher信任、Gate 3、Pilot 或正式Release通过。
- 已知限制：包内正式Publisher清单为空，服务器在无可信Publisher时必须失败关闭；P23没有证明请求到达真实生产组合或产生DOCX。

## 下一项

P24：使用 GitHub hosted Edge，在合成会话与受控API响应下验证需求详情到DOCX请求操作、固定请求负载、提交成功/信任拒绝反馈与历史导航。不得使用客户数据，不得把合成API称作后端信任验收。
