#!/usr/bin/env python3
"""
PPTist AI Backend API 测试脚本
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查端点"""
    print("🔍 测试健康检查...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ 健康检查通过")
            print(f"响应: {response.json()}")
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False
    return True

def test_ppt_outline():
    """测试PPT大纲生成"""
    print("\n📝 测试PPT大纲生成...")
    
    data = {
        "model": "Qwen/Qwen3-32B",
        "language": "中文",
        "content": "人工智能在教育领域的应用",
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/tools/aippt_outline",
            json=data,
            stream=True
        )
        
        if response.status_code == 200:
            print("✅ 大纲生成请求成功")
            print("📄 生成的大纲内容:")
            print("-" * 50)
            
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk:
                    print(chunk, end='')
            print("\n" + "-" * 50)
        else:
            print(f"❌ 大纲生成失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def test_ppt_content():
    """测试PPT内容生成"""
    print("\n🎨 测试PPT内容生成...")
    
    # 使用示例大纲
    sample_outline = """# 人工智能在教育领域的应用
## 人工智能教育概述
### AI教育的定义与意义
- 人工智能技术在教育中的应用
- 提升教学效果和学习体验
- 推动教育现代化发展
### AI教育的发展历程
- 早期探索阶段
- 技术突破期
- 规模化应用期
## 具体应用场景
### 个性化学习
- 智能推荐学习内容
- 自适应学习路径
- 学习效果评估"""
    
    data = {
        "model": "Qwen/Qwen3-32B",
        "language": "中文",
        "content": sample_outline,
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/tools/aippt",
            json=data,
            stream=True
        )
        
        if response.status_code == 200:
            print("✅ 内容生成请求成功")
            print("🎯 生成的PPT页面:")
            print("-" * 50)
            
            page_count = 0
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk.strip():
                    page_count += 1
                    print(f"页面 {page_count}:")
                    try:
                        # 尝试解析JSON以美化输出
                        page_data = json.loads(chunk.strip())
                        print(json.dumps(page_data, ensure_ascii=False, indent=2))
                    except json.JSONDecodeError:
                        print(chunk.strip())
                    print("-" * 30)
            print(f"总共生成了 {page_count} 个页面")
        else:
            print(f"❌ 内容生成失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")

def main():
    """主测试函数"""
    print("🧪 PPTist AI Backend API 测试")
    print("=" * 50)
    
    # 测试服务器连接
    if not test_health():
        print("❌ 服务器未启动或无法连接")
        print("请先运行: python run.py")
        return
    
    # 测试大纲生成
    test_ppt_outline()
    
    # 等待一下再测试内容生成
    time.sleep(2)
    
    # 测试内容生成
    test_ppt_content()
    
    print("\n🎉 测试完成!")

if __name__ == "__main__":
    main()