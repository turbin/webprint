#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模拟打印机脚本
用于开发和测试环境中，当实际打印机不可用时使用
"""

import subprocess
import time
import os
import sys
import random
import threading
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mock-printer")

def mock_print(filepath, on_complete=None):
    """
    模拟打印文件
    模拟打印机的行为，但不实际打印任何内容
    
    Args:
        filepath: 要打印的文件路径
        on_complete: 打印完成后的回调函数，接收一个布尔参数表示成功与否
    """
    if not os.path.exists(filepath):
        logger.error(f"错误: 文件 {filepath} 不存在")
        if callable(on_complete):
            try:
                logger.info(f"执行回调函数(文件不存在): {filepath}")
                on_complete(False)
            except Exception as e:
                logger.error(f"执行回调函数失败: {str(e)}")
        return False
    
    filename = os.path.basename(filepath)
    logger.info(f"开始打印文件: {filename}")
    
    def print_process():
        # 模拟文件处理和打印过程
        try:
            file_size = os.path.getsize(filepath)
            # 根据文件大小模拟不同的打印时间
            print_time = max(2, min(10, file_size / 1024 / 100))
            
            # 显示打印进度
            for i in range(10):
                progress = (i + 1) * 10
                logger.info(f"打印进度: {progress}%")
                time.sleep(print_time / 10)
            
            # 模拟打印成功或失败 (95% 成功率)
            success = random.random() < 0.95
            
            if success:
                logger.info(f"文件 {filename} 打印成功")
                result = True
            else:
                logger.error(f"错误: 文件 {filename} 打印失败")
                result = False
            
            # 执行回调函数
            if callable(on_complete):
                try:
                    logger.info(f"执行回调函数(打印结果={result}): {filepath}")
                    on_complete(result)
                except Exception as e:
                    logger.error(f"执行回调函数失败: {str(e)}")
            
            return result
        except Exception as e:
            logger.error(f"打印过程中出错: {str(e)}")
            if callable(on_complete):
                try:
                    logger.info(f"执行回调函数(发生异常): {filepath}")
                    on_complete(False)
                except Exception as callback_error:
                    logger.error(f"执行回调函数失败: {str(callback_error)}")
            return False
    
    # 在单独的线程中执行打印过程
    logger.info(f"创建打印线程: {filepath}")
    t = threading.Thread(target=print_process)
    t.daemon = True
    t.start()
    logger.info(f"打印线程已启动: {filepath}")
    
    return True  # 返回True表示打印任务已成功启动

def print_file(filepath, on_complete=None):
    """兼容接口，供app.py调用"""
    return mock_print(filepath, on_complete)

def main():
    """主函数"""
    # 检查命令行参数
    if len(sys.argv) < 2:
        print("用法: python mock_printer.py <文件路径>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    # 检查文件是否存在
    if not os.path.exists(filepath):
        print(f"错误: 文件 {filepath} 不存在")
        sys.exit(1)
    
    # 创建事件用于等待打印完成
    print_done = threading.Event()
    result = [False]  # 使用列表存储打印结果
    
    def on_complete(success):
        result[0] = success
        print_done.set()
    
    # 模拟打印
    mock_print(filepath, on_complete)
    
    # 等待打印完成
    print_done.wait()
    
    # 返回适当的退出代码
    sys.exit(0 if result[0] else 1)

if __name__ == "__main__":
    main() 