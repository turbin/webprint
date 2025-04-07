<template>
  <div class="uploader-container">
    <el-upload
      class="upload-area"
      drag
      multiple
      :action="uploadUrl"
      :on-success="handleSuccess"
      :on-error="handleError"
      :before-upload="beforeUpload"
      :on-progress="handleProgress"
      :file-list="fileList"
      :on-change="handleChange"
      accept=".pdf,.jpg,.jpeg,.png,.docx"
    >
      <el-icon><Upload /></el-icon>
      <div class="el-upload__text">
        将文件拖到此处，或<em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 PDF、图片和 DOCX 文件
        </div>
      </template>
    </el-upload>

    <div v-if="fileList.length > 0" class="file-list">
      <h3>待打印文件列表</h3>
      <el-table :data="fileList" style="width: 100%">
        <el-table-column prop="name" label="文件名" />
        <el-table-column prop="status" label="状态">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度">
          <template #default="scope">
            <el-progress 
              :percentage="scope.row.progress || 0"
              :status="scope.row.status === 'error' ? 'exception' : ''"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export default {
  name: 'FileUploader',
  setup() {
    const uploadUrl = '/api/print'
    const fileList = ref([])

    const beforeUpload = (file) => {
      const isValidType = /\.(pdf|jpg|jpeg|png|docx)$/i.test(file.name)
      if (!isValidType) {
        ElMessage.error('只支持 PDF、图片和 DOCX 文件！')
        return false
      }
      return true
    }

    const handleChange = (file) => {
      const existingIndex = fileList.value.findIndex(f => f.uid === file.uid)
      if (existingIndex === -1) {
        fileList.value.push({
          ...file,
          status: 'waiting',
          progress: 0
        })
      }
    }

    const handleSuccess = (response, file) => {
      const index = fileList.value.findIndex(f => f.uid === file.uid)
      if (index !== -1) {
        fileList.value[index].status = 'success'
        fileList.value[index].progress = 100
      }
      ElMessage.success(`${file.name} 打印成功`)
    }

    const handleError = (error, file) => {
      const index = fileList.value.findIndex(f => f.uid === file.uid)
      if (index !== -1) {
        fileList.value[index].status = 'error'
      }
      ElMessage.error(`${file.name} 打印失败`)
    }

    const handleProgress = (event, file) => {
      const index = fileList.value.findIndex(f => f.uid === file.uid)
      if (index !== -1) {
        fileList.value[index].progress = Math.round(event.percent)
        fileList.value[index].status = 'uploading'
      }
    }

    const getStatusType = (status) => {
      const types = {
        'success': 'success',
        'error': 'danger',
        'uploading': 'warning',
        'waiting': 'info'
      }
      return types[status] || 'info'
    }

    const getStatusText = (status) => {
      const texts = {
        'success': '打印成功',
        'error': '打印失败',
        'uploading': '正在打印',
        'waiting': '等待打印'
      }
      return texts[status] || status
    }

    return {
      uploadUrl,
      fileList,
      beforeUpload,
      handleChange,
      handleSuccess,
      handleError,
      handleProgress,
      getStatusType,
      getStatusText
    }
  }
}
</script>

<style scoped>
.uploader-container {
  margin-top: 20px;
}

.upload-area {
  width: 100%;
}

.file-list {
  margin-top: 30px;
}

.el-upload__tip {
  color: #909399;
  font-size: 12px;
  margin-top: 7px;
}

h3 {
  margin-bottom: 20px;
  color: #606266;
}
</style> 