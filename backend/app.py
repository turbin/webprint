from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
import uuid
import shutil
from werkzeug.utils import secure_filename
import subprocess
import threading
from queue import Queue
import sys
import logging
import importlib.util
import pathlib
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("web-printer")

app = Flask(__name__)
# 增加最大内容长度限制，设为100MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
CORS(app)

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 配置临时分块文件夹
CHUNKS_FOLDER = 'uploads/chunks'
if not os.path.exists(CHUNKS_FOLDER):
    os.makedirs(CHUNKS_FOLDER)

# 打印队列
print_queue = Queue()
# 打印状态（文件ID -> 状态）
print_status = {}
# 锁定打印队列的互斥锁
queue_lock = threading.Lock()
# 当前是否有文件正在打印
currently_printing = False

# 使用模拟打印机
USE_MOCK_PRINTER = True

# 导入模拟打印模块
def import_mock_printer():
    try:
        # 获取当前文件的目录路径
        current_dir = pathlib.Path(__file__).parent.absolute()
        mock_printer_path = os.path.join(current_dir, "mock_printer.py")
        
        # 动态导入mock_printer模块
        spec = importlib.util.spec_from_file_location("mock_printer", mock_printer_path)
        mock_printer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mock_printer)
        
        logger.info(f"成功导入模拟打印机模块，路径: {mock_printer_path}")
        return mock_printer
    except Exception as e:
        logger.error(f"导入模拟打印机模块失败: {str(e)}")
        return None

# 预加载模拟打印机模块
mock_printer = import_mock_printer()

def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'jpg', 'jpeg', 'png', 'docx'}

def print_file(file_info):
    """打印文件"""
    global currently_printing
    
    file_id = file_info['id']
    filepath = file_info['path']
    filename = file_info['name']
    
    logger.info(f"准备打印文件: {filename} (ID: {file_id}), 路径: {filepath}")
    
    # 检查文件是否存在
    if not os.path.exists(filepath):
        logger.error(f"文件不存在: {filepath}")
        update_status(file_id, 'error')
        with queue_lock:
            currently_printing = False
        process_next_print_job()
        return False
    
    try:
        logger.info(f"开始打印文件: {filename}")
        update_status(file_id, 'printing')
        
        if USE_MOCK_PRINTER:
            # 使用模拟打印机
            if mock_printer:
                # 定义回调函数处理打印完成事件
                def print_complete_callback(success):
                    try:
                        logger.info(f"收到打印完成回调: {filename}, 结果: {success}")
                        if success:
                            logger.info(f"模拟打印成功: {filename}")
                            update_status(file_id, 'completed')
                        else:
                            logger.error(f"模拟打印失败: {filename}")
                            update_status(file_id, 'error')
                    except Exception as e:
                        logger.error(f"处理打印回调时出错: {str(e)}")
                    finally:
                        # 清理工作
                        try:
                            if os.path.exists(filepath):
                                logger.info(f"删除已打印的文件: {filepath}")
                                os.remove(filepath)
                            else:
                                logger.warning(f"打印后找不到文件: {filepath}")
                        except Exception as e:
                            logger.error(f"删除文件失败: {str(e)}")
                        
                        # 重置打印状态并处理下一个打印任务
                        with queue_lock:
                            global currently_printing
                            currently_printing = False
                            logger.info(f"重置打印状态并处理下一个打印任务")
                        process_next_print_job()
                
                # 检查是否支持回调函数版本
                if hasattr(mock_printer, 'print_file'):
                    # 使用带回调的接口
                    logger.info(f"使用带回调的模拟打印接口")
                    success = mock_printer.print_file(filepath, print_complete_callback)
                    
                    if not success:
                        logger.error(f"启动模拟打印失败: {filename}")
                        raise Exception("启动模拟打印失败")
                    
                    # 打印机将在后台处理，通过回调通知结果
                    # 这里直接返回，不执行finally块中的代码
                    return True
                else:
                    # 使用旧版接口
                    logger.info(f"使用传统的模拟打印接口")
                    success = mock_printer.mock_print(filepath)
                    if not success:
                        raise Exception("模拟打印失败")
            else:
                raise Exception("模拟打印机模块不可用")
        else:
            # 根据文件类型调用不同的打印命令
            if filepath.endswith(('.pdf')):
                subprocess.run(['lpr', filepath], check=True)
            elif filepath.endswith(('.jpg', '.jpeg', '.png')):
                subprocess.run(['lpr', filepath], check=True)
            elif filepath.endswith('.docx'):
                # 对于docx文件，首先转换为PDF
                logger.info(f"转换DOCX文件: {filename}")
                subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', filepath, '--outdir', UPLOAD_FOLDER], check=True)
                pdf_path = os.path.join(UPLOAD_FOLDER, os.path.splitext(filename)[0] + '.pdf')
                subprocess.run(['lpr', pdf_path], check=True)
                
                # 删除临时PDF文件
                try:
                    os.remove(pdf_path)
                except:
                    pass
                
        update_status(file_id, 'completed')
        logger.info(f"文件打印完成: {filename}")
        return True
    except Exception as e:
        logger.error(f"打印错误: {str(e)}")
        update_status(file_id, 'error')
        return False
    finally:
        # 如果使用的是带回调的接口，则不在此处理清理工作
        if not (USE_MOCK_PRINTER and mock_printer and hasattr(mock_printer, 'print_file')):
            logger.info(f"在finally块中处理清理工作")
            # 删除原始上传文件
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                else:
                    logger.warning(f"文件不存在，无法删除: {filepath}")
            except Exception as e:
                logger.error(f"删除文件失败: {str(e)}")
            
            # 重置打印状态
            with queue_lock:
                currently_printing = False
            
            # 检查队列中是否还有文件待打印
            process_next_print_job()

