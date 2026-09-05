/**
 * 后端地址 + 客户端 ID + 微信登录 session
 *
 * 本地 DEV 默认 http://127.0.0.1:8787（开发者工具请关闭域名校验）。
 * 真机 / 正式版改为 HTTPS，或在控制台：
 *   wx.setStorageSync('hermes_api_base', 'https://你的域名')
 *
 * 登录：wx.login → POST /api/login → 保存 session_token
 * - 未配置 WECHAT_* 时后端为 DEV 模式（任意 code 可换假 openid）
 * - 请求优先带 Authorization: Bearer；保留 X-Client-Id 作备份
 */

const STORAGE_CLIENT = 'hermes_client_id'
const STORAGE_TOKEN = 'hermes_session_token'
const STORAGE_OPENID = 'hermes_openid'
const STORAGE_API_BASE = 'hermes_api_base'

const DEFAULT_BASE_URL = 'http://127.0.0.1:8787'

function _randomId() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  let s = 'mp_'
  for (let i = 0; i < 16; i++) {
    s += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return s
}

function getBaseUrl() {
  try {
    const stored = wx.getStorageSync(STORAGE_API_BASE)
    if (stored && typeof stored === 'string' && stored.trim()) {
      return stored.trim().replace(/\/$/, '')
    }
  } catch (e) {
    /* ignore */
  }
  return DEFAULT_BASE_URL
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

/** FastAPI detail 可能是字符串或 { message, upgrade_hint } */
function extractDetail(body) {
  if (!body) return ''
  const d = body.detail
  if (typeof d === 'string' && d) return d
  if (d && typeof d === 'object') {
    return d.message || d.upgrade_hint || ''
  }
  if (typeof body.message === 'string') return body.message
  return ''
}

function showUpgradeModal(extraHint) {
  const content = extraHint
    || '每天可免费整理 5 次（北京时间 0 点重置）。用完后可第二天再试，或联系管理员手工开通会员。当前为演示，暂无在线支付。'
  wx.showModal({
    title: '开通会员',
    content,
    showCancel: false,
    confirmText: '知道了'
  })
}

function _postLogin(code) {
  return new Promise((resolve) => {
    wx.request({
      url: `${getBaseUrl()}/api/login`,
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
          resolve({
            ok: false,
            error: extractDetail(res.data) || '登录失败',
            statusCode: res.statusCode
          })
        }
      },
      fail: (err) => {
        console.warn('login request fail', err)
        resolve({ ok: false, error: 'network' })
      }
    })
  })
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
        _postLogin(code).then(resolve)
      },
      fail: (err) => {
        // 开发者工具外偶发；仍可用假 code 试后端 DEV 模式
        console.warn('wx.login fail, trying dev code', err)
        _postLogin('dev-fallback-' + getClientId()).then((r) => {
          if (r.ok) {
            resolve(r)
          } else {
            resolve({ ok: false, error: r.error || 'wx.login failed' })
          }
        })
      }
    })
  })
}

module.exports = {
  DEFAULT_BASE_URL,
  getBaseUrl,
  get baseUrl() {
    return getBaseUrl()
  },
  getClientId,
  getSessionToken,
  getOpenId,
  clientHeaders,
  ensureLogin,
  saveSession,
  clearSession,
  extractDetail,
  showUpgradeModal
}
