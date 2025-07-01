#!/usr/bin/env python3
"""
快速API测试脚本

简单的测试脚本，用于验证PDF翻译API的基本功能。

使用方法:
    python tests/test_api_quick.py
    
或者作为模块运行:
    python -m tests.test_api_quick
"""

import json
import time
import requests
from pathlib import Path


def test_api_workflow():
    """测试完整的API工作流程"""
    
    base_url = "http://localhost:8000"
    
    print("🚀 开始API快速测试\n")
    
    # 1. 健康检查
    print("1️⃣ 检查API服务状态...")
    try:
        response = requests.get(f"{base_url}/api/health")
        response.raise_for_status()
        health = response.json()
        print(f"✅ API服务正常: {health['status']}")
    except Exception as e:
        print(f"❌ API服务不可用: {e}")
        print("请先启动API服务: python api_server.py")
        return False
    
    # 2. 查找测试文件
    print("\n2️⃣ 查找测试PDF文件...")
    test_dir = Path(__file__).parent.parent / "test" / "file"
    pdf_files = list(test_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("❌ 未找到测试PDF文件")
        return False
    
    test_file = pdf_files[0]
    print(f"✅ 使用测试文件: {test_file.name}")
    
    # 3. 上传文件
    print("\n3️⃣ 上传PDF文件...")
    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file.name, f, 'application/pdf')}
            response = requests.post(f"{base_url}/api/files/upload", files=files)
            response.raise_for_status()
            upload_result = response.json()
        
        file_id = upload_result["file_id"]
        print(f"✅ 文件上传成功: {upload_result['filename']}")
        print(f"   文件ID: {file_id}")
        print(f"   文件大小: {upload_result['size']} 字节")
        
    except Exception as e:
        print(f"❌ 文件上传失败: {e}")
        return False
    
    # 4. 启动翻译
    print("\n4️⃣ 启动翻译任务...")
    try:
        translation_config = {
            "file_id": file_id,
            "config": {
                "service": "claude-sonnet-4-20250514",
                "lang_from": "English",
                "lang_to": "Simplified Chinese", 
                "page_range": "First",  # 只翻译第一页
                "threads": 1,
                "no_dual": True,  # 只生成单语版本，节省时间
                "translate_table_text": False,  # 跳过表格翻译
                "watermark_output_mode": "No Watermark"
            }
        }
        
        response = requests.post(
            f"{base_url}/api/translate",
            json=translation_config,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        translate_result = response.json()
        
        task_id = translate_result["task_id"]
        print(f"✅ 翻译任务启动成功")
        print(f"   任务ID: {task_id}")
        
    except Exception as e:
        print(f"❌ 翻译启动失败: {e}")
        # 清理上传的文件
        try:
            requests.delete(f"{base_url}/api/files/{file_id}")
        except:
            pass
        return False
    
    # 5. 监控翻译进度
    print("\n5️⃣ 监控翻译进度...")
    max_wait = 120  # 最多等待2分钟
    start_time = time.time()
    
    try:
        while time.time() - start_time < max_wait:
            response = requests.get(f"{base_url}/api/task/{task_id}/status")
            response.raise_for_status()
            status = response.json()
            
            current_status = status["status"]
            progress = status.get("progress", 0)
            stage = status.get("stage", "")
            
            print(f"   📊 {current_status} - {progress}% - {stage}")
            
            if current_status == "completed":
                print("✅ 翻译完成!")
                result = status["result"]
                print(f"   耗时: {result.get('total_seconds', 0):.1f}秒")
                break
                
            elif current_status == "error":
                error_msg = status.get("error", "未知错误")
                print(f"❌ 翻译失败: {error_msg}")
                return False
                
            elif current_status == "cancelled":
                print("❌ 翻译被取消")
                return False
            
            time.sleep(2)  # 每2秒检查一次
        else:
            print("❌ 翻译超时")
            return False
            
    except Exception as e:
        print(f"❌ 监控翻译进度失败: {e}")
        return False
    
    # 6. 下载结果
    print("\n6️⃣ 下载翻译结果...")
    try:
        # 下载单语PDF
        response = requests.get(f"{base_url}/api/task/{task_id}/download/mono")
        response.raise_for_status()
        
        output_dir = Path(__file__).parent / "test_output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"translated_{test_file.stem}_{task_id[:8]}.pdf"
        with open(output_file, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ 翻译结果已保存: {output_file}")
        print(f"   文件大小: {len(response.content)} 字节")
        
    except Exception as e:
        print(f"❌ 下载结果失败: {e}")
        return False
    
    # 7. 清理资源
    print("\n7️⃣ 清理资源...")
    try:
        # 清理上传的文件
        response = requests.delete(f"{base_url}/api/files/{file_id}")
        if response.status_code == 200:
            print("✅ 上传文件已清理")
        
        # 清理任务文件
        response = requests.delete(f"{base_url}/api/task/{task_id}")
        if response.status_code == 200:
            print("✅ 任务文件已清理")
            
    except Exception as e:
        print(f"⚠️ 清理资源时出现问题: {e}")
    
    print("\n🎉 API测试成功完成!")
    return True


def test_error_scenarios():
    """测试错误场景"""
    
    base_url = "http://localhost:8000"
    
    print("\n🧪 测试错误处理场景...")
    
    # 测试1: 上传非PDF文件
    print("\n🔸 测试上传非PDF文件...")
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", mode='w') as f:
            f.write("This is not a PDF")
            f.flush()
            
            with open(f.name, 'rb') as file:
                files = {'file': ('test.txt', file, 'text/plain')}
                response = requests.post(f"{base_url}/api/files/upload", files=files)
        
        if response.status_code == 400:
            print("✅ 正确拒绝了非PDF文件")
        else:
            print(f"❌ 应该拒绝非PDF文件，但状态码是: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试上传非PDF文件时出错: {e}")
    
    # 测试2: 使用无效的文件ID启动翻译
    print("\n🔸 测试无效文件ID...")
    try:
        invalid_config = {
            "file_id": "invalid-file-id-12345",
            "config": {
                "service": "claude-sonnet-4-20250514",
                "lang_from": "English", 
                "lang_to": "Simplified Chinese"
            }
        }
        
        response = requests.post(
            f"{base_url}/api/translate",
            json=invalid_config,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 404:
            print("✅ 正确拒绝了无效的文件ID")
        else:
            print(f"❌ 应该拒绝无效文件ID，但状态码是: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试无效文件ID时出错: {e}")
    
    # 测试3: 查询不存在的任务
    print("\n🔸 测试查询不存在的任务...")
    try:
        response = requests.get(f"{base_url}/api/task/invalid-task-id/status")
        
        if response.status_code == 404:
            print("✅ 正确处理了不存在的任务查询")
        else:
            print(f"❌ 应该返回404，但状态码是: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试查询不存在任务时出错: {e}")
    
    print("✅ 错误处理测试完成")


if __name__ == "__main__":
    success = test_api_workflow()
    
    if success:
        test_error_scenarios()
        print("\n🌟 所有测试完成!")
    else:
        print("\n💥 主要测试失败，跳过错误处理测试")