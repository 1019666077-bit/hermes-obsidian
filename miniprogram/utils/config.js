/**
 * 后端地址配置 + 客户端 ID
 * 开发者工具本地调试可用 http://127.0.0.1:8787
 * 真机调试 / 正式版必须配置 HTTPS 合法域名（微信公众平台 → 开发 → 开发管理 → 服务器域名）
 */

const STORAGE_KEY = 'hermes_client_id'

function _randomId() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let s = 'mp_'
  for (let i = 0; i < 16; i++) {
    s += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return s
}

function getClientId() {
  try {
    let id = wx.getStorageSync(STORAGE_KEY)
    if (!id || typeof id !== 'string') {
      id = _randomId()
      wx.setStorageSync(STORAGE_KEY, id)
    }
    return id
  } catch (e) {
    return 'anonymous'
  }
}

function clientHeaders() {
  return {
    'X-Client-Id': getClientId()
  }
}

module.exports = {
  baseUrl: 'http://127.0.0.1:8787',
  getClientId,
  clientHeaders
}
