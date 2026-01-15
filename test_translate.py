#!/usr/bin/env python3
"""
PDF翻译API测试脚本

使用方式：
    python test_translate.py <pdf文件路径> [选项]

示例：
    python test_translate.py test.pdf
    python test_translate.py test.pdf --lang-to Japanese
    python test_translate.py test.pdf --pages "1-3" --service DeepSeek
    python test_translate.py test.pdf --first-page --no-dual
"""

import argparse
import sys
import time
from pathlib import Path

import requests


class PDFTranslateClient:
    """PDF翻译API客户端"""

    def __init__(self, base_url: str = "https://pdf2pdf.by.dianzhantech.com"):
        self.base_url = base_url
        self.session = requests.Session()

    def health_check(self) -> dict:
        """健康检查"""
        response = self.session.get(f"{self.base_url}/api/health")
        response.raise_for_status()
        return response.json()

    def upload_file(self, file_path: Path) -> dict:
        """上传PDF文件"""
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = self.session.post(
                f"{self.base_url}/api/files/upload", files=files
            )
            response.raise_for_status()
            return response.json()

    def start_translation(self, file_id: str, config: dict) -> dict:
        """启动翻译任务"""
        data = {"file_id": file_id, "config": config}
        response = self.session.post(
            f"{self.base_url}/api/translate",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        response = self.session.get(f"{self.base_url}/api/task/{task_id}/status")
        response.raise_for_status()
        return response.json()

    def download_result(self, task_id: str, file_type: str, output_path: Path) -> Path:
        """下载翻译结果"""
        response = self.session.get(
            f"{self.base_url}/api/task/{task_id}/download/{file_type}"
        )
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path

    def cleanup_file(self, file_id: str) -> dict:
        """清理上传的文件"""
        response = self.session.delete(f"{self.base_url}/api/files/{file_id}")
        response.raise_for_status()
        return response.json()

    def cleanup_task(self, task_id: str) -> dict:
        """清理任务"""
        response = self.session.delete(f"{self.base_url}/api/task/{task_id}")
        response.raise_for_status()
        return response.json()


def translate_pdf(
    pdf_path: str,
    base_url: str = "https://pdf2pdf.by.dianzhantech.com",
    lang_from: str = "English",
    lang_to: str = "Simplified Chinese",
    service: str = "DeepSeek",
    page_range: str = "All",
    pages: str = None,
    no_mono: bool = False,
    no_dual: bool = False,
    qps: int = 4,
    output_dir: str = None,
    cleanup: bool = True,
    timeout: int = 600,
):
    """执行PDF翻译"""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"[ERROR] 文件不存在: {pdf_path}")
        sys.exit(1)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = pdf_path.parent

    client = PDFTranslateClient(base_url)

    # 1. 健康检查
    print(f"[1/5] 检查API服务器 ({base_url})...")
    try:
        health = client.health_check()
        print(
            f"      服务器状态: {health['status']}, 活跃任务: {health['active_tasks']}"
        )
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] 无法连接到API服务器: {base_url}")
        print("        请先启动API服务器: python api_server.py")
        sys.exit(1)

    # 2. 上传文件
    print(f"[2/5] 上传文件: {pdf_path.name}...")
    upload_result = client.upload_file(pdf_path)
    file_id = upload_result["file_id"]
    print(f"      文件ID: {file_id}, 大小: {upload_result['size']} bytes")

    # 3. 构建配置并启动翻译
    config = {
        "lang_from": lang_from,
        "lang_to": lang_to,
        "service": service,
        "page_range": page_range if not pages else "Range",
        "page_input": pages,
        "no_mono": no_mono,
        "no_dual": no_dual,
        "qps": qps,
    }

    print(f"[3/5] 启动翻译任务...")
    print(f"      语言: {lang_from} -> {lang_to}")
    print(f"      服务: {service}")
    print(f"      页面: {pages if pages else page_range}")

    translate_result = client.start_translation(file_id, config)
    task_id = translate_result["task_id"]
    print(f"      任务ID: {task_id}")

    # 4. 监控进度
    print(f"[4/5] 等待翻译完成...")
    start_time = time.time()
    last_progress = -1

    while time.time() - start_time < timeout:
        status = client.get_task_status(task_id)
        current_status = status["status"]
        progress = int(status.get("progress", 0))
        stage = status.get("stage", "")

        if progress != last_progress:
            elapsed = time.time() - start_time
            print(f"      [{elapsed:.0f}s] {progress}% - {stage}")
            last_progress = progress

        if current_status == "completed":
            result = status["result"]
            print(f"      翻译完成! 耗时: {result['total_seconds']:.1f}秒")
            break
        elif current_status == "error":
            print(f"[ERROR] 翻译失败: {status.get('error', 'Unknown error')}")
            if cleanup:
                client.cleanup_file(file_id)
                client.cleanup_task(task_id)
            sys.exit(1)
        elif current_status == "cancelled":
            print("[ERROR] 翻译被取消")
            sys.exit(1)

        time.sleep(2)
    else:
        print(f"[ERROR] 翻译超时 ({timeout}秒)")
        sys.exit(1)

    # 5. 下载结果
    print(f"[5/5] 下载翻译结果...")
    downloaded_files = []

    result = status["result"]
    stem = pdf_path.stem

    if result.get("mono_pdf_path") and not no_mono:
        mono_output = output_dir / f"{stem}_mono.pdf"
        client.download_result(task_id, "mono", mono_output)
        downloaded_files.append(mono_output)
        print(f"      单语版: {mono_output}")

    if result.get("dual_pdf_path") and not no_dual:
        dual_output = output_dir / f"{stem}_dual.pdf"
        client.download_result(task_id, "dual", dual_output)
        downloaded_files.append(dual_output)
        print(f"      双语版: {dual_output}")

    # 清理
    if cleanup:
        client.cleanup_file(file_id)
        client.cleanup_task(task_id)
        print("      已清理服务器临时文件")

    print("\n[完成] 翻译成功!")
    for f in downloaded_files:
        print(f"  -> {f}")

    return downloaded_files


