/**
 * 后端地址配置 + 客户端 ID + 微信登录 session
 * 开发者工具本地调试可用 http://127.0.0.1:8787
 * 真机调试 / 正式版必须配置 HTTPS 合法域名（微信公众平台 → 开发 → 开发管理 → 服务器域名）
 *
 * 登录：wx.login → POST /api/login → 保存 session_token
 * - 未配置 WECHAT_* 时后端为 DEV 模式（任意 code 可换假 openid）
 * - 请求优先带 Authorization: Bearer；保留 X-Client-Id 作备份
 */

const STORAGE_CLIENT = 'hermes_client_id'
const STORAGE_TOKEN = 'hermes_session_token'
const STORAGE_OPENID = 'hermes_openid'

const baseUrl = 'http://127.0.0.1:8787'

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
    let id = wx.getStorageSync(STORAGE_CLIENT)
    if (!id || typeof id !== 'string') {
      id = _randomId()
      wx.setStorageSync(STORAGE_CLIENT, id)
    }
    return id
  } catch (e) {
    return 'anonymous'
  }
}

function getSessionToken() {
  try {
    const t = wx.getStorageSync(STORAGE_TOKEN)
    return t && typeof t === 'string' ? t : ''
  } catch (e) {
    return ''
  }
}

function getOpenId() {
  try {
    const o = wx.getStorageSync(STORAGE_OPENID)
    return o && typeof o === 'string' ? o : ''
  } catch (e) {
    return ''
  }
}

function saveSession(token, openid) {
  try {
    if (token) wx.setStorageSync(STORAGE_TOKEN, token)
    if (openid) wx.setStorageSync(STORAGE_OPENID, openid)
  } catch (e) {
    console.warn('saveSession failed', e)
  }
}

function clearSession() {
  try {
    wx.removeStorageSync(STORAGE_TOKEN)
    wx.removeStorageSync(STORAGE_OPENID)
  } catch (e) {
    /* ignore */
  }
}

/** Headers for all API calls: Bearer when logged in + X-Client-Id backup */
function clientHeaders() {
  const h = {
    'X-Client-Id': getClientId()
  }
  const token = getSessionToken()
  if (token) {
    h.Authorization = `Bearer ${token}`
  }
  return h
}

/**
 * wx.login → POST /api/login → persist token
 * Resolves with { ok, mode, openid, token } or { ok:false, error }
 */
function ensureLogin() {
  return new Promise((resolve) => {
    wx.login({
      success: (loginRes) => {
        const code = (loginRes && loginRes.code) || 'dev-local-code'
        wx.request({
          url: `${baseUrl}/api/login`,
          method: 'POST',
          header: {
            'Content-Type': 'application/json',
            'X-Client-Id': getClientId()
          },
          data: { code },
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.session_token) {
              const token = res.data.session_token || res.data.token
              const openid = res.data.openid || ''
              saveSession(token, openid)
              resolve({
                ok: true,
                mode: res.data.mode || 'unknown',
                openid,
                token,
                hint: res.data.hint
              })
            } else {
              console.warn('login failed', res.statusCode, res.data)
              resolve({ ok: false, error: (res.data && res.data.detail) || 'login failed' })
            }
          },
          fail: (err) => {
            console.warn('login request fail', err)
            resolve({ ok: false, error: 'network' })
          }
        })
      },
      fail: (err) => {
        // 开发者工具外偶发；仍可用假 code 试后端 DEV 模式
        console.warn('wx.login fail, trying dev code', err)
        wx.request({
          url: `${baseUrl}/api/login`,
          method: 'POST',
          header: {
            'Content-Type': 'application/json',
            'X-Client-Id': getClientId()
          },
          data: { code: 'dev-fallback-' + getClientId() },
          success: (res) => {
            if (res.statusCode < 300 && res.data && res.data.session_token) {
              saveSession(res.data.session_token, res.data.openid || '')
              resolve({ ok: true, mode: res.data.mode || 'dev', openid: res.data.openid, token: res.data.session_token })
            } else {
              resolve({ ok: false, error: 'wx.login failed' })
            }
          },
          fail: () => resolve({ ok: false, error: 'wx.login failed' })
        })
      }
    })
  })
}

module.exports = {
  baseUrl,
  getClientId,
  getSessionToken,
  getOpenId,
  clientHeaders,
  ensureLogin,
  saveSession,
  clearSession
}
