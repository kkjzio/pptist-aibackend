from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
import os
import json
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
- 节可以有2~6个，最多10个
- 每个节内容数量只能有1~10个，尽量保证每个节的内容数不同
- 内容和节的数量可以根据主题灵活调整
- 不要添加任何注释或解释说明

输出格式为：
# PPT标题（只有一个）
## 章的名字
### 节的名字
- 内容1
- 内容2
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

# PPT封面页和目录页生成模板
cover_contents_template = """
你是一个专业的PPT内容生成助手，请根据给定的大纲内容，生成封面页和目录页的JSON内容。

输出格式要求如下：
- 每一页为一个独立 JSON 对象
- 每个 JSON 对象写在**同一行**
- 页面之间用两个换行符分隔
- 不要添加任何注释或解释说明

注意事项：
- 只生成封面页("cover")和目录页("contents")
- 每个text的介绍内容可以尽量丰富，但是不应该超过100字

示例格式（注意每个 JSON 占一行）：

{{"type": "cover", "data": {{ "title": "接口相关内容介绍", "text": "了解接口定义、设计与实现要点" }}}}

{{"type": "contents", "data": {{ "items": ["接口定义概述", "接口分类详情", "接口设计原则"] }}}}

请根据以下信息生成封面页和目录页：

语言：{language}
大纲内容：{content}
"""

cover_contents_prompt = PromptTemplate.from_template(cover_contents_template)

# PPT章节内容生成模板
section_content_template = """
你是一个专业的PPT内容生成助手，请根据给定的章节信息，生成该章节的过渡页和内容页的JSON内容。

输出格式要求如下：
- 每一页为一个独立 JSON 对象
- 每个 JSON 对象写在**同一行**
- 页面之间用两个换行符分隔
- 不要添加任何注释或解释说明

注意事项：
- 为每个章节生成一个过渡页("transition")
- 为章节下的每个节生成一个内容页("content")
- 每个text的内容可以尽量丰富，但是不应该超过100字

示例格式（注意每个 JSON 占一行）：

{{"type": "transition", "data": {{ "title": "接口定义", "text": "开始介绍接口的基本含义" }}}}

{{"type": "content", "data": {{ "title": "接口定义", "items": [ {{ "title": "基本概念", "text": "接口定义了一组方法的契约或规范，但不提供具体实现。它好比一个“蓝图”，规定了实现它的类必须具备哪些功能。" }}, {{ "title": "作用", "text": "接口的主要作用是实现多态和松耦合。它让不同类型的对象能以统一的方式被处理，提高了代码的灵活性、可扩展性和复用性。通过接口，系统各部分之间的依赖性降低，更易于维护和升级。" }} ] }}}}

请根据以下信息生成章节内容：

语言：{language}
章节标题：{section_title}
章节内容：{section_content}
"""

section_content_prompt = PromptTemplate.from_template(section_content_template)



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


def build_cover_contents_chain(model_name: str = None):
    """构建封面页和目录页生成链"""
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API Key 未配置")
    
    model_config = settings.get_model_config(model_name)
    llm = ChatOpenAI(
        temperature=model_config["temperature"],
        model=model_config["model"],
        openai_api_key=model_config["openai_api_key"],
        openai_api_base=model_config["openai_api_base"]
    )
    return cover_contents_prompt | llm | StrOutputParser()


def build_section_content_chain(model_name: str = None):
    """构建章节内容生成链"""
    if not settings.validate():
        raise HTTPException(status_code=500, detail="OpenAI API Key 未配置")
    
    model_config = settings.get_model_config(model_name)
    llm = ChatOpenAI(
        temperature=model_config["temperature"],
        model=model_config["model"],
        openai_api_key=model_config["openai_api_key"],
        openai_api_base=model_config["openai_api_base"]
    )
    return section_content_prompt | llm | StrOutputParser()




