const {
  getBaseUrl,
  clientHeaders,
  ensureLogin,
  showUpgradeModal
} = require('../../utils/config.js')

Page({
  data: {
    apiBase: getBaseUrl(),
    loginLabel: '',
    planLabel: '免费试用',
    quotaRemainLabel: '每天 5 次',
    quotaHint: '每天可免费整理 5 次（北京时间 0 点重置）。用完后第二天恢复，或开通会员。',
    quotaPercent: 100,
    exhausted: false,
    upgradeHint: ''
  },

  onShow() {
    this.setData({ apiBase: getBaseUrl() })
    ensureLogin().then((r) => {
      let loginLabel = '未登录（按设备计次）'
      if (r && r.ok) {
        loginLabel = r.mode === 'live' ? '微信已登录' : '开发登录（本地）'
      } else if (r && r.error === 'network') {
        loginLabel = 'API 未连接'
      }
      this.setData({ loginLabel })
      this.loadQuota()
    })
  },

  loadQuota() {
    wx.request({
      url: `${getBaseUrl()}/api/quota`,
      method: 'GET',
      header: clientHeaders(),
      success: (res) => {
        if (res.statusCode !== 200 || !res.data) return
        const d = res.data
        const limit = Number(d.limit) || 5
        const remaining = Number(d.remaining)
        const exhausted = !!d.exhausted || remaining <= 0
        const percent = limit > 0 ? Math.max(0, Math.round((remaining / limit) * 100)) : 0
        this.setData({
          planLabel: d.plan_label || '免费试用',
          quotaRemainLabel: exhausted ? '今日已用完' : `今日剩余 ${remaining}/${limit} 次`,
          quotaHint: d.hint || this.data.quotaHint,
          quotaPercent: percent,
          exhausted,
          upgradeHint: d.upgrade_hint || ''
        })
      }
    })
  },

  onUpgrade() {
    showUpgradeModal(this.data.upgradeHint)
  },

  goOrganize() {
    wx.navigateTo({ url: '/pages/organize/organize' })
  }
})
