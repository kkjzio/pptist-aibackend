# PPTist AI Backend

本项目为基于https://github.com/pipipi-pikachu/PPTist/issues/354#issuecomment-2863517189回答制作的ai生成后端，支持使用自定义url和模型。

基于 LangChain 和 FastAPI 的 AI 驱动 PPT 生成后端服务。

用于[PPTist](https://github.com/pipipi-pikachu/PPTist)的ai后端生成ppt使用

对应pptist的分支[57e21c3b4c28ce4195fbb20815f432d596c0e5c8](https://github.com/pipipi-pikachu/PPTist/tree/b3bbb75ea467690f0c71a4b6319720959cfdc84f)

请使用对应版本的的pptist使用该后端

## 功能特性

- 🤖 **AI 大纲生成**: 根据主题自动生成 PPT 大纲结构
- 🎨 **智能内容生成**: 基于大纲生成完整的 PPT 页面内容
- 🔄 **流式响应**: 支持实时流式数据传输
- 🌐 **RESTful API**: 标准的 HTTP API 接口
- 📚 **自动文档**: 自动生成 API 文档

## 技术栈

- **FastAPI**: 现代高性能 Web 框架
- **LangChain**: AI 应用开发框架
- **OpenAI**: GPT 模型支持
- **Pydantic**: 数据验证和序列化
- **uv**: 极速 Python 包管理器

## 快速开始

### 1. 环境准备

确保您的系统已安装 Python 3.13 或更高版本，并安装 [uv](https://docs.astral.sh/uv/)。

#### 安装 uv

```bash
# 使用 pip 安装
pip install uv

# 或使用 curl (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 PowerShell (Windows)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 安装依赖

使用 uv 安装项目依赖：
```bash
uv sync
```

### 3. 配置环境变量

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，设置您的 API 配置：
```bash
# OpenAI API 配置
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1

# AI 模型配置
DEFAULT_MODEL=gpt-4o-mini
DEFAULT_TEMPERATURE=0.7

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

### 4. 启动服务

使用 uv 启动服务：
```bash
uv run main.py
```

或者使用 uvicorn：
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

服务将在 http://localhost:8000 启动。

### 5. 访问 API 文档

打开浏览器访问 http://localhost:8000/docs 查看自动生成的 API 文档。

### 6.修改pptist代码

```bash
# 拉取源代码
git clone https://github.com/pipipi-pikachu/PPTist.git

# 切换分支
git check 57e21c3b4c28ce4195fbb20815f432d596c0e5c8
```

修改服务器地址：

+ 在`PPTist\src\services\index.ts`中修改`SERVER_URL`变量
+ 在`src\views\Editor\AIPPTDialog.vue`中，59行修改Select标签中的可选模型选项，145行的`const model = ref('GLM-4-Flash')`改为默认的模型



## API 接口

### 健康检查
```http
GET /health
```

### 生成 PPT 大纲
```http
POST /tools/aippt_outline
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "language": "中文",
  "require": "人工智能在教育领域的应用",
  "stream": true
}
```

### 生成 PPT 内容
```http
POST /tools/aippt
Content-Type: application/json

{
  "model": "gpt-4o-mini",
  "language": "中文",
  "content": "# PPT标题\n## 章节1\n### 小节1\n- 内容1",
  "stream": true
}
```

## 使用示例

### Python 客户端示例

```python
import requests
import json

# 生成大纲
def generate_outline():
    response = requests.post(
        "http://localhost:8000/tools/aippt_outline",
        json={
            "model": "gpt-4o-mini",
            "language": "中文",
            "require": "机器学习基础知识",
            "stream": True
        },
        stream=True
    )
    
    for chunk in response.iter_content(decode_unicode=True):
        if chunk:
            print(chunk, end='')

# 生成PPT内容
def generate_content(outline):
    response = requests.post(
        "http://localhost:8000/tools/aippt",
        json={
            "model": "gpt-4o-mini",
            "language": "中文",
            "content": outline,
            "stream": True
        },
        stream=True
    )
    
    for chunk in response.iter_content(decode_unicode=True):
        if chunk.strip():
            page_data = json.loads(chunk.strip())
            print(json.dumps(page_data, ensure_ascii=False, indent=2))
```

### 测试脚本

运行提供的测试脚本：
```bash
uv run test_api.py
```

## PPT 页面类型

生成的 PPT 内容支持以下页面类型：

- **封面页 (cover)**: 包含标题和副标题
- **目录页 (contents)**: 包含章节列表
- **过渡页 (transition)**: 章节间的过渡页面
- **内容页 (content)**: 具体的内容页面
- **结束页 (end)**: PPT 结束页

## 输出格式

### 大纲格式
```markdown
# PPT标题
## 章的名字
### 节的名字
- 内容1
- 内容2
- 内容3
```

### 页面内容格式
```json
{"type": "cover", "data": {"title": "标题", "text": "副标题"}}
{"type": "contents", "data": {"items": ["章节1", "章节2"]}}
{"type": "content", "data": {"title": "标题", "items": [{"title": "小标题", "text": "内容"}]}}
```

## 配置说明

### 支持的模型

- `gpt-4o`: OpenAI GPT-4 Omni 模型
- `gpt-4o-mini`: OpenAI GPT-4 Omni Mini 模型（默认）
- 其他兼容 OpenAI API 的模型

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 必填 |
| `OPENAI_BASE_URL` | API 基础URL | https://api.openai.com/v1 |
| `DEFAULT_MODEL` | 默认使用的 AI 模型 | gpt-4o-mini |
| `DEFAULT_TEMPERATURE` | 模型创造性参数 | 0.7 |
| `HOST` | 服务器监听地址 | 0.0.0.0 |
| `PORT` | 服务器端口 | 8000 |
| `DEBUG` | 调试模式开关 | false |

## 错误处理

API 会返回相应的 HTTP 状态码和错误信息：

- `200`: 请求成功
- `400`: 请求参数错误
- `500`: 服务器内部错误

流式响应中的错误会以文本形式返回。

## 开发指南

### 项目结构

```
pptist-aibackend/
├── main.py              # 主应用文件
├── test_api.py          # API 测试脚本
├── pyproject.toml       # 项目配置和依赖
├── .python-version      # Python 版本锁定
├── .env.example         # 环境变量模板
└── README.md           # 说明文档
```

### 扩展功能

您可以通过修改 `main.py` 中的模板和链来自定义 AI 行为：

1. 修改 `outline_template` 来调整大纲生成格式
2. 修改 `ppt_content_template` 来调整内容生成格式
3. 调整 `temperature` 参数来控制输出的创造性

## 许可证

本项目采用 MIT 许可证。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 支持

如果您在使用过程中遇到问题，请：

1. 检查 API Key 是否正确设置
2. 确认网络连接正常
3. 查看服务器日志获取详细错误信息
4. 提交 Issue 寻求帮助



## Reference

https://github.com/pipipi-pikachu/PPTist/issues/354#issuecomment-2863517189

https://github.com/pipipi-pikachu/PPTist/issues/354