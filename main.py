from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
import os
import logging
from config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 验证配置
if not settings.validate():
    logger.error("❌ 配置验证失败！")
    if not settings.openai_api_key:
        logger.error("原因: OPENAI_API_KEY 环境变量未设置")
    elif settings.openai_api_key == "your-openai-api-key-here":
        logger.error("原因: OPENAI_API_KEY 仍为默认值，请设置真实的 API Key")
    elif not settings.openai_api_key.startswith(('sk-', 'sk_')):
        logger.error("原因: OPENAI_API_KEY 格式无效，应以 'sk-' 开头")
    logger.error("请检查 .env 文件或环境变量配置")
else:
    logger.info(f"✅ 配置验证通过 (模型: {settings.default_model})")

app = FastAPI(
    title="PPTist AI Backend",
    description="AI-powered PPT generation backend using LangChain and FastAPI",
    version="0.1.0"
)

# 配置 CORS 允许的源
allowed_origins = [
    "http://localhost:3000",  # React 开发服务器
    "http://localhost:5173",  # Vite 开发服务器
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8080",  # Vue 开发服务器
    "http://127.0.0.1:8080",
]

# 如果是调试模式，允许所有源（开发环境）
if settings.debug:
    allowed_origins = ["*"]
    logger.info("🌐 CORS: 调试模式 - 允许所有源访问")
else:
    logger.info(f"🌐 CORS: 生产模式 - 允许的源: {allowed_origins}")

# 添加 CORS 中间件配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 添加请求验证错误处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求验证错误，提供详细的错误信息"""
    logger.error(f"🚫 请求验证失败: {request.method} {request.url}")
    logger.error(f"🚫 错误详情: {exc.errors()}")
    
    # 提取请求体信息
    try:
        body = await request.body()
        if body:
            logger.error(f"🚫 请求体: {body.decode('utf-8')}")
    except Exception:
        pass
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "请求参数验证失败",
            "help": {
                "/tools/aippt_outline": "需要参数: model, language, content",
                "/tools/aippt": "需要参数: model, language, content"
            }
        }
    )

router = APIRouter()

# PPT大纲生成模板
outline_template = """你是用户的PPT大纲生成助手，请根据下列主题生成章节结构。

注意事项：
- 内容和节的数量可以根据主题灵活调整
- 不要添加任何注释或解释说明

输出格式为：
# PPT标题（只有一个）
## 章的名字
### 节的名字
- 内容1
- 内容2
- 内容3
### 节的名字
- xxxxx
- xxxxx
- xxxxx
### 节的名字
- xxxxx
- xxxxx
- xxxxx
- xxxxx

这是生成要求：{content}
这是生成的语言要求：{language}
"""

outline_prompt = PromptTemplate.from_template(outline_template)

# PPT内容生成模板
ppt_content_template = """
你是一个专业的PPT内容生成助手，请根据给定的大纲内容，生成完整的PPT页面内容结构。

页面类型包括：
- 封面页："cover"
- 目录页："contents"
- 内容页："content"
- 过渡页："transition"
- 结束页："end"

输出格式要求如下：
- 每一页为一个独立 JSON 对象
- 每个 JSON 对象写在**同一行**
- 页面之间用两个换行符分隔
- 不要添加任何注释或解释说明

注意事项：
- 目录页的items可以2~6个，最多10个
- 内容页的items只能有2~4个

示例格式（注意每个 JSON 占一行）：

{{"type": "cover", "data": {{ "title": "接口相关内容介绍", "text": "了解接口定义、设计与实现要点" }}}}

{{"type": "contents", "data": {{ "items": ["接口定义概述", "接口分类详情", "接口设计原则"] }}}}

{{"type": "transition", "data": {{ "title": "接口定义", "text": "开始介绍接口的基本含义" }}}}

{{"type": "content", "data": {{ "title": "接口定义", "items": [ {{ "title": "基本概念", "text": "接口是系统中模块通信的协议" }}, {{ "title": "作用", "text": "促进模块解耦，提高系统灵活性" }} ] }}}}

{{"type": "end"}}


请根据以下信息生成 PPT 内容：

语言：{language}
大纲内容：{content}
"""

ppt_content_prompt = PromptTemplate.from_template(ppt_content_template)


def build_outline_chain(model_name: str = None):
    """构建PPT大纲生成链"""
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API Key 未配置")
    
    model_config = settings.get_model_config(model_name)
    llm = ChatOpenAI(
        temperature=model_config["temperature"],
        model=model_config["model"],
        openai_api_key=model_config["openai_api_key"],
        openai_api_base=model_config["openai_api_base"]
    )
    return outline_prompt | llm | StrOutputParser()


def build_ppt_content_chain(model_name: str = None):
    """构建PPT内容生成链"""
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API Key 未配置")
    
    model_config = settings.get_model_config(model_name)
    llm = ChatOpenAI(
        temperature=model_config["temperature"],
        model=model_config["model"],
        openai_api_key=model_config["openai_api_key"],
        openai_api_base=model_config["openai_api_base"]
    )
    return ppt_content_prompt | llm | StrOutputParser()


# 请求模型定义
class PPTOutlineRequest(BaseModel):
    model: str = Field('gpt-4o-mini', description="使用的模型名称，例如 gpt-4o 或 gpt-4o-mini")
    language: str = Field(..., description="生成内容的语言，例如 中文、English")
    content: str = Field(..., max_length=50, description="生成的要求，不超过50字")
    stream: bool = True


class PPTContentRequest(BaseModel):
    model: str = Field('gpt-4o-mini', description="使用的模型名称，例如 gpt-4o 或 gpt-4o-mini")
    language: str = Field(..., description="生成内容的语言，例如 中文、English")
    content: str = Field(..., description="PPT大纲内容")
    stream: bool = True


# 路由实现
@router.post("/tools/aippt_outline")
async def generate_ppt_outline_stream(request: PPTOutlineRequest):
    """生成PPT大纲（流式返回）"""
    logger.info(f"📝 收到大纲生成请求: 模型={request.model}, 语言={request.language}, 要求={request.content}")
    
    try:
        chain = build_outline_chain(request.model)
    except HTTPException as e:
        logger.error(f"构建大纲生成链失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"构建大纲生成链异常: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")

    async def token_stream():
        try:
            logger.info("开始生成PPT大纲...")
            async for chunk in chain.astream({
                "content": request.content,
                "language": request.language
            }):
                yield chunk
            logger.info("PPT大纲生成完成")
        except Exception as e:
            error_msg = f"生成过程中出错: {str(e)}"
            logger.error(error_msg)
            yield f"错误: {error_msg}"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


@router.post("/tools/aippt")
async def generate_ppt_content_stream(request: PPTContentRequest):
    """生成PPT内容（流式返回）"""
    logger.info(f"📄 收到内容生成请求: 模型={request.model}, 语言={request.language}")
    logger.info(f"📄 大纲内容长度: {len(request.content)} 字符")
    
    try:
        chain = build_ppt_content_chain(request.model)
    except HTTPException as e:
        logger.error(f"构建内容生成链失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"构建内容生成链异常: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")
    
    async def page_stream():
        buffer = ""
        page_count = 0
        try:
            logger.info("开始生成PPT内容...")
            async for chunk in chain.astream({
                "language": request.language,
                "content": request.content
            }):
                buffer += chunk
                # 检查缓冲区中是否包含完整的页面分隔符 "\n\n"
                while "\n\n" in buffer:
                    page_content, separator, rest_of_buffer = buffer.partition("\n\n")
                    if page_content.strip():  # 确保不是由多个换行符产生的空内容
                        page_count += 1
                        logger.debug(f"生成第 {page_count} 页内容")
                        yield page_content + separator  # 保留分隔符
                    buffer = rest_of_buffer
            
            # 处理流结束后缓冲区中剩余的最后一部分内容（如果LLM输出末尾没有 \n\n）
            if buffer.strip():
                page_count += 1
                logger.debug(f"生成第 {page_count} 页内容（最后一页）")
                yield buffer.strip()
            
            logger.info(f"PPT内容生成完成，总共生成 {page_count} 页")
        except Exception as e:
            error_msg = f"生成过程中出错: {str(e)}"
            logger.error(error_msg)
            yield f'{{"error": "{error_msg}"}}'

    return StreamingResponse(page_stream(), media_type="text/event-stream")


# 添加健康检查端点
@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "message": "PPTist AI Backend is running"}


# 注册路由
app.include_router(router)


# 根路径
@app.get("/")
async def root():
    return {
        "message": "Welcome to PPTist AI Backend",
        "version": "0.1.0",
        "endpoints": {
            "outline": "/tools/aippt_outline",
            "content": "/tools/aippt",
            "health": "/health",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    if not settings.validate():
        logger.error("❌ 启动失败: OpenAI API Key 未配置或无效")
        logger.error("请设置 OPENAI_API_KEY 环境变量或创建 .env 文件")
        logger.error("可以复制 .env.example 为 .env 并修改其中的 API Key")
        exit(1)
    
    logger.info(f"🚀 启动 PPTist AI Backend...")
    logger.info(f"📡 服务器地址: http://{settings.host}:{settings.port}")
    logger.info(f"📚 API 文档: http://{settings.host}:{settings.port}/docs")
    
    try:
        uvicorn.run(
            "main:app",  # 使用字符串导入路径以支持 reload 功能
            host=settings.host,
            port=settings.port,
            reload=settings.debug
        )
    except Exception as e:
        logger.error(f"❌ 启动失败: {str(e)}")
        logger.error("请检查端口是否被占用或其他启动问题")
        raise
