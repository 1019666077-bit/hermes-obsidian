const { baseUrl } = require('../../utils/config.js')

Page({
  data: {
    filePath: '',
    fileName: '',
    busy: false,
    status: '',
    jobId: '',
    downloadPath: ''
  },

  chooseFile() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['zip', 'md', 'txt', 'csv', 'markdown'],
      success: (res) => {
        const f = res.tempFiles[0]
        this.setData({
          filePath: f.path,
          fileName: f.name,
          status: '',
          jobId: '',
          downloadPath: ''
        })
      },
      fail: (err) => {
        wx.showToast({ title: '未选择文件', icon: 'none' })
        console.warn('chooseMessageFile', err)
      }
    })
  },

  startOrganize() {
    const { filePath, fileName } = this.data
    if (!filePath) {
      wx.showToast({ title: '请先选择文件', icon: 'none' })
      return
    }
    this.setData({ busy: true, status: '上传并整理中…', downloadPath: '' })

    wx.uploadFile({
      url: `${baseUrl}/api/organize`,
      filePath,
      name: 'files',
      success: (res) => {
        let body
        try {
          body = JSON.parse(res.data)
        } catch (e) {
          this.setData({ busy: false, status: '响应解析失败' })
          return
        }
        if (res.statusCode >= 400 || !body.job_id) {
          this.setData({
            busy: false,
            status: `失败：${body.detail || res.data}`
          })
          return
        }
        this.setData({
          jobId: body.job_id,
          status: `整理完成（引擎：${body.engine || 'unknown'}），正在下载…`
        })
        this.downloadVault(body.job_id)
      },
      fail: (err) => {
        this.setData({
          busy: false,
          status: `请求失败：请确认本机 API 已启动（${baseUrl}）。真机需 HTTPS 合法域名。`
        })
        console.error(err)
      }
    })
  },

  downloadVault(jobId) {
    const url = `${baseUrl}/api/download/${jobId}`
    wx.downloadFile({
      url,
      success: (res) => {
        if (res.statusCode !== 200) {
          this.setData({ busy: false, status: `下载失败 HTTP ${res.statusCode}` })
          return
        }
        this.setData({
          busy: false,
          downloadPath: res.tempFilePath,
          status: '整理完成，可打开或保存 vault zip'
        })
      },
      fail: (err) => {
        this.setData({ busy: false, status: '下载失败' })
        console.error(err)
      }
    })
  },

  openVault() {
    const path = this.data.downloadPath
    if (!path) return
    wx.openDocument({
      filePath: path,
      fileType: 'zip',
      showMenu: true,
      fail: () => {
        wx.showToast({ title: '无法直接预览 zip，请保存后解压', icon: 'none' })
      }
    })
  },

  saveVault() {
    const path = this.data.downloadPath
    if (!path) return
    // 基础库支持 saveFile；部分端可用 shareFileMessage
    wx.saveFile({
      tempFilePath: path,
      success: (res) => {
        wx.showToast({ title: '已保存', icon: 'success' })
        this.setData({ status: `已保存：${res.savedFilePath}` })
      },
      fail: () => {
        if (wx.shareFileMessage) {
          wx.shareFileMessage({
            filePath: path,
            fileName: `obsidian-vault-${(this.data.jobId || '').slice(0, 8)}.zip`,
            fail: () => wx.showToast({ title: '保存失败', icon: 'none' })
          })
        } else {
          wx.showToast({ title: '当前环境不支持保存', icon: 'none' })
        }
      }
    })
  }
})
