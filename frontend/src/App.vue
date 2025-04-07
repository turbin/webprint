<template>
  <div class="app-container">
    <h1>文件打印系统</h1>
    <div class="upload-container">
      <input type="file" id="file-input" multiple @change="handleFileChange" ref="fileInput"
             accept=".pdf,.jpg,.jpeg,.png,.docx" class="file-input" />
      <label for="file-input" class="file-label">
        选择文件上传
      </label>
      <span class="file-types">支持: PDF, JPG, PNG, DOCX</span>
    </div>

    <div v-if="selectedFiles.length > 0" class="file-list">
      <h3>文件列表：</h3>
      <ul>
        <li v-for="(file, index) in selectedFiles" :key="index" class="file-item">
          <div class="file-info">
            <span class="file-name">{{ file.name }} <span class="file-size">({{ formatFileSize(file.size) }})</span></span>
            <span class="file-status" :class="file.status">{{ getStatusText(file.status) }}</span>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar" :style="{ width: file.progress + '%' }"></div>
          </div>
        </li>
      </ul>
    </div>

    <div class="queue-info" v-if="queueInfo.queue_size > 0 || queueInfo.is_printing">
      <div class="queue-status">
        <span>打印队列: {{ queueInfo.queue_size }} 个文件等待打印</span>
        <span v-if="queueInfo.is_printing" class="printing-indicator">正在打印</span>
      </div>
    </div>

    <div class="actions">
      <button @click="uploadFiles" class="upload-button" :disabled="selectedFiles.length === 0 || uploading">
        {{ uploading ? '上传中...' : '开始打印' }}
      </button>
      <button @click="clearFiles" class="clear-button" :disabled="selectedFiles.length === 0 || uploading">
        清空列表
      </button>
    </div>

    <div v-if="message" class="message" :class="messageType">
      {{ message }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      selectedFiles: [],
      uploading: false,
      message: '',
      messageType: 'info',
      completedUploads: 0,
      queueInfo: {
        queue_size: 0,
        is_printing: false
      },
      uploadedFiles: [], // 存储已上传文件的ID和状态
      statusCheckInterval: null,
      queueCheckInterval: null,
      chunkSize: 5 * 1024 * 1024, // 分块大小，5MB
      largeFileSizeThreshold: 10 * 1024 * 1024 // 大文件阈值，10MB
    }
  },
  methods: {
    handleFileChange(event) {
      const files = event.target.files;
      if (!files.length) return;

      // 转换FileList为数组并添加状态信息
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        // 检查文件类型
        if (!this.validateFileType(file)) {
          this.showMessage(`不支持的文件类型: ${file.name}`, 'error');
          continue;
        }
        
        // 检查文件大小
        if (file.size > 90 * 1024 * 1024) {
          this.showMessage(`文件过大: ${file.name} (最大支持90MB)`, 'error');
          continue;
        }
        
        this.selectedFiles.push({
          file: file,
          name: file.name,
          size: file.size,
          status: 'waiting',
          progress: 0,
          isLargeFile: file.size > this.largeFileSizeThreshold
        });
      }

      // 重置文件输入，允许选择相同文件
      this.$refs.fileInput.value = '';
    },

    validateFileType(file) {
      const validTypes = ['.pdf', '.jpg', '.jpeg', '.png', '.docx'];
      const fileExt = '.' + file.name.split('.').pop().toLowerCase();
      return validTypes.includes(fileExt);
    },

    formatFileSize(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    uploadFiles() {
      if (this.selectedFiles.length === 0) return;
      
      this.uploading = true;
      this.completedUploads = 0;
      this.uploadedFiles = [];
      
      // 确保状态正确初始化
      this.showMessage('开始上传文件...', 'info');
      
      // 将所有文件标记为等待中
      this.selectedFiles.forEach(fileObj => {
        fileObj.status = 'uploading';
        fileObj.progress = 0;
      });

      // 处理每个文件
      this.selectedFiles.forEach(fileObj => {
        if (fileObj.isLargeFile) {
          // 使用分块上传
          this.uploadLargeFile(fileObj);
        } else {
          // 使用普通上传
          this.uploadFile(fileObj);
        }
      });

      // 开始定期检查打印队列状态
      this.startQueueCheck();
    },

    uploadFile(fileObj) {
      const formData = new FormData();
      formData.append('file', fileObj.file);

      // 创建XMLHttpRequest对象来跟踪上传进度
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          fileObj.progress = Math.round((event.loaded / event.total) * 100);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          // 解析响应
          try {
            const response = JSON.parse(xhr.responseText);
            fileObj.status = 'queued';
            fileObj.progress = 100;
            fileObj.file_id = response.file_id;
            
            // 添加到已上传文件列表以便跟踪状态
            this.uploadedFiles.push({
              file_id: response.file_id,
              fileObj: fileObj
            });
            
            this.completedUploads++;
            
            // 检查是否所有文件都已上传完成
            if (this.completedUploads === this.selectedFiles.length) {
              this.uploading = false;
              this.showMessage('所有文件已成功上传并加入打印队列', 'success');
              // 开始跟踪打印状态
              this.startStatusCheck();
            }
          } catch (e) {
            console.error('解析响应失败:', e);
            fileObj.status = 'error';
            this.showMessage(`上传失败: ${fileObj.name} - 无法解析响应`, 'error');
          }
        } else {
          // 尝试解析错误响应
          let errorMsg = '上传失败';
          try {
            const errorResponse = JSON.parse(xhr.responseText);
            errorMsg = errorResponse.error || errorMsg;
          } catch (e) {
            // 忽略解析错误
          }
          fileObj.status = 'error';
          this.uploading = false;
          this.showMessage(`${errorMsg}: ${fileObj.name}`, 'error');
        }
      });

      xhr.addEventListener('error', () => {
        fileObj.status = 'error';
        this.uploading = false;
        this.showMessage(`上传失败: ${fileObj.name} - 网络错误`, 'error');
      });

      xhr.open('POST', '/api/print');
      xhr.send(formData);
    },

    async uploadLargeFile(fileObj) {
      try {
        console.log(`开始分块上传大文件: ${fileObj.name} (${this.formatFileSize(fileObj.size)})`);
        
        // 计算分块数量
        const totalChunks = Math.ceil(fileObj.size / this.chunkSize);
        
        // 初始化分块上传
        const initResponse = await fetch('/api/chunk/init', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            filename: fileObj.name,
            totalChunks: totalChunks,
            fileSize: fileObj.size
          })
        });
        
        if (!initResponse.ok) {
          const errorData = await initResponse.json().catch(() => ({ error: '初始化分块上传失败' }));
          throw new Error(errorData.error || `初始化分块上传失败: ${initResponse.statusText}`);
        }
        
        const initData = await initResponse.json();
        const fileId = initData.file_id;
        
        console.log(`分块上传初始化成功，文件ID: ${fileId}, 总分块数: ${totalChunks}`);
        
        // 上传每个分块
        const file = fileObj.file;
        let uploadedChunks = 0;
        let retryCount = 0;
        const maxRetries = 3;
        
        for (let i = 0; i < totalChunks; i++) {
          let success = false;
          retryCount = 0;
          
          while (!success && retryCount < maxRetries) {
            try {
              const start = i * this.chunkSize;
              const end = Math.min(start + this.chunkSize, fileObj.size);
              const chunk = file.slice(start, end);
              
              const formData = new FormData();
              formData.append('file', chunk, `${fileId}_chunk_${i}`);
              formData.append('chunkIndex', i);
              formData.append('fileId', fileId);
              
              const chunkResponse = await fetch('/api/chunk/upload', {
                method: 'POST',
                body: formData
              });
              
              if (!chunkResponse.ok) {
                const errorData = await chunkResponse.json().catch(() => ({ error: '上传分块失败' }));
                throw new Error(errorData.error || `上传分块 ${i} 失败: ${chunkResponse.statusText}`);
              }
              
              success = true;
            } catch (error) {
              retryCount++;
              console.warn(`分块 ${i} 上传失败，尝试重试 (${retryCount}/${maxRetries}): ${error.message}`);
              
              if (retryCount >= maxRetries) {
                throw new Error(`分块 ${i} 上传失败，超过最大重试次数`);
              }
              
              // 等待一段时间再重试
              await new Promise(resolve => setTimeout(resolve, 1000));
            }
          }
          
          // 更新进度
          uploadedChunks++;
          fileObj.progress = Math.round((uploadedChunks / totalChunks) * 100);
          
          console.log(`分块 ${i}/${totalChunks} 上传成功，当前进度: ${fileObj.progress}%`);
        }
        
        // 所有分块已上传，触发合并
        console.log(`所有分块已上传，请求合并文件...`);
        
        const completeResponse = await fetch('/api/chunk/complete', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            fileId: fileId
          })
        });
        
        if (!completeResponse.ok) {
          const errorData = await completeResponse.json().catch(() => ({ error: '合并文件失败' }));
          throw new Error(errorData.error || `合并文件失败: ${completeResponse.statusText}`);
        }
        
        const completeData = await completeResponse.json();
        
        // 更新文件状态
        fileObj.status = 'queued';
        fileObj.progress = 100;
        fileObj.file_id = fileId;
        
        // 添加到已上传文件列表以便跟踪状态
        this.uploadedFiles.push({
          file_id: fileId,
          fileObj: fileObj
        });
        
        this.completedUploads++;
        
        // 检查是否所有文件都已上传完成
        if (this.completedUploads === this.selectedFiles.length) {
          this.uploading = false;
          this.showMessage('所有文件已成功上传并加入打印队列', 'success');
          // 开始跟踪打印状态
          this.startStatusCheck();
        }
        
        console.log(`文件 ${fileObj.name} 分块上传完成并成功加入打印队列`);
      } catch (error) {
        console.error(`分块上传错误:`, error);
        fileObj.status = 'error';
        this.showMessage(`上传失败: ${fileObj.name} - ${error.message}`, 'error');
        
        // 增加完成计数，避免卡在上传状态
        this.completedUploads++;
        if (this.completedUploads === this.selectedFiles.length) {
          this.uploading = false;
        }
      }
    },

    clearFiles() {
      if (!this.uploading) {
        // 停止所有状态检查
        this.stopStatusCheck();
        this.stopQueueCheck();
        
        this.selectedFiles = [];
        this.uploadedFiles = [];
        this.message = '';
      }
    },

    showMessage(text, type = 'info') {
      this.message = text;
      this.messageType = type;
      
      // 3秒后清除消息
      setTimeout(() => {
        if (this.message === text) {
          this.message = '';
        }
      }, 3000);
    },

    getStatusText(status) {
      const statusMap = {
        'waiting': '等待上传',
        'uploading': '上传中',
        'queued': '等待打印',
        'printing': '正在打印',
        'completed': '打印完成',
        'error': '处理失败'
      };
      return statusMap[status] || status;
    },

    startStatusCheck() {
      // 停止之前的定时器
      this.stopStatusCheck();
      
      console.log('开始状态检查...');
      // 每3秒检查一次文件状态
      this.statusCheckInterval = setInterval(() => {
        this.checkPrintStatus();
      }, 3000);
    },

    stopStatusCheck() {
      if (this.statusCheckInterval) {
        clearInterval(this.statusCheckInterval);
        this.statusCheckInterval = null;
      }
    },

    checkPrintStatus() {
      // 检查每个已上传文件的状态
      if (this.uploadedFiles.length === 0) {
        console.log('没有文件需要检查状态');
        return;
      }
      
      console.log(`开始检查${this.uploadedFiles.length}个文件的状态...`);
      
      this.uploadedFiles.forEach(item => {
        if (!item || !item.fileObj || !item.file_id) {
          console.warn('状态检查: 无效的文件信息');
          return;
        }
        
        // 只检查未完成的文件
        if (item.fileObj.status !== 'completed' && item.fileObj.status !== 'error') {
          console.log(`检查文件状态: ${item.file_id}, 当前状态: ${item.fileObj.status}`);
          
          fetch(`/api/status/${item.file_id}`)
            .then(response => {
              if (!response.ok) {
                throw new Error(`服务器返回错误状态码: ${response.status}`);
              }
              return response.json();
            })
            .then(data => {
              console.log(`文件 ${item.file_id} 状态: ${data.status}`);
              if (data.status && data.status !== 'unknown') {
                // 更新文件状态
                item.fileObj.status = data.status;
                
                // 如果状态是error，显示错误消息
                if (data.status === 'error') {
                  this.showMessage(`文件 ${item.fileObj.name} 处理失败`, 'error');
                } else if (data.status === 'completed') {
                  this.showMessage(`文件 ${item.fileObj.name} 打印完成`, 'success');
                }
                
                // 如果所有文件都已完成，停止状态检查
                if (this.allFilesCompleted()) {
                  this.stopStatusCheck();
                  if (this.uploadedFiles.every(item => item.fileObj.status === 'completed')) {
                    this.showMessage('所有文件打印完成', 'success');
                  } else {
                    this.showMessage('文件处理已完成，部分文件处理失败', 'info');
                  }
                }
              }
            })
            .catch(error => {
              console.error('检查状态失败:', error);
              // 不要在网络错误时修改文件状态，只记录错误
            });
        }
      });
    },

    allFilesCompleted() {
      // 检查是否所有上传的文件都已完成处理
      return this.uploadedFiles.length > 0 && this.uploadedFiles.every(item => 
        item.fileObj.status === 'completed' || item.fileObj.status === 'error'
      );
    },

    startQueueCheck() {
      // 停止之前的定时器
      this.stopQueueCheck();
      
      // 每5秒检查一次打印队列状态
      this.queueCheckInterval = setInterval(() => {
        this.checkQueueStatus();
      }, 5000);
    },

    stopQueueCheck() {
      if (this.queueCheckInterval) {
        clearInterval(this.queueCheckInterval);
        this.queueCheckInterval = null;
      }
    },

    checkQueueStatus() {
      fetch('/api/queue')
        .then(response => {
          if (!response.ok) {
            throw new Error(`服务器返回错误状态码: ${response.status}`);
          }
          return response.json();
        })
        .then(data => {
          console.log('队列状态:', data);
          this.queueInfo = data;
        })
        .catch(error => {
          console.error('检查队列状态失败:', error);
        });
    }
  },
  created() {
    // 初始化时检查一次打印队列
    this.checkQueueStatus();
  },
  beforeUnmount() {
    // 组件销毁前清除所有定时器
    this.stopStatusCheck();
    this.stopQueueCheck();
  }
}
</script>

