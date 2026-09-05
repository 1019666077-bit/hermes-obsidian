const {
  getBaseUrl,
  clientHeaders,
  getClientId,
  ensureLogin,
  extractDetail,
  showUpgradeModal
} = require('../../utils/config.js')

function hideLoadingSafe() {
  try {
    wx.hideLoading()
  } catch (e) {
    /* ignore */
  }
}

Page({
  data: {
    filePath: '',
    fileName: '',
    busy: false,
    status: '',
    statusKind: '',
    jobId: '',
    downloadPath: '',
    engine: '',
    planLabel: '免费试用',
    quotaRemainLabel: '正在获取剩余次数…',
    quotaHint: '每天可免费整理 5 次（北京时间 0 点重置）。',
    quotaPercent: 100,
    remaining: null,
    exhausted: false,
    upgradeHint: '',
    loginLabel: ''
  },

  onShow() {
    ensureLogin().then((r) => {
      let loginLabel = '未登录（按设备计次）'
      if (r && r.ok) {
        loginLabel = r.mode === 'live' ? '微信已登录' : '开发登录（本地）'
      } else if (r && r.error === 'network') {
        loginLabel = 'API 未连接'
        wx.showToast({ title: '连不上本机 API', icon: 'none' })
      } else if (r && !r.ok) {
        loginLabel = '登录失败（按设备计次）'
        wx.showToast({ title: r.error || '登录失败', icon: 'none' })
      }
      this.setData({ loginLabel })
      this.refreshQuota()
    })
  },

  applyQuota(d) {
    if (!d) return
    const limit = Number(d.limit) || 5
    const remaining = Number(d.remaining)
    const exhausted = !!d.exhausted || remaining <= 0
    const percent = limit > 0 ? Math.max(0, Math.round((remaining / limit) * 100)) : 0
    const who = d.openid
      ? `openid ${String(d.openid).slice(0, 10)}…`
      : `设备 ${getClientId().slice(0, 8)}…`
    this.setData({
      remaining,
      planLabel: d.plan_label || '免费试用',
      quotaRemainLabel: exhausted ? '今日已用完' : `今日剩余 ${remaining}/${limit} 次`,
      quotaHint: d.hint || `按 ${who} 计次`,
      quotaPercent: percent,
      exhausted,
      upgradeHint: d.upgrade_hint || ''
    })
  },

  refreshQuota() {
    wx.request({
      url: `${getBaseUrl()}/api/quota`,
      method: 'GET',
      header: clientHeaders(),
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          this.applyQuota(res.data)
        }
      },
      fail: () => {
        this.setData({
          quotaRemainLabel: '配额暂不可用',
          quotaHint: '请确认本机 API 已启动，或检查 hermes_api_base。'
        })
      }
    })
  },

  onUpgrade() {
    showUpgradeModal(this.data.upgradeHint)
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
          statusKind: '',
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
    const { filePath, fileName, exhausted } = this.data
    if (!filePath) {
      wx.showToast({ title: '请先选择文件', icon: 'none' })
      return
    }
    if (exhausted) {
      wx.showToast({ title: '今日次数已用完', icon: 'none' })
      this.onUpgrade()
      return
    }

    this.setData({
      busy: true,
      status: '正在上传并整理…',
      statusKind: '',
      downloadPath: '',
      engine: ''
    })
    wx.showLoading({ title: '整理中…', mask: true })

    const failUi = (status, toast) => {
      hideLoadingSafe()
      this.setData({ busy: false, status, statusKind: 'is-error' })
      if (toast) wx.showToast({ title: toast, icon: 'none' })
    }

    const runUpload = () => {
      wx.uploadFile({
        url: `${getBaseUrl()}/api/organize`,
        filePath,
        name: 'files',
        header: clientHeaders(),
        formData: { filename: fileName || '' },
        success: (res) => {
          let body
          try {
            body = JSON.parse(res.data)
          } catch (e) {
            failUi('响应解析失败', '服务器返回异常')
            return
          }

          if (res.statusCode === 429) {
            const msg = extractDetail(body) || '今日免费次数已用完'
            const hint = body.detail && body.detail.upgrade_hint
            hideLoadingSafe()
            this.setData({
              busy: false,
              status: msg,
              statusKind: 'is-error',
              exhausted: true,
              quotaRemainLabel: '今日已用完',
              quotaPercent: 0,
              upgradeHint: hint || this.data.upgradeHint
            })
            wx.showToast({ title: '今日次数已用完', icon: 'none' })
            this.refreshQuota()
            return
          }

          if (res.statusCode >= 400 || !body.job_id) {
            failUi(`失败：${extractDetail(body) || res.data}`, '整理失败')
            this.refreshQuota()
            return
          }

          const engine = body.engine || 'unknown'
          if (body.quota) this.applyQuota(body.quota)
          this.setData({
            jobId: body.job_id,
            engine,
            status: `整理完成（引擎：${engine}），正在下载…`,
            statusKind: ''
          })
          this.downloadVault(body.job_id)
        },
        fail: (err) => {
          console.error(err)
          failUi(
            `请求失败：请确认 API 已启动（${getBaseUrl()}）。真机需 HTTPS 合法域名。`,
            '请求失败'
          )
        }
      })
    }

    ensureLogin().then(runUpload)
  },

  downloadVault(jobId) {
    const url = `${getBaseUrl()}/api/download/${jobId}`
    wx.downloadFile({
      url,
      header: clientHeaders(),
      success: (res) => {
        hideLoadingSafe()
        if (res.statusCode !== 200) {
          this.setData({
            busy: false,
            status: `下载失败 HTTP ${res.statusCode}`,
            statusKind: 'is-error'
          })
          wx.showToast({ title: '下载失败', icon: 'none' })
          return
        }
        const eng = this.data.engine ? `（引擎：${this.data.engine}）` : ''
        this.setData({
          busy: false,
          downloadPath: res.tempFilePath,
          status: `整理完成${eng}，可打开或保存 vault zip`,
          statusKind: 'is-ok'
        })
        wx.showToast({ title: '整理完成', icon: 'success' })
        this.refreshQuota()
      },
      fail: (err) => {
        console.error(err)
        hideLoadingSafe()
        this.setData({ busy: false, status: '下载失败', statusKind: 'is-error' })
        wx.showToast({ title: '下载失败', icon: 'none' })
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
        wx.showToast({ title: '无法预览 zip，请先保存', icon: 'none' })
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
        this.setData({ status: `已保存：${res.savedFilePath}`, statusKind: 'is-ok' })
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
