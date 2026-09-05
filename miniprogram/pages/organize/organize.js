const { baseUrl, clientHeaders, getClientId } = require('../../utils/config.js')

Page({
  data: {
    filePath: '',
    fileName: '',
    busy: false,
    status: '',
    jobId: '',
    downloadPath: '',
    engine: '',
    quotaText: '',
    remaining: null
  },

  onShow() {
    this.refreshQuota()
  },

  refreshQuota() {
    wx.request({
      url: `${baseUrl}/api/quota`,
      method: 'GET',
      header: clientHeaders(),
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          const d = res.data
          this.setData({
            remaining: d.remaining,
            quotaText: `今日剩余 ${d.remaining}/${d.limit} 次（客户端 ${getClientId().slice(0, 10)}…）`
          })
        }
      },
      fail: () => {
        // ignore offline
      }
    })
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
          downloadPath: '',
          engine: ''
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
    this.setData({ busy: true, status: '上传并整理中…', downloadPath: '', engine: '' })

    wx.uploadFile({
      url: `${baseUrl}/api/organize`,
      filePath,
      name: 'files',
      header: clientHeaders(),
      success: (res) => {
        let body
        try {
          body = JSON.parse(res.data)
        } catch (e) {
          this.setData({ busy: false, status: '响应解析失败' })
          return
        }

        if (res.statusCode === 429) {
          const msg = (body && body.detail) || '今日免费次数已用完'
          this.setData({ busy: false, status: msg })
          wx.showToast({ title: '配额已用尽', icon: 'none' })
          this.refreshQuota()
          return
        }

        if (res.statusCode >= 400 || !body.job_id) {
          this.setData({
            busy: false,
            status: `失败：${(body && body.detail) || res.data}`
          })
          this.refreshQuota()
          return
        }

        const engine = body.engine || 'unknown'
        let quotaHint = ''
        if (body.quota) {
          quotaHint = `，剩余 ${body.quota.remaining}/${body.quota.limit}`
          this.setData({
            remaining: body.quota.remaining,
            quotaText: `今日剩余 ${body.quota.remaining}/${body.quota.limit} 次`
          })
        }
        this.setData({
          jobId: body.job_id,
          engine,
          status: `整理完成（引擎：${engine}${quotaHint}），正在下载…`
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
      header: clientHeaders(),
      success: (res) => {
        if (res.statusCode !== 200) {
          this.setData({ busy: false, status: `下载失败 HTTP ${res.statusCode}` })
          return
        }
        const eng = this.data.engine ? `（引擎：${this.data.engine}）` : ''
        this.setData({
          busy: false,
          downloadPath: res.tempFilePath,
          status: `整理完成${eng}，可打开或保存 vault zip`
        })
        this.refreshQuota()
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