<style>
.app-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

h1 {
  color: #409EFF;
  text-align: center;
  margin-bottom: 30px;
}

.upload-container {
  text-align: center;
  margin-bottom: 20px;
}

.file-input {
  width: 0.1px;
  height: 0.1px;
  opacity: 0;
  overflow: hidden;
  position: absolute;
  z-index: -1;
}

.file-label {
  display: inline-block;
  background-color: #409EFF;
  color: white;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.file-label:hover {
  background-color: #66b1ff;
}

.file-types {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.file-list {
  margin-top: 20px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 15px;
}

.file-list h3 {
  margin-top: 0;
  color: #606266;
  font-size: 16px;
}

.file-list ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.file-item {
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.file-item:last-child {
  border-bottom: none;
}

.file-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.file-name {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70%;
}

.file-size {
  color: #909399;
  font-size: 12px;
  margin-left: 5px;
}

.file-status {
  font-size: 14px;
  font-weight: bold;
}

.file-status.waiting {
  color: #909399;
}

.file-status.uploading {
  color: #e6a23c;
}

.file-status.queued {
  color: #409EFF;
}

.file-status.printing {
  color: #e6a23c;
}

.file-status.completed {
  color: #67c23a;
}

.file-status.error {
  color: #f56c6c;
}

.progress-bar-container {
  height: 6px;
  background-color: #e6e6e6;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background-color: #409EFF;
  transition: width 0.3s ease;
}

.queue-info {
  margin-top: 15px;
  padding: 10px;
  background-color: #f4f4f5;
  border-radius: 4px;
}

.queue-status {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #606266;
}

.printing-indicator {
  padding: 2px 10px;
  background-color: #e6a23c;
  color: white;
  border-radius: 10px;
  font-size: 12px;
}

.actions {
  margin-top: 20px;
  text-align: center;
}

.upload-button, .clear-button {
  padding: 10px 20px;
  border-radius: 4px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  margin: 0 10px;
  transition: background-color 0.3s;
}

.upload-button {
  background-color: #409EFF;
  color: white;
}

.upload-button:hover:not(:disabled) {
  background-color: #66b1ff;
}

.clear-button {
  background-color: #f56c6c;
  color: white;
}

.clear-button:hover:not(:disabled) {
  background-color: #f78989;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.message {
  margin-top: 20px;
  padding: 10px;
  border-radius: 4px;
  text-align: center;
}

.message.info {
  background-color: #e9f5fe;
  color: #409EFF;
}

.message.success {
  background-color: #f0f9eb;
  color: #67c23a;
}

.message.error {
  background-color: #fef0f0;
  color: #f56c6c;
}
</style> 