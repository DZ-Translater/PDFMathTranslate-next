# 部署指南

本项目提供了多种部署方式，支持原有的 Gradio 界面和新的 FastAPI 前后端分离架构。

## 🚀 快速部署

### 方式 1: Docker Compose (推荐)

同时启动两个服务：

```bash
# 克隆项目
git clone https://github.com/PDFMathTranslate/PDFMathTranslate-next.git
cd PDFMathTranslate-next

# 使用 Docker Compose 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

服务访问地址：
- **Gradio 界面**: http://localhost:7860
- **FastAPI 界面**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

### 方式 2: 单独启动 API 服务器

```bash
# 构建 API 服务器镜像
docker build -f Dockerfile.api -t pdf2zh-api .

# 运行 API 服务器
docker run -d \
  --name pdf2zh-api \
  -p 8000:8000 \
  -v $(pwd)/pdf2zh_files:/app/pdf2zh_files \
  -v $(pwd)/config:/app/config \
  pdf2zh-api
```

### 方式 3: 传统 Gradio 部署

```bash
# 构建传统镜像
docker build -t pdf2zh .

# 运行 Gradio 界面
docker run -d \
  --name pdf2zh-gradio \
  -p 7860:7860 \
  -v $(pwd)/pdf2zh_files:/app/pdf2zh_files \
  -v $(pwd)/config:/app/config \
  pdf2zh
```

## ⚙️ 环境变量配置

### API 服务器环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | `0.0.0.0` | 绑定主机地址 |
| `PORT` | `8000` | API 服务器端口 |
| `LOG_LEVEL` | `info` | 日志级别 |
| `RELOAD` | `false` | 开发模式自动重载 |

### 翻译引擎配置

通过环境变量配置翻译服务：

```bash
# OpenAI
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"

# Azure OpenAI
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="your-endpoint"

# Google Translate
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"

# DeepL
export DEEPL_AUTH_KEY="your-auth-key"
```

## 🐳 生产环境部署

### 使用 Docker Compose 生产配置

创建 `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  pdf2zh-api:
    build: 
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - LOG_LEVEL=warning
    volumes:
      - pdf2zh_data:/app/pdf2zh_files
      - ./config:/app/config:ro
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - pdf2zh-api
    restart: always

volumes:
  pdf2zh_data:
```

### Nginx 配置示例

创建 `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server pdf2zh-api:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        
        # HTTP to HTTPS redirect
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        client_max_body_size 100M;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;

        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

## 🔧 本地开发

### 安装依赖

```bash
# 克隆项目
git clone https://github.com/PDFMathTranslate/PDFMathTranslate-next.git
cd PDFMathTranslate-next

# 安装基础依赖
pip install -e .

# 启动 API 服务器
python api_server.py

# 或者使用命令行工具
pdf2zh-api
```

### 开发模式启动

```bash
# 启用自动重载
RELOAD=true python api_server.py

# 或设置环境变量
export RELOAD=true
export LOG_LEVEL=debug
pdf2zh-api
```

## 📊 监控和日志

### 健康检查

```bash
# API 服务器健康检查
curl http://localhost:8000/api/health

# 响应示例
{
  "status": "healthy",
  "active_tasks": 2,
  "completed_tasks": 15
}
```

### 日志查看

```bash
# Docker Compose 日志
docker-compose logs -f pdf2zh-api

# 单个容器日志
docker logs -f pdf2zh-api
```

## 🔒 安全考虑

### 生产环境安全配置

1. **HTTPS 配置**: 使用 SSL/TLS 证书
2. **防火墙设置**: 只开放必要端口
3. **访问控制**: 配置 IP 白名单
4. **文件上传限制**: 设置合理的文件大小限制
5. **资源限制**: 配置内存和 CPU 限制

### 环境变量安全

```bash
# 使用 .env 文件管理敏感信息
cat > .env << EOF
OPENAI_API_KEY=sk-xxxxx
AZURE_OPENAI_API_KEY=xxxxx
DEEPL_AUTH_KEY=xxxxx
EOF

# 设置正确的权限
chmod 600 .env
```

## 🚨 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8000
   
   # 修改端口
   PORT=8001 python api_server.py
   ```

2. **内存不足**
   ```bash
   # 增加 Docker 内存限制
   docker run --memory=4g pdf2zh-api
   ```

3. **文件权限问题**
   ```bash
   # 确保目录权限正确
   chmod -R 755 pdf2zh_files static
   ```

4. **翻译服务配置错误**
   ```bash
   # 检查配置
   docker exec -it pdf2zh-api env | grep API_KEY
   ```

### 日志分析

```bash
# 查看错误日志
docker-compose logs pdf2zh-api | grep ERROR

# 实时监控
docker-compose logs -f --tail=100 pdf2zh-api
```

## 📈 性能优化

### 资源配置建议

- **CPU**: 最少 2 核，推荐 4 核以上
- **内存**: 最少 4GB，推荐 8GB 以上
- **存储**: SSD，预留足够空间用于临时文件

### 并发处理

API 服务器支持多任务并发处理，可以通过以下方式优化：

```bash
# 设置工作进程数
uvicorn api_server:app --workers 4 --host 0.0.0.0 --port 8000
```

## 🔄 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重新构建和启动
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```