def update_status(file_id, status):
    """更新文件打印状态"""
    with queue_lock:
        print_status[file_id] = status
        logger.info(f"文件 {file_id} 状态更新为: {status}")

def get_status(file_id):
    """获取文件打印状态"""
    with queue_lock:
        return print_status.get(file_id, 'unknown')

def process_next_print_job():
    """处理队列中的下一个打印任务"""
    global currently_printing
    
    with queue_lock:
        if print_queue.empty() or currently_printing:
            return
        
        currently_printing = True
        next_file = print_queue.get()
    
    # 在新线程中执行打印任务
    print_thread = threading.Thread(target=print_file, args=(next_file,))
    print_thread.daemon = True
    print_thread.start()

def add_to_print_queue(file_info):
    """添加文件到打印队列"""
    with queue_lock:
        print_queue.put(file_info)
        print_status[file_info['id']] = 'queued'
        logger.info(f"文件 {file_info['name']} (ID: {file_info['id']}) 已添加到打印队列")
    
    # 如果没有正在打印的文件，开始处理队列
    process_next_print_job()

@app.route('/api/print', methods=['POST'])
def upload_file():
    """处理文件上传请求（普通上传方式）"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有上传文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '未选择文件'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # 生成唯一ID
            file_id = str(uuid.uuid4())
            
            # 确保上传目录存在
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
            
            # 保存文件到带有ID的路径，以避免名称冲突
            filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
            file.save(filepath)
            
            logger.info(f"文件上传成功: {filename} (ID: {file_id})")
            
            # 将文件信息添加到打印队列
            file_info = {
                'id': file_id,
                'name': filename,
                'path': filepath,
                'timestamp': time.time()
            }
            
            add_to_print_queue(file_info)
            
            return jsonify({
                'message': '文件已加入打印队列',
                'file_id': file_id,
                'status': 'queued'
            })
        
        return jsonify({'error': '不支持的文件类型'}), 400
    except Exception as e:
        logger.error(f"文件上传处理错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/chunk/init', methods=['POST'])
def init_chunked_upload():
    """初始化分块上传"""
    try:
        data = request.json
        if not data or 'filename' not in data or 'totalChunks' not in data or 'fileSize' not in data:
            return jsonify({'error': '缺少必要参数'}), 400
        
        filename = secure_filename(data['filename'])
        total_chunks = int(data['totalChunks'])
        file_size = int(data['fileSize'])
        
        # 验证分块数量和文件大小
        if total_chunks <= 0 or total_chunks > 1000:
            logger.warning(f"无效的分块数量: {total_chunks}")
            return jsonify({'error': '无效的分块数量'}), 400
            
        if file_size <= 0 or file_size > 100 * 1024 * 1024:  # 最大100MB
            logger.warning(f"无效的文件大小: {file_size}")
            return jsonify({'error': '文件大小超过限制'}), 400
        
        if not allowed_file(filename):
            logger.warning(f"不支持的文件类型: {filename}")
            return jsonify({'error': '不支持的文件类型'}), 400
        
        # 生成唯一ID
        file_id = str(uuid.uuid4())
        
        # 确保分块目录存在
        chunk_dir = os.path.join(CHUNKS_FOLDER, file_id)
        if not os.path.exists(chunk_dir):
            os.makedirs(chunk_dir)
        
        # 保存上传信息到metadata文件
        metadata = {
            'filename': filename,
            'id': file_id,
            'totalChunks': total_chunks,
            'fileSize': file_size,
            'receivedChunks': [],
            'timestamp': time.time()
        }
        
        with open(os.path.join(chunk_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)
        
        logger.info(f"初始化分块上传: {filename} (ID: {file_id}), 总块数: {total_chunks}, 文件大小: {file_size}字节")
        
        return jsonify({
            'message': '分块上传初始化成功',
            'file_id': file_id
        })
    except Exception as e:
        logger.error(f"初始化分块上传错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/chunk/upload', methods=['POST'])
def upload_chunk():
    """上传单个文件块"""
    try:
        if 'file' not in request.files or 'chunkIndex' not in request.form or 'fileId' not in request.form:
            return jsonify({'error': '缺少必要参数'}), 400
        
        file = request.files['file']
        
        # 检查是否有有效的文件内容
        if not file.content_length or file.content_length <= 0:
            return jsonify({'error': '空的文件分块'}), 400
            
        try:
            chunk_index = int(request.form['chunkIndex'])
        except ValueError:
            logger.warning(f"无效的分块索引: {request.form['chunkIndex']}")
            return jsonify({'error': '分块索引必须是整数'}), 400
            
        file_id = request.form['fileId']
        
        # 确认分块目录存在
        chunk_dir = os.path.join(CHUNKS_FOLDER, file_id)
        if not os.path.exists(chunk_dir):
            logger.warning(f"分块目录不存在: {chunk_dir}")
            return jsonify({'error': '无效的文件ID'}), 400
        
        # 加载元数据
        try:
            with open(os.path.join(chunk_dir, 'metadata.json'), 'r') as f:
                metadata = json.load(f)
                
            # 验证分块索引
            if chunk_index < 0 or chunk_index >= metadata['totalChunks']:
                logger.warning(f"分块索引越界: {chunk_index}, 总块数: {metadata['totalChunks']}")
                return jsonify({'error': f'分块索引越界'}), 400
                
        except Exception as e:
            logger.error(f"读取元数据失败: {str(e)}")
            return jsonify({'error': '无法加载文件元数据'}), 500
        
        # 保存分块
        chunk_path = os.path.join(chunk_dir, f'chunk_{chunk_index}')
        file.save(chunk_path)
        
        # 更新元数据
        if chunk_index not in metadata['receivedChunks']:
            metadata['receivedChunks'].append(chunk_index)
        
        with open(os.path.join(chunk_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)
        
        logger.info(f"接收到分块: {chunk_index}/{metadata['totalChunks']} (文件ID: {file_id})")
        
        # 检查是否所有分块都已接收
        all_received = len(metadata['receivedChunks']) == metadata['totalChunks']
        
        return jsonify({
            'message': '分块上传成功',
            'chunkIndex': chunk_index,
            'allReceived': all_received
        })
    except Exception as e:
        logger.error(f"分块上传错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/chunk/complete', methods=['POST'])
def complete_chunked_upload():
    """完成分块上传，合并文件块并加入打印队列"""
    try:
        data = request.json
        if not data or 'fileId' not in data:
            return jsonify({'error': '缺少文件ID'}), 400
        
        file_id = data['fileId']
        
        # 确认分块目录存在
        chunk_dir = os.path.join(CHUNKS_FOLDER, file_id)
        if not os.path.exists(chunk_dir):
            logger.warning(f"分块目录不存在: {chunk_dir}")
            return jsonify({'error': '无效的文件ID'}), 400
        
        # 加载元数据
        try:
            with open(os.path.join(chunk_dir, 'metadata.json'), 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            logger.error(f"读取元数据失败: {str(e)}")
            return jsonify({'error': '无法加载文件元数据'}), 500
        
        # 检查是否所有分块都已接收
        missing_chunks = []
        for i in range(metadata['totalChunks']):
            if i not in metadata['receivedChunks']:
                missing_chunks.append(i)
                
        if missing_chunks:
            logger.warning(f"文件不完整，缺少分块: {missing_chunks}")
            return jsonify({
                'error': f'文件不完整，缺少分块索引: {missing_chunks}'
            }), 400
        
        # 确保上传目录存在
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        # 合并文件
        filename = metadata['filename']
        filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
        
        try:
            with open(filepath, 'wb') as outfile:
                for i in range(metadata['totalChunks']):
                    chunk_path = os.path.join(chunk_dir, f'chunk_{i}')
                    if os.path.exists(chunk_path):
                        with open(chunk_path, 'rb') as infile:
                            outfile.write(infile.read())
                    else:
                        logger.error(f"找不到分块文件: {chunk_path}")
                        return jsonify({'error': f'找不到分块{i}'}), 500
        except Exception as e:
            logger.error(f"合并文件错误: {str(e)}")
            return jsonify({'error': f'合并文件错误: {str(e)}'}), 500
        
        # 检查合并后的文件大小
        if os.path.getsize(filepath) != metadata['fileSize']:
            logger.warning(f"合并后文件大小不匹配: 预期{metadata['fileSize']}字节，实际{os.path.getsize(filepath)}字节")
        
        # 清理分块
        try:
            shutil.rmtree(chunk_dir)
        except Exception as e:
            logger.warning(f"清理分块目录失败，将继续处理: {str(e)}")
        
        logger.info(f"合并完成: {filename} (ID: {file_id}), 大小: {os.path.getsize(filepath)}字节")
        
        # 将文件添加到打印队列
        file_info = {
            'id': file_id,
            'name': filename,
            'path': filepath,
            'timestamp': time.time()
        }
        
        add_to_print_queue(file_info)
        
        return jsonify({
            'message': '文件已组装并加入打印队列',
            'file_id': file_id,
            'status': 'queued'
        })
    except Exception as e:
        logger.error(f"完成分块上传错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/status/<file_id>', methods=['GET'])
def check_status(file_id):
    """检查文件打印状态"""
    try:
        status = get_status(file_id)
        return jsonify({
            'file_id': file_id,
            'status': status
        })
    except Exception as e:
        logger.error(f"获取状态错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/queue', methods=['GET'])
def get_queue():
    """获取打印队列状态"""
    try:
        with queue_lock:
            queue_size = print_queue.qsize()
            is_printing = currently_printing
        
        return jsonify({
            'queue_size': queue_size,
            'is_printing': is_printing
        })
    except Exception as e:
        logger.error(f"获取队列状态错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

@app.route('/api/download/<file_id>', methods=['GET'])
def download_file(file_id):
    """下载文件"""
    try:
        # 获取文件路径
        for filename in os.listdir(UPLOAD_FOLDER):
            if filename.startswith(f"{file_id}_"):
                logger.info(f"找到文件: {filename}")
                return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
        
        logger.warning(f"找不到文件ID: {file_id}")
        return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        logger.error(f"下载文件错误: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("Web打印服务启动")
    # 更改端口，避免与系统服务冲突（特别是macOS的AirPlay服务）
    app.run(debug=True, host='0.0.0.0', port=5001) 