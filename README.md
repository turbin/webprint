# Web 打印系统

这是一个基于 Vue.js 和 Python Flask 的 Web 打印系统，支持上传 PDF、图片和 DOCX 文件进行打印。

## 功能特点

- 支持多文件同时上传
- 实时显示打印进度
- 文件类型限制（PDF、图片、DOCX）
- 打印队列管理
- 美观的用户界面

## 系统要求

- Node.js >= 16
- Python >= 3.8
- CUPS 打印系统
- LibreOffice（用于 DOCX 文件转换）
- Conda（用于 Python 环境管理）

## 安装步骤

1. 创建并激活 Conda 环境：
```bash
# 创建环境
conda create -n webprint python=3.8

# 激活环境
conda activate webprint
```

2. 安装前端依赖：
```bash
cd frontend
npm install
```

3. 安装后端依赖：
```bash
cd backend
pip install -r requirements.txt
```

4. 安装系统依赖：
```bash
# macOS
brew install cups libreoffice

# Ubuntu/Debian
sudo apt-get install cups libreoffice
```

## 运行项目

### 方式一：使用启动脚本（推荐）

1. 启动所有服务：
```bash
./start.sh
```

2. 停止所有服务：
```bash
./stop.sh
```

### 方式二：手动启动

1. 确保已激活 Conda 环境：
```bash
conda activate webprint
```

2. 启动后端服务：
```bash
cd backend
python app.py
```

3. 启动前端开发服务器：
```bash
cd frontend
npm run dev
```

4. 在浏览器中访问：http://localhost:5173

## 注意事项

- 确保系统已正确配置打印机
- DOCX 文件打印需要安装 LibreOffice
- 上传的文件会在打印完成后自动删除
- 使用 Conda 环境时，请确保在运行后端服务前已激活 `webprint` 环境
- 使用启动脚本时，日志文件将保存在 `logs` 目录下 