def main():
    parser = argparse.ArgumentParser(
        description="PDF翻译API测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_translate.py document.pdf
  python test_translate.py document.pdf --lang-to Japanese
  python test_translate.py document.pdf --pages "1-5"
  python test_translate.py document.pdf --first-page --no-dual
  python test_translate.py document.pdf --service SiliconFlowFree
        """,
    )

    parser.add_argument("pdf_file", help="要翻译的PDF文件路径")
    parser.add_argument(
        "--url", default="https://pdf2pdf.by.dianzhantech.com", help="API服务器地址"
    )
    parser.add_argument("--lang-from", default="English", help="源语言 (默认: English)")
    parser.add_argument(
        "--lang-to",
        default="Simplified Chinese",
        help="目标语言 (默认: Simplified Chinese)",
    )
    parser.add_argument(
        "--service", default="DeepSeek", help="翻译服务 (默认: DeepSeek)"
    )
    parser.add_argument("--pages", help="页面范围，如 '1-5' 或 '1,3,5'")
    parser.add_argument("--first-page", action="store_true", help="只翻译第一页")
    parser.add_argument("--first-5", action="store_true", help="只翻译前5页")
    parser.add_argument("--no-mono", action="store_true", help="不生成单语版本")
    parser.add_argument("--no-dual", action="store_true", help="不生成双语版本")
    parser.add_argument("--qps", type=int, default=4, help="每秒请求数 (默认: 4)")
    parser.add_argument("--output-dir", "-o", help="输出目录 (默认: 与输入文件同目录)")
    parser.add_argument(
        "--no-cleanup", action="store_true", help="不清理服务器临时文件"
    )
    parser.add_argument(
        "--timeout", type=int, default=600, help="超时时间秒 (默认: 600)"
    )

    args = parser.parse_args()

    # 处理页面范围
    page_range = "All"
    pages = args.pages
    if args.first_page:
        page_range = "First"
        pages = None
    elif args.first_5:
        page_range = "First 5 pages"
        pages = None

    translate_pdf(
        pdf_path=args.pdf_file,
        base_url=args.url,
        lang_from=args.lang_from,
        lang_to=args.lang_to,
        service=args.service,
        page_range=page_range,
        pages=pages,
        no_mono=args.no_mono,
        no_dual=args.no_dual,
        qps=args.qps,
        output_dir=args.output_dir,
        cleanup=not args.no_cleanup,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
