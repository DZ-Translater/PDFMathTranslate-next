# API 测试说明

这个目录包含了PDF翻译API的集成测试脚本。

## 测试文件

- `test_api_integration.py` - 完整的pytest集成测试套件
- `test_api_quick.py` - 快速验证API功能的简单脚本
- `requirements-test.txt` - 测试依赖包

## 运行测试前的准备

### 1. 启动API服务

首先确保API服务正在运行：

```bash
# 在项目根目录下
python api_server.py
```

API服务默认运行在 `http://localhost:8000`

### 2. 安装测试依赖

```bash
pip install -r tests/requirements-test.txt
```

### 3. 配置环境变量

确保已配置翻译服务的API密钥：

```bash
# 创建 .env.local 文件
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_BASE_URL="https://api.anthropic.com/v1"
```

## 运行测试

### 快速测试（推荐）

最简单的方式是运行快速测试脚本：

```bash
python tests/test_api_quick.py
```

这个脚本会：
- ✅ 检查API服务状态
- ✅ 上传测试PDF文件
- ✅ 启动翻译任务（只翻译第一页）
- ✅ 监控翻译进度
- ✅ 下载翻译结果
- ✅ 清理资源
- ✅ 测试错误处理

### 完整pytest测试

运行完整的测试套件：

```bash
# 在项目根目录下运行
python -m pytest tests/test_api_integration.py -v

# 或者运行所有测试
python -m pytest tests/ -v
```

### 测试特定功能

```bash
# 只测试文件上传
python -m pytest tests/test_api_integration.py::TestAPIIntegration::test_02_upload_file -v

# 只测试翻译流程
python -m pytest tests/test_api_integration.py::TestAPIIntegration::test_03_start_translation_minimal_config -v
```

## 测试输出

测试完成后，翻译结果会保存在 `tests/test_output/` 目录中。

### 文件命名规则

- `translated_mono_{task_id}.pdf` - 单语翻译结果
- `translated_dual_{task_id}.pdf` - 双语翻译结果

## 测试覆盖的功能

### ✅ 基础功能
- API健康检查
- PDF文件上传
- 翻译任务启动
- 翻译进度查询
- 结果文件下载
- 资源清理

### ✅ 配置测试
- 最小配置翻译
- 完整配置翻译
- 各种翻译选项

### ✅ 错误处理
- 上传非PDF文件
- 无效文件ID
- 不存在的任务查询
- 服务超时处理

## 故障排除

### API服务未启动

```
❌ API服务不可用: Connection refused
```

**解决方案**: 启动API服务 `python api_server.py`

### 缺少测试文件

```
❌ 未找到测试PDF文件
```

**解决方案**: 确保 `test/file/` 目录下有PDF测试文件

### API密钥未配置

翻译任务可能失败并显示认证错误。

**解决方案**: 配置正确的API密钥和Base URL

### 翻译超时

如果翻译任务运行时间过长：

1. 检查API密钥是否正确
2. 检查网络连接
3. 尝试使用更小的测试文件
4. 增加超时时间

## 自定义测试

可以修改测试配置：

```python
# 在 test_api_quick.py 中修改翻译配置
translation_config = {
    "file_id": file_id,
    "config": {
        "service": "claude-sonnet-4-20250514",
        "lang_from": "English",
        "lang_to": "Simplified Chinese",
        "page_range": "All",  # 翻译所有页面
        "threads": 4,         # 增加并发数
        # ... 其他配置
    }
}
```

## 注意事项

1. **测试成本**: 翻译测试会消耗API配额，建议使用小文件和有限页面
2. **并发限制**: 不要同时运行多个翻译测试，可能导致资源冲突
3. **清理资源**: 测试脚本会自动清理资源，但如果测试异常终止，可能需要手动清理

## 贡献

添加新测试时请：
1. 遵循现有的测试模式
2. 添加适当的错误处理
3. 确保清理测试资源
4. 更新此README文档