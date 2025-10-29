"""
API集成测试

测试PDF翻译API的完整工作流程：
1. 上传PDF文件
2. 启动翻译任务
3. 查询翻译进度
4. 下载翻译结果
5. 清理文件

运行方式：
    python -m pytest tests/test_api_integration.py -v

或者直接运行：
    python tests/test_api_integration.py
"""

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from typing import Dict

import pytest
import requests
from requests import Response


class APIClient:
    """API客户端封装"""

    def __init__(self, base_url: str = "https://pdf2pdf.by.dianzhantech.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def upload_file(self, file_path: Path) -> Dict[str, Any]:
        """上传PDF文件"""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = self.session.post(f"{self.base_url}/api/files/upload", files=files)
            response.raise_for_status()
            return response.json()

    def start_translation(self, file_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """启动翻译任务"""
        data = {"file_id": file_id, "config": config}
        response = self.session.post(f"{self.base_url}/api/translate", json=data, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        return response.json()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        response = self.session.get(f"{self.base_url}/api/task/{task_id}/status")
        response.raise_for_status()
        return response.json()

    def download_result(self, task_id: str, file_type: str) -> bytes:
        """下载翻译结果"""
        response = self.session.get(f"{self.base_url}/api/task/{task_id}/download/{file_type}")
        response.raise_for_status()
        return response.content

    def cleanup_file(self, file_id: str) -> Dict[str, Any]:
        """清理上传的文件"""
        response = self.session.delete(f"{self.base_url}/api/files/{file_id}")
        response.raise_for_status()
        return response.json()

    def cleanup_task(self, task_id: str) -> Dict[str, Any]:
        """清理任务文件"""
        response = self.session.delete(f"{self.base_url}/api/task/{task_id}")
        response.raise_for_status()
        return response.json()

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()


class TestAPIIntegration:
    """API集成测试类"""

    @classmethod
    def setup_class(cls):
        """测试类设置"""
        cls.client = APIClient()
        cls.test_files_dir = Path(__file__).parent.parent / "test" / "file"
        cls.output_dir = Path(__file__).parent / "test_output"
        cls.output_dir.mkdir(exist_ok=True)

        # 检查测试文件是否存在
        cls.test_pdf_files = list(cls.test_files_dir.glob("*.pdf"))
        if not cls.test_pdf_files:
            pytest.skip("没有找到测试PDF文件")

    def test_01_health_check(self):
        """测试健康检查接口"""
        result = self.client.health_check()
        assert "status" in result
        assert result["status"] == "healthy"
        assert "active_tasks" in result
        assert "completed_tasks" in result

    def test_02_upload_file(self):
        """测试文件上传接口"""
        test_file = self.test_pdf_files[0]

        # 上传文件
        result = self.client.upload_file(test_file)

        # 验证响应
        assert "file_id" in result
        assert "filename" in result
        assert "size" in result
        assert "message" in result
        assert result["filename"] == test_file.name
        assert result["size"] > 0
        assert result["message"] == "File uploaded successfully"

        # 保存文件ID用于后续测试
        self.uploaded_file_id = result["file_id"]

        print(f"✅ 文件上传成功: {result['filename']} (ID: {result['file_id']})")

    def test_03_start_translation_minimal_config(self):
        """测试启动翻译（最小配置）"""
        if not hasattr(self, "uploaded_file_id"):
            pytest.skip("需要先上传文件")

        # 最小翻译配置
        config = {
            "service": "claude-sonnet-4-20250514",
            "lang_from": "English",
            "lang_to": "Simplified Chinese",
            "page_range": "First",  # 只翻译第一页，节省时间
            "threads": 1,
            "no_dual": True,  # 只生成单语版本
        }

        # 启动翻译
        result = self.client.start_translation(self.uploaded_file_id, config)

        # 验证响应
        assert "task_id" in result
        assert "status" in result
        assert result["status"] == "started"

        # 保存任务ID用于后续测试
        self.task_id = result["task_id"]

        print(f"✅ 翻译任务启动成功: {result['task_id']}")

    def test_04_monitor_translation_progress(self):
        """测试翻译进度监控"""
        if not hasattr(self, "task_id"):
            pytest.skip("需要先启动翻译任务")

        max_wait_time = 300  # 最多等待5分钟
        start_time = time.time()

        print("🔄 监控翻译进度...")

        while time.time() - start_time < max_wait_time:
            status = self.client.get_task_status(self.task_id)

            # 验证状态结构
            assert "status" in status
            assert "progress" in status

            current_status = status["status"]
            progress = status.get("progress", 0)
            stage = status.get("stage", "")

            print(f"📊 状态: {current_status}, 进度: {progress}%, 阶段: {stage}")

            if current_status == "completed":
                assert "result" in status
                result = status["result"]
                assert "mono_pdf_path" in result or "dual_pdf_path" in result
                assert "total_seconds" in result

                self.translation_result = status
                print(f"✅ 翻译完成! 耗时: {result['total_seconds']:.2f}秒")
                return

            elif current_status == "error":
                error_msg = status.get("error", "Unknown error")
                pytest.fail(f"翻译失败: {error_msg}")

            elif current_status == "cancelled":
                pytest.fail("翻译被取消")

            # 等待一秒后继续检查
            time.sleep(1)

        pytest.fail(f"翻译超时（超过{max_wait_time}秒）")

    def test_05_download_results(self):
        """测试下载翻译结果"""
        if not hasattr(self, "translation_result"):
            pytest.skip("需要先完成翻译")

        result = self.translation_result["result"]

        # 下载单语PDF（如果存在）
        if result.get("mono_pdf_path"):
            mono_content = self.client.download_result(self.task_id, "mono")
            assert len(mono_content) > 0

            # 保存到本地文件
            mono_file = self.output_dir / f"translated_mono_{self.task_id}.pdf"
            with open(mono_file, "wb") as f:
                f.write(mono_content)

            print(f"✅ 单语PDF下载成功: {mono_file}")

        # 下载双语PDF（如果存在）
        if result.get("dual_pdf_path"):
            dual_content = self.client.download_result(self.task_id, "dual")
            assert len(dual_content) > 0

            # 保存到本地文件
            dual_file = self.output_dir / f"translated_dual_{self.task_id}.pdf"
            with open(dual_file, "wb") as f:
                f.write(dual_content)

            print(f"✅ 双语PDF下载成功: {dual_file}")

    def test_06_full_config_translation(self):
        """测试完整配置的翻译"""
        # 上传另一个测试文件
        if len(self.test_pdf_files) < 2:
            pytest.skip("需要至少2个测试文件")

        test_file = self.test_pdf_files[1]
        upload_result = self.client.upload_file(test_file)
        file_id = upload_result["file_id"]

        # 完整配置
        config = {
            "service": "claude-sonnet-4-20250514",
            "lang_from": "English",
            "lang_to": "Simplified Chinese",
            "page_range": "First",
            "threads": 2,
            "no_mono": False,
            "no_dual": False,
            "dual_translate_first": False,
            "use_alternating_pages_dual": False,
            "watermark_output_mode": "No Watermark",
            "custom_system_prompt_input": "请提供准确、流畅的中文翻译。",
            "min_text_length": 5,
            "primary_font_family": "Auto",
            "skip_clean": False,
            "disable_rich_text_translate": False,
            "enhance_compatibility": False,
            "split_short_lines": False,
            "short_line_split_factor": 0.5,
            "translate_table_text": True,
            "skip_scanned_detection": False,
            "ocr_workaround": False,
            "auto_enable_ocr_workaround": True,
            "max_pages_per_part": 0,
            "ignore_cache": False,
            "engine_settings": {},
        }

        # 启动翻译
        translate_result = self.client.start_translation(file_id, config)
        task_id = translate_result["task_id"]

        print(f"✅ 完整配置翻译任务启动: {task_id}")

        # 等待完成（简化版本，不等待太久）
        max_checks = 30
        for i in range(max_checks):
            status = self.client.get_task_status(task_id)
            if status["status"] in ["completed", "error", "cancelled"]:
                break
            time.sleep(2)

        # 清理
        self.client.cleanup_file(file_id)
        self.client.cleanup_task(task_id)

        print(f"✅ 完整配置测试完成")

    def test_07_cleanup(self):
        """测试清理功能"""
        if hasattr(self, "uploaded_file_id"):
            # 清理上传的文件
            result = self.client.cleanup_file(self.uploaded_file_id)
            assert "status" in result
            assert result["status"] == "cleaned"
            print(f"✅ 文件清理完成: {self.uploaded_file_id}")

        if hasattr(self, "task_id"):
            # 清理任务文件
            result = self.client.cleanup_task(self.task_id)
            assert "status" in result
            assert result["status"] == "cleaned"
            print(f"✅ 任务清理完成: {self.task_id}")

    def test_08_error_handling(self):
        """测试错误处理"""

        # 测试上传非PDF文件
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
            f.write("This is not a PDF file")
            f.flush()

            with pytest.raises(requests.exceptions.HTTPError):
                self.client.upload_file(Path(f.name))

        # 测试使用不存在的文件ID启动翻译
        config = {"service": "claude-sonnet-4-20250514"}
        with pytest.raises(requests.exceptions.HTTPError):
            self.client.start_translation("non-existent-id", config)

        # 测试查询不存在的任务状态
        with pytest.raises(requests.exceptions.HTTPError):
            self.client.get_task_status("non-existent-task")

        print("✅ 错误处理测试完成")


def run_manual_test():
    """手动运行测试的函数"""
    print("🚀 开始API集成测试...\n")

    # 检查API服务是否运行
    client = APIClient()
    try:
        health = client.health_check()
        print(f"✅ API服务正常运行: {health}")
    except Exception as e:
        print(f"❌ API服务未运行或无法连接: {e}")
        print("请先启动API服务: python api_server.py")
        return

    # 运行测试
    test_instance = TestAPIIntegration()
    test_instance.setup_class()

    try:
        print("\n1. 健康检查...")
        test_instance.test_01_health_check()

        print("\n2. 上传文件...")
        test_instance.test_02_upload_file()

        print("\n3. 启动翻译...")
        test_instance.test_03_start_translation_minimal_config()

        print("\n4. 监控进度...")
        test_instance.test_04_monitor_translation_progress()

        print("\n5. 下载结果...")
        test_instance.test_05_download_results()

        print("\n6. 完整配置测试...")
        test_instance.test_06_full_config_translation()

        print("\n7. 清理资源...")
        test_instance.test_07_cleanup()

        print("\n8. 错误处理测试...")
        test_instance.test_08_error_handling()

        print("\n🎉 所有测试通过！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        # 尝试清理资源
        try:
            if hasattr(test_instance, "uploaded_file_id"):
                test_instance.client.cleanup_file(test_instance.uploaded_file_id)
            if hasattr(test_instance, "task_id"):
                test_instance.client.cleanup_task(test_instance.task_id)
        except:
            pass


if __name__ == "__main__":
    run_manual_test()
