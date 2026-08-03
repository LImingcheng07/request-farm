# request-farm

批量注册**免费额度账号**的零成本方案 —— 每个账号每天数百次免费模型请求，注册过程 **¥0 成本**（本地反检测浏览器打码验证码，不花验证码服务费）。

> 适用于提供"注册即送每日免费请求额度"的托管 AI agent 平台（free-tier daily request allowance）。

## ✨ 特性

- 💰 **零成本**：本地 Camoufox 反检测浏览器打码 Turnstile，不花一分钱验证码费
- 🔀 **双打码后端**：本地 solver（免费）或第三方 API（YesCaptcha 等），API 失败自动降级本地
- 🤖 **全自动**：建邮箱 → 打码 → 注册 → 收验证邮件 → 验证 → 登录 → 保存凭证
- 🔄 **多账号池**：凭证输出为 JSON，可对接任意多账号轮换代理（如 [keel-code-switch](https://github.com/cszf1/keel-code-switch) 风格的 Anthropic 兼容层）
- 🛡️ **风控友好**：注册请求走住宅代理（单 IP 注册会 429 限流），打码端不需要代理
- 📦 **零依赖**：纯 Python 标准库 + curl

## 🏗️ 架构

```
┌─ turnstile-solver（本地打码，免费）──────┐
│  Camoufox 反检测浏览器池 :5009           │
└──────────────┬───────────────────────────┘
               │ Turnstile token（30-60s）
┌──────────────▼───────────────────────────┐
│  kc_batch.py（本脚本）                   │
│  ① 临时邮箱建地址（可选 API 自动）       │
│  ② 打码（本地 / YesCaptcha 自动降级）    │
│  ③ 住宅代理注册 API                      │
│  ④ 自动收验证邮件 → 验证 → 登录          │
│  ⑤ 凭证写入 credentials/                 │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│  多账号轮换代理（可选）                  │
│  OpenAI/Anthropic 兼容 API + round-robin │
└──────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 配置环境变量

**打码后端二选一（API 失败自动降级本地）**：

```bash
# 方案 A：本地打码（免费，推荐）—— 需部署 turnstile-solver（见下）
export KC_CAPTCHA_BACKEND=local
export KC_SOLVER_URL=http://127.0.0.1:5009

# 方案 B：第三方打码 API（付费，无需本地资源；失败自动切 A）
export KC_CAPTCHA_BACKEND=yescaptcha
export KC_YESCAPTCHA_KEY=your_client_key
```

**目标平台配置**：

```bash
export KC_API_BASE=https://keelcode.ai                      # 平台 API 根地址
export KC_SITEKEY=0x4AAAAAAEDkke8x5GYWpYaB              # 注册页 Turnstile sitekey
export KC_SITE_URL=https://keelcode.ai/signup
export KC_PROXY="http://user:pass@host:port"           # 住宅代理（必须，注册防 429）
export KC_PASSWORD="YourStrongPass123!"
export KC_NAME=agent

# 可选：临时邮箱 API（cloudtempmail 兼容协议，自动建邮箱+收验证邮件）
export KC_MAIL_API=https://mail-api.example.com
export KC_MAIL_ADMIN_KEY=your_admin_key
export KC_MAIL_DOMAIN=example.com
```

### 2. 部署本地打码服务（可选，方案 A 需要）

需要 [Camoufox](https://github.com/daijro/camoufox)（反检测 Firefox）：

```bash
pip install camoufox quart rich patchright
python -m camoufox fetch
python api_solver.py --browser_type camoufox --thread 1 --host 0.0.0.0 --port 5009
```

### 3. 跑！

```bash
python3 kc_batch.py 10        # 批量注册 10 个账号
python3 kc_batch.py 1 kc      # 注册 1 个，邮箱前缀 kc
```

完成后凭证在 `credentials/accountN.json`：

```json
{
  "schemaVersion": 1,
  "apiBaseUrl": "https://keelcode.ai",
  "accessToken": "...",
  "authStyle": "bearer",
  "expiresAt": "2026-08-10T00:00:00.000Z",
  "user": {"name": "agent", "email": "..."}
}
```

## 🔌 对接多账号轮换代理

把凭证丢进任何支持账号池的代理（如 keel-code-switch 的 credentials/ 目录），即可获得 OpenAI/Anthropic 兼容 API + 自动轮换（401 标坏、429 冷却）：

```bash
cp credentials/account*.json keel-code-switch/credentials/
cd keel-code-switch && bun run proxy.ts --port 8082
```

```
Base URL: http://127.0.0.1:8082
API Key:  任意非空
```

## 📊 单账号收益示例

某平台免费档（每日 UTC 重置，按请求计费）：

| 模型 | 次/天 |
|------|-------|
| flash 模型 | 100 |
| 中型模型 ×3 | 50 ×3 |
| pro 模型 | 50 |
| 开源模型 | 50 |
| 旗舰模型 | 25 |
| **合计** | **375** |

10 个号 = 每天 3750 次免费请求。

## ⚠️ 免责声明

- 本项目仅用于技术学习与研究
- 目标平台 ToS 通常禁止批量注册/滥用，批量操作有账号被封风险，后果自负
- 请遵守目标平台服务条款与当地法律法规

## License

MIT
