# P08-A01 固定 KDF 双计算诊断

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15；脚本validation/aut-04-a12-p08-a01-kdf-pair/verify.py。

实际exit0，4批各20请求、20真实verify+20真实hash，计时后每批20新hash真实核验；同16实际KDF上界、峰值16/结束0，合成缓冲退出擦除，不打印或持久化密码/hash，无客户数据/外发。轮1串行/并行P95=1672.890/1275.076ms；轮2反序并行/串行=1262.386/1521.531ms。详细墙钟及方法限制见progress同名文件。

诊断正确性PASS；并行候选仍超过1秒，因此未接入正式实现。`http_performance_pass=null`明确未测HTTP，不用诊断exit0覆盖CR008原FAIL；history双verify/坏密码/正式服务/TLS/最低硬件未测。串行对照是每计算lease、生产是每请求lease；executor排队包含在请求耗时、不在capacity等待，不能报告无排队。

完整unit/19集成链/coverage/HTTP性能/wheel未重跑；本批无生产代码/依赖/API/Schema/权限变化，兼容0049，无升级。CR008/Gate/可用包未完成。下一同PhaseWeb登录客户端合同前置。
