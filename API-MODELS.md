# API 模型配置指南

本API服务支持通过环境变量配置的特定模型，提供简化且安全的部署方式。

## 🤖 支持的模型

### 1. GPT-4o Mini
- **模型名称**: `gpt-4o-mini`
- **提供商**: OpenAI
- **特点**: 快速、经济的GPT-4级别模型

### 2. Claude 3.5 Sonnet
- **模型名称**: `claude-3-5-sonnet-20240620`
- **提供商**: Anthropic
- **特点**: 高质量的长文本理解和翻译

## 🔧 环境变量配置

### GPT-4o Mini 配置

```bash
# OpenAI API 配置
export OPENAI_API_KEY="sk-your-openai-api-key-here"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选，默认值
```

### Claude 3.5 Sonnet 配置

```bash
# Anthropic API 配置 (通过 OpenAI 兼容接口)
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key-here"
export ANTHROPIC_BASE_URL="https://api.anthropic.com/v1"  # 可选，默认值
```

## 🚀 部署方式

### 方式 1: Docker 直接运行

```bash
# 使用 GPT-4o Mini
docker run -it --rm -p 8080:8080 \
  -e OPENAI_API_KEY="your-api-key" \
  -e OPENAI_BASE_URL="https://api.openai.com/v1" \
  yzg963/pdfmathtranslate-next

# 使用 Claude 3.5 Sonnet
docker run -it --rm -p 8080:8080 \
  -e ANTHROPIC_API_KEY="your-api-key" \
  -e ANTHROPIC_BASE_URL="https://api.anthropic.com/v1" \
  yzg963/pdfmathtranslate-next
```

### 方式 2: Docker Compose

编辑 `docker-compose.yml` 文件，取消注释并配置相应的环境变量：

```yaml
environment:
  - HOST=0.0.0.0
  - PORT=8080
  - LOG_LEVEL=info
  # 启用需要的模型配置
  - OPENAI_API_KEY=your_openai_api_key_here
  - OPENAI_BASE_URL=https://api.openai.com/v1
  # - ANTHROPIC_API_KEY=your_anthropic_api_key_here
  # - ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
```

然后运行：

```bash
docker-compose up -d pdf2zh-api
```

### 方式 3: 环境变量文件

创建 `.env` 文件：

```env
# API 服务配置
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=info

# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1

# Anthropic 配置  
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
```

使用环境变量文件运行：

```bash
docker run -it --rm -p 8080:8080 --env-file .env yzg963/pdfmathtranslate-next
```

## 🌐 Web 界面使用

1. **启动服务**后访问: http://localhost:8080

2. **翻译服务选择**:
   - 从下拉菜单选择 `gpt-4o-mini` 或 `claude-3-5-sonnet-20240620`
   - 界面会显示环境变量配置状态

3. **环境变量状态**:
   - ✅ 已配置: 环境变量已正确设置
   - ❌ 未配置: 需要设置相应的环境变量

4. **选择语言和其他选项**，然后开始翻译

## 🔒 安全注意事项

### API 密钥安全
- **生产环境**: 使用 Docker secrets 或 Kubernetes secrets
- **开发环境**: 使用 `.env` 文件（添加到 `.gitignore`）
- **CI/CD**: 使用环境变量或密钥管理服务

### 权限控制
```bash
# 设置 .env 文件权限
chmod 600 .env

# 避免在日志中暴露密钥
export OPENAI_API_KEY="$(cat /secure/path/openai.key)"
```

## 🛠️ 故障排除

### 1. 模型无法使用
检查环境变量是否正确设置：
```bash
# 检查环境变量
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# 在容器内检查
docker exec -it container_name env | grep API_KEY
```

### 2. API 调用失败
- 验证 API 密钥有效性
- 检查 Base URL 配置
- 确认网络连接正常

### 3. 界面显示"未配置"
重新启动容器，确保环境变量传递正确：
```bash
docker-compose down
docker-compose up -d
```

## 📊 监控和日志

### 查看服务状态
```bash
# 检查健康状态
curl http://localhost:8080/api/health

# 查看服务日志
docker-compose logs -f pdf2zh-api
```

### API 文档
服务启动后可访问交互式 API 文档：
- Swagger UI: http://localhost:8080/docs
- ReDoc: http://localhost:8080/redoc

## 🎯 使用建议

1. **模型选择**:
   - **GPT-4o Mini**: 适合快速、经济的翻译需求
   - **Claude 3.5 Sonnet**: 适合高质量、长文档翻译

2. **性能优化**:
   - 调整 `每秒请求数` 参数避免API限流
   - 大文档建议启用 `每部分最大页数` 选项

3. **质量控制**:
   - 使用 `自定义系统提示` 优化翻译质量
   - 开启 `增强兼容性` 处理复杂PDF格式

---

通过环境变量配置，您可以安全地使用这些先进的AI模型进行PDF翻译，无需在界面中输入敏感信息。