def parse_outline(content: str) -> dict:
    """解析大纲内容，提取标题和章节信息"""
    lines = content.strip().split('\n')
    result = {
        'title': '',
        'chapters': []
    }
    
    current_chapter = None
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('# '):  # PPT标题
            result['title'] = line[2:].strip()
        elif line.startswith('## '):  # 章节标题
            if current_chapter:
                result['chapters'].append(current_chapter)
            current_chapter = {
                'title': line[3:].strip(),
                'sections': []
            }
            current_section = None
        elif line.startswith('### '):  # 节标题
            if current_chapter:
                current_section = {
                    'title': line[4:].strip(),
                    'items': []
                }
                current_chapter['sections'].append(current_section)
        elif line.startswith('- '):  # 内容项
            if current_section:
                current_section['items'].append(line[2:].strip())
    
    # 添加最后一个章节
    if current_chapter:
        result['chapters'].append(current_chapter)
    
    return result


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
    """生成PPT内容（分步骤流式返回）"""
    logger.info(f"📄 收到内容生成请求: 模型={request.model}, 语言={request.language}")
    logger.info(f"📄 大纲内容长度: {len(request.content)} 字符")
    
    # 解析大纲
    try:
        outline_data = parse_outline(request.content)
        logger.info(f"📄 解析大纲成功: 标题={outline_data['title']}, 章节数={len(outline_data['chapters'])}")
    except Exception as e:
        logger.error(f"解析大纲失败: {str(e)}")
        raise HTTPException(status_code=400, detail="大纲格式解析失败")
    
    # 构建生成链
    try:
        cover_contents_chain = build_cover_contents_chain(request.model)
        section_content_chain = build_section_content_chain(request.model)
    except HTTPException as e:
        logger.error(f"构建生成链失败: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"构建生成链异常: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")
    
    async def structured_page_stream():
        page_count = 0
        
        try:
            # 第一步：生成封面页和目录页
            logger.info("🏠 开始生成封面页和目录页...")
            buffer = ""
            async for chunk in cover_contents_chain.astream({
                "language": request.language,
                "content": request.content
            }):
                buffer += chunk
                # 检查缓冲区中是否包含完整的页面分隔符 "\n\n"
                while "\n\n" in buffer:
                    page_content, separator, rest_of_buffer = buffer.partition("\n\n")
                    if page_content.strip():
                        page_count += 1
                        logger.debug(f"生成第 {page_count} 页内容（封面/目录）")
                        yield page_content + separator
                    buffer = rest_of_buffer
            
            # 处理剩余内容
            if buffer.strip():
                page_count += 1
                logger.debug(f"生成第 {page_count} 页内容（封面/目录最后一页）")
                yield buffer + "\n\n"
            
            # 第二步：为每个章节生成过渡页和内容页
            for chapter_idx, chapter in enumerate(outline_data['chapters']):
                logger.info(f"📖 开始生成第 {chapter_idx + 1} 章: {chapter['title']}")
                
                # 准备章节内容字符串
                section_content = f"## {chapter['title']}\n"
                for section in chapter['sections']:
                    section_content += f"### {section['title']}\n"
                    for item in section['items']:
                        section_content += f"- {item}\n"
                
                buffer = ""
                async for chunk in section_content_chain.astream({
                    "language": request.language,
                    "section_title": chapter['title'],
                    "section_content": section_content
                }):
                    buffer += chunk
                    # 检查缓冲区中是否包含完整的页面分隔符 "\n\n"
                    while "\n\n" in buffer:
                        page_content, separator, rest_of_buffer = buffer.partition("\n\n")
                        if page_content.strip():
                            page_count += 1
                            logger.debug(f"生成第 {page_count} 页内容（第{chapter_idx + 1}章）")
                            yield page_content + separator
                        buffer = rest_of_buffer
                
                # 处理剩余内容
                if buffer.strip():
                    page_count += 1
                    logger.debug(f"生成第 {page_count} 页内容（第{chapter_idx + 1}章最后一页）")
                    yield buffer + "\n\n"
            
            # 第三步：生成结束页
            logger.info("🎬 开始生成结束页...")
            page_count += 1
            logger.debug(f"生成第 {page_count} 页内容（结束页）")
            yield '{"type": "end"}'
            
            logger.info(f"PPT内容生成完成，总共生成 {page_count} 页")
            
        except Exception as e:
            error_msg = f"生成过程中出错: {str(e)}"
            logger.error(error_msg)
            yield f'{{"error": "{error_msg}"}}'

    return StreamingResponse(structured_page_stream(), media_type="text/event-stream")


# 添加健康检查端点
@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "message": "PPTist AI Backend is running"}


# 添加JSON文件读取端点
@router.get("/data/{filename}.json")
async def get_json_file(filename: str):
    """读取template目录下的JSON文件"""
    try:
        # 构建文件路径
        file_path = os.path.join("template", f"{filename}.json")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.warning(f"📁 文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail=f"文件 {filename}.json 不存在")
        
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"📄 成功读取文件: {filename}.json")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"🚫 JSON格式错误: {filename}.json - {str(e)}")
        raise HTTPException(status_code=400, detail=f"文件 {filename}.json 格式错误")
    except Exception as e:
        logger.error(f"🚫 读取文件失败: {filename}.json - {str(e)}")
        raise HTTPException(status_code=500, detail="服务器内部错误")


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
            "data": "/data/{filename}.json",
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
