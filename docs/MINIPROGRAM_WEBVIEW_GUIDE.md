# 全龄段多语言学习智能体 · 微信小程序（web-view 版）接入指南

> 本指南对应"先出 web-view 版"方案：用微信小程序的 `<web-view>` 组件内嵌 H5 演示页，
> 最快把现有能力搬进小程序。**核心差异**：小程序内麦克风不可用，录音改为"上传音频文件"，
> 评测与 Coze 指导全部由腾讯云函数服务端完成（避免前端跨域 CORS 与令牌暴露）。

---

## 1. 交付物清单

| 文件 | 作用 |
|---|---|
| `miniprogram_webview/` | 微信小程序壳（仅一个 web-view 页面，承载 H5） |
| `frontend/pronunciation_eval_demo_wv.html` | 增强版 H5：检测微信环境，自动降级为"上传音频"；评测+指导一次请求拿全 |
| `scf_xf_proxy_clean/index.py` | 云函数源码（已增强：评测后可选服务端调 Coze 生成指导） |
| `scf_xf_proxy_clean/xf_ise_proxy.zip` | 已重新打包的云函数（含 websocket 依赖，可直接上传覆盖） |
| `docs/MINIPROGRAM_WEBVIEW_GUIDE.md` | 本文件 |

---

## 2. 三步跑通（本地调试，最快）

> 本地调试可绕过备案要求，先把整条链路验证通。

1. **重部署云函数**（腾讯云 SCF 控制台）
   - 上传 `scf_xf_proxy_clean/xf_ise_proxy.zip` 覆盖原函数代码（Web 函数，Python 3.9）。
   - 环境变量：**保留** `XF_APPID` / `XF_APIKEY` / `XF_APISECRET`；**新增** `COZE_TOKEN`（Coze 个人设置里的 PAT）、`COZE_BOT_ID`（你的智能体 Bot ID）。
   - 确认函数配置里「公网访问 / CORS」已开启（之前已配）。
   - 验证：`curl -X POST <函数URL> -H 'Content-Type: application/json' -d '{}'` 应返回 `{"error":"missing reference_text"}`。

2. **托管 H5 到本地 HTTPS**
   - 用任意能起 HTTPS 的方式把 `pronunciation_eval_demo_wv.html` 暴露出来；本机调试最简单是用内网穿透/临时证书，或先在桌面浏览器直接打开验证（桌面支持实时录音）。
   - H5 顶部 `SCF_URL` 已是当前函数地址，一般无需改；只有换函数才改。

3. **微信开发者工具打开小程序壳**
   - 导入 `miniprogram_webview/` 目录。
   - `project.config.json` 的 `appid` 先用 `touristappid`（游客模式）可预览；但 **web-view 在游客模式不可用**，需改成你自己的真实小程序 AppID。
   - 改 `pages/index/index.js` 里 `h5Url` 为你托管的 H5 地址。
   - 开发者工具 → 详情 → 本地设置 → 勾选「不校验业务域名/TLS/HTTPS 证书」即可本地预览。

---

## 3. 正式发布（线上）必做：备案域名

微信小程序的 `<web-view>` 对承载域名有硬要求，**无法绕过**：

- H5 必须托管在 **已 ICP 备案的 HTTPS 域名** 下。
- 该域名必须加入小程序后台「开发 → 开发设置 → 业务域名」，并按提示下载校验文件放到域名根目录完成校验。
- ❌ 不可用：`github.io`、`vercel.app` 等境外/未备案域名（微信会拒绝加载）。
- ✅ 可用：国内云服务器 + 备案域名、腾讯云 COS/静态网站托管 + 备案域名 + CDN、阿里云 OSS 静态站等。

> 云函数 `*.ap-guangzhou.tencentscf.com` 与 `api.coze.cn` 是 H5 **内部 fetch** 的目标，
> 不受小程序「业务域名」限制（那是给 web-view 的 src 用的）；它们走的是公网 HTTPS，正常可达。
> 若 H5 内 fetch 报跨域，确认 SCF 的 CORS 已开启——评测与 Coze 现在都走 SCF 服务端，**不存在浏览器→Coze 的跨域**。

---

## 4. 关键设计点（为什么这样改）

### 4.1 录音降级为"上传音频"
微信 web-view 内的 H5 **无法可靠获取麦克风权限**（官方只支持原生 `wx.getRecorderManager`）。
H5 自动检测 `MicroMessenger` UA：在微信内隐藏"实时录音"按钮，只保留「上传音频」。
桌面浏览器仍可用实时录音。上传的音频由浏览器 `decodeAudioData` 解码后重采样为 16k WAV 再发送。

### 4.2 评测 + 指导合并为一次服务端请求
原 H5 在前端直连 `api.coze.cn`，存在两个问题：
- 浏览器跨域（Coze API 未必返回 CORS 头）；
- Coze PAT 暴露在客户端（安全风险）。

现改为：**云函数评测讯飞后，直接用服务端 `urllib` 调 Coze `/v3/chat` 生成指导**，随评测结果一并返回 `coach` 字段。
前端只认 `coach`；若云函数未配 `COZE_TOKEN/COZE_BOT_ID`，H5 顶部仍可填令牌走前端兜底（默认留空）。
这一改动同时让桌面 H5 演示页受益（不再依赖浏览器 CORS）。

### 4.3 功能齐全性（与完整智能体对照）
| 功能 | 落地 | 状态 |
|---|---|---|
| 全龄段自适应 | Coze Bot 人设 + 路由 | ✅ |
| 三板块多语种 | Coze 知识库 + 路由 | ✅ |
| 记忆 / 薄弱点复习 | Coze 数据表 | ✅ |
| RAG 知识锚定 | Coze 知识库 | ✅ |
| 发音评测（音素级，不转文字） | 小程序上传音频 → 云函数 → 讯飞 | ✅ |
| 发音指导 + 朗读 | 云函数调 Coze → 指导文本；TTS（桌面可用，web-view 降级为手动阅读） | ✅ |
| 护栏 / 防模板化 | Bot 人设 + 变量池 | ✅ |

**未丢失任何功能**；仅"评测编排"从 Coze 工作流内部挪到小程序/云函数（原因：Coze 拦截 tencentscf 域名，工作流 HTTP 节点报"设备环境异常"）。

---

## 5. 已知限制与后续升级

- **TTS 朗读**：web-view 内 `SpeechSynthesis` 可能不可用，页面已降级为"显示指导文本，提示手动阅读"。若需小程序内真朗读，后续改原生小程序用 TTS 服务（讯飞/腾讯云）返回音频 URL + `wx.createInnerAudioContext`。
- **上传录音体验**：比实时录音多一步"先录后传"。若要体验更顺，建议升级为 **原生小程序**（`wx.getRecorderManager` 原生录音 → `wx.request` 直传云函数），可参考 `docs/COZE_MIGRATION_GUIDE.md` §13.11 的数据流。
- **Coze 工作流**：你搭的 `yuyanxuexiluyouqi_1` 中"评测 HTTP 节点"因平台域名限制不可用于工作流内；教学对话能力通过 Coze Bot API（服务端代调）完整保留。
