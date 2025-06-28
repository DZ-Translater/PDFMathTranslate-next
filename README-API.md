# PDFMathTranslate API Server

这是一个基于 FastAPI 的前后端分离 PDF 翻译服务，替代了原有的 Gradio 界面。

## 功能特点

- 🌐 **前后端分离**: FastAPI 后端 + 现代 Web 前端
- 📄 **PDF 上传**: 支持拖拽上传和点击选择
- ⚙️ **丰富配置**: 支持所有原 Gradio 界面的翻译参数
- 📊 **实时进度**: 异步翻译处理，实时显示翻译进度
- 🔄 **任务管理**: 支持取消正在进行的翻译任务
- 📥 **结果下载**: 支持下载单语和双语 PDF 结果

## 快速开始

### 1. 安装依赖

```bash
# 安装基础项目依赖
pip install -e .

# 安装 API 服务器额外依赖
pip install -r requirements-api.txt
```

### 2. 启动服务器

```bash
python api_server.py
```

服务器将在 `http://localhost:8000` 启动

### 3. 访问界面

打开浏览器访问 `http://localhost:8000` 即可使用 Web 界面进行 PDF 翻译。

## API 接口文档

### 核心端点

- `GET /` - 前端界面
- `POST /api/translate` - 开始翻译任务
- `GET /api/task/{task_id}/status` - 获取任务状态
- `POST /api/task/{task_id}/cancel` - 取消任务
- `GET /api/task/{task_id}/download/{file_type}` - 下载结果文件
- `GET /api/languages` - 获取支持的语言列表
- `GET /api/services` - 获取支持的翻译服务列表

### 配置接口

- `GET /api/health` - 健康检查
- `DELETE /api/task/{task_id}` - 清理任务数据

详细的 API 文档可通过访问 `http://localhost:8000/docs` 查看 Swagger UI。

## 主要改进

### 相比 Gradio 界面的优势

1. **更好的用户体验**: 现代化的 Web 界面，响应式设计
2. **异步处理**: 非阻塞的翻译处理，支持多任务并发
3. **实时反馈**: 详细的进度显示和状态更新
4. **任务管理**: 可以取消、监控和清理翻译任务
5. **API 友好**: RESTful API 设计，便于集成其他应用

### 保持的功能

- 支持所有原有的翻译参数和选项
- 保持与原项目相同的翻译引擎和配置系统
- 支持所有翻译服务（OpenAI、Azure、Google 等）
- 保持相同的高质量翻译结果

## 目录结构

```
PDFMathTranslate-next/
├── api_server.py          # FastAPI 服务器主文件
├── requirements-api.txt   # API 服务器依赖
├── static/               # 前端静态文件
│   ├── index.html       # 主页面
│   ├── style.css        # 样式文件
│   └── script.js        # JavaScript 逻辑
└── pdf2zh_files/        # 翻译任务文件存储目录
```

## 开发说明

### 自定义配置

服务器使用与原项目相同的配置系统，支持通过环境变量和配置文件进行配置。

### 扩展功能

- 可以通过修改 `api_server.py` 添加新的 API 端点
- 前端界面可以通过修改 `static/` 目录下的文件进行定制
- 支持添加新的翻译引擎和参数

### 安全考虑

- 生产环境建议配置 HTTPS
- 可以添加身份验证和访问控制
- 建议设置文件上传大小限制和任务数量限制

## 故障排除

1. **端口冲突**: 修改 `api_server.py` 中的端口号
2. **依赖问题**: 确保已安装所有必需依赖
3. **翻译失败**: 检查翻译引擎配置和 API 密钥
4. **文件上传失败**: 检查文件大小和格式是否符合要求

## 与原项目的兼容性

这个 API 服务器完全兼容原项目的配置和翻译功能，可以作为 Gradio 界面的替代方案使用，同时保持所有原有功能。