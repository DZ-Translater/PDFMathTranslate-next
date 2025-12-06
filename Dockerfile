# 使用 uv 官方镜像作为基础镜像
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# 设置工作目录
WORKDIR /app

# 暴露 GUI 端口
EXPOSE 7860

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    libgl1 \
    libglib2.0-0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# 复制所有项目文件（构建需要）
COPY . .

# 安装 Python 依赖
RUN uv sync --no-dev

# 预热 babeldoc 资源
RUN uv run babeldoc --version && uv run babeldoc --warmup

# 创建必要的目录
RUN mkdir -p /app/configs /app/pdf2zh_files

# 验证安装
RUN uv run python -c "import pdf2zh_next; print(f'pdf2zh-next version: {pdf2zh_next.__version__}')"

# 启动 GUI
# 配置文件路径: /app/configs/config.v3.toml
CMD ["uv", "run", "pdf2zh_next/gui.py"]
