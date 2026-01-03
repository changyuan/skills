# Social Media Publisher MCP

一个强大的 Model Context Protocol (MCP) 服务器，允许 Claude Code 将内容发布到多个主流社交媒体平台。

## ✨ 支持平台

| 平台 | ID | 功能描述 |
| :--- | :--- | :--- |
| **微信公众号** | `wechat` | 支持 Markdown 转 HTML，自动创建草稿，支持封面图 |
| **抖音** | `douyin` | 发布视频元数据，支持视频 ID 关联 |
| **小红书** | `xiaohongshu` | 发布图文笔记（标题 + 内容 + 图片） |
| **哔哩哔哩** | `bilibili` | 发布专栏文章，自动存入创作中心草稿箱 |
| **推特 (X)** | `twitter` | 发布推文，支持标签和 Thread 格式 |
| **飞书 (Lark)** | `feishu` | 自动创建云文档，支持 Markdown 内容同步 |

## 🚀 快速开始

### 1. 构建项目

```bash
cd mcp-server
npm install
npm run build
```

构建完成后，可执行文件位于 `mcp-server/dist/index.js`。

### 2. 配置 Claude Code

将以下配置添加到你的 Claude 配置文件中（通常位于 `~/.claude/config.json` 或项目根目录下的 `.claude_config.json`）。

```json
{
  "mcpServers": {
    "social-media-publisher": {
      "command": "node",
      "args": ["/绝对路径/到/你的/projects/skills/mcp-server/dist/index.js"],
      "env": {
        "WECHAT_APP_ID": "你的微信AppID",
        "WECHAT_APP_SECRET": "你的微信AppSecret",
        "DOUYIN_ACCESS_TOKEN": "可选",
        "DOUYIN_OPEN_ID": "可选",
        "XIAOHONGSHU_ACCESS_TOKEN": "可选",
        "BILIBILI_SESSDATA": "你的SESSDATA",
        "BILIBILI_BILI_JCT": "你的BILI_JCT",
        "TWITTER_APP_KEY": "可选",
        "TWITTER_APP_SECRET": "可选",
        "TWITTER_ACCESS_TOKEN": "可选",
        "TWITTER_ACCESS_SECRET": "可选",
        "FEISHU_APP_ID": "你的飞书AppID",
        "FEISHU_APP_SECRET": "你的飞书AppSecret"
      }
    }
  }
}
```

### 3. 本地开发

如果你想进行开发调试，可以使用 `dev` 模式：

```bash
cd mcp-server
npm run dev
```

## 🛠 环境变量详情

| 变量名 | 平台 | 说明 |
| :--- | :--- | :--- |
| `WECHAT_APP_ID` | 微信 | 公众号 AppID (服务号或订阅号) |
| `WECHAT_APP_SECRET` | 微信 | 公众号 AppSecret |
| `DOUYIN_ACCESS_TOKEN` | 抖音 | 开放平台 Access Token |
| `XIAOHONGSHU_ACCESS_TOKEN` | 小红书 | 合作伙伴 Token 或 Session |
| `BILIBILI_SESSDATA` | B站 | Cookie 中的 SESSDATA |
| `BILIBILI_BILI_JCT` | B站 | Cookie 中的 bili_jct (CSRF Token) |
| `TWITTER_APP_KEY` | Twitter | API Key (Consumer Key) |
| `FEISHU_APP_ID` | 飞书 | 自建应用 App ID |
| `FEISHU_APP_SECRET` | 飞书 | 自建应用 App Secret |

## 📦 项目结构

- `src/index.ts`: MCP 服务器核心逻辑
- `dist/`: 编译后的产物
- `package.json`: 依赖与脚本配置

## 📜 许可证

ISC
