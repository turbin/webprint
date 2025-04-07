#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试打印机功能的脚本
"""

import os
import sys
import time
import logging
import threading
import importlib.util
import pathlib

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("printer-test")

def import_mock_printer():
    try:
        # 获取当前文件的目录路径
        current_dir = pathlib.Path(__file__).parent.absolute()
        mock_printer_path = os.path.join(current_dir, "mock_printer.py")
        
        logger.info(f"尝试导入模拟打印机模块: {mock_printer_path}")
        
        # 检查文件是否存在
        if not os.path.exists(mock_printer_path):
            logger.error(f"模拟打印机模块文件不存在: {mock_printer_path}")
            return None
        
        # 动态导入mock_printer模块
        spec = importlib.util.spec_from_file_location("mock_printer", mock_printer_path)
        mock_printer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mock_printer)
        
        logger.info(f"模拟打印机模块加载成功")
        
        # 检查关键函数是否存在
        if hasattr(mock_printer, 'print_file'):
            logger.info("模块包含print_file函数")
        else:
            logger.warning("模块不包含print_file函数")
            
        if hasattr(mock_printer, 'mock_print'):
            logger.info("模块包含mock_print函数")
        else:
            logger.warning("模块不包含mock_print函数")
        
        return mock_printer
    except Exception as e:
        logger.error(f"导入模拟打印机模块失败: {str(e)}")
        return None

def test_printer_callback():
    """测试打印机回调功能"""
    mock_printer = import_mock_printer()
    if not mock_printer:
        logger.error("无法导入模拟打印机模块")
        return False
    
    # 创建测试文件
    test_file = os.path.join(os.path.dirname(__file__), "test_print.txt")
    with open(test_file, "w") as f:
        f.write("This is a test file for printing.\n" * 100)
    
    logger.info(f"创建测试文件: {test_file}")
    
    # 创建一个事件，用于等待打印完成
    print_done = threading.Event()
    result = [False]  # 用列表存储结果，以便在回调中修改
    
    def on_print_complete(success):
        logger.info(f"收到打印完成回调，结果: {success}")
        result[0] = success
        print_done.set()
    
    # 测试打印
    logger.info("开始测试打印")
    if hasattr(mock_printer, 'print_file'):
        logger.info("使用print_file函数打印")
        success = mock_printer.print_file(test_file, on_print_complete)
    else:
        logger.info("使用mock_print函数打印")
        success = mock_printer.mock_print(test_file, on_print_complete)
    
    if not success:
        logger.error("启动打印失败")
        return False
    
    logger.info("等待打印完成...")
    # 等待打印完成，最多等待30秒
    if print_done.wait(timeout=30):
        logger.info(f"打印完成，结果: {result[0]}")
    else:
        logger.error("等待打印超时")
        return False
    
    # 清理测试文件
    try:
        os.remove(test_file)
        logger.info("已删除测试文件")
    except:
        logger.warning("删除测试文件失败")
    
    return result[0]

if __name__ == "__main__":
    logger.info("开始测试模拟打印机功能")
    result = test_printer_callback()
    logger.info(f"测试结果: {'成功' if result else '失败'}")
    sys.exit(0 if result else 1) 