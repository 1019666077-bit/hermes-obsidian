const { ensureLogin } = require('./utils/config.js')

App({
  onLaunch() {
    console.log('Hermes×Obsidian mini-program launched (Phase 5)')
    ensureLogin().then((r) => {
      if (r && r.ok) {
        console.log('login ok', r.mode, r.openid)
      } else {
        console.warn('login skipped/failed', r && r.error)
      }
    })
  },
  globalData: {
    productName: '笔记整理成 Obsidian'
  }
})
