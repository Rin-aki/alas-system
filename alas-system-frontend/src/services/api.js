/**
 * API服务 - 处理与后端的通信
 */

function isLocalLikeHostname(hostname) {
  return hostname === 'localhost'
    || hostname === '127.0.0.1'
    || /^10\.10\.10\.\d+$/.test(hostname)
}

function resolveBaseUrl(rawValue) {
  const value = (rawValue || '').trim()

  if (!value || typeof window === 'undefined') {
    return value.replace(/\/$/, '')
  }

  try {
    const configuredUrl = new URL(value)
    const currentUrl = new URL(window.location.href)

    if (isLocalLikeHostname(configuredUrl.hostname) && isLocalLikeHostname(currentUrl.hostname)) {
      configuredUrl.hostname = currentUrl.hostname
    }

    return configuredUrl.toString().replace(/\/$/, '')
  } catch {
    return value.replace(/\/$/, '')
  }
}

const API_BASE_URL = resolveBaseUrl(import.meta.env.VITE_API_BASE_URL)
const AUTH_RETRY_DELAY_MS = 150
const AUTH_RETRY_ATTEMPTS = 3

if (!API_BASE_URL) {
  console.warn('VITE_API_BASE_URL 未设置，API 请求将使用相对路径。')
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

export function resolveRuntimeUrl(rawValue, options = {}) {
  const value = (rawValue || '').trim()

  if (!value || typeof window === 'undefined') {
    return value
  }

  try {
    const configuredUrl = new URL(value)
    const currentUrl = new URL(window.location.href)

    if (isLocalLikeHostname(configuredUrl.hostname) && isLocalLikeHostname(currentUrl.hostname)) {
      configuredUrl.hostname = currentUrl.hostname
    }

    if (options.service && isLocalLikeHostname(configuredUrl.hostname)) {
      const normalizedPath = configuredUrl.pathname.replace(/\/+$/, '')
      configuredUrl.pathname = `${normalizedPath}/${options.service}/`
      configuredUrl.searchParams.delete('service')
    }

    return configuredUrl.toString()
  } catch {
    return value
  }
}

async function waitForAuthState(request, key) {
  for (let attempt = 0; attempt < AUTH_RETRY_ATTEMPTS; attempt += 1) {
    const response = await request()
    const isAuthenticated = response.ok && response.data?.[key] === true

    if (isAuthenticated) {
      return true
    }

    if (attempt < AUTH_RETRY_ATTEMPTS - 1) {
      await sleep(AUTH_RETRY_DELAY_MS)
    }
  }

  return false
}

/**
 * 发送请求到后端API
 * @param {string} endpoint - API端点
 * @param {Object} options - 请求选项
 * @returns {Promise} - 返回响应Promise
 */
export async function apiRequest(endpoint, options = {}) {
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  const url = `${API_BASE_URL}${path}`

  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }

  const requestOptions = {
    ...options,
    headers,
    credentials: options.credentials || 'same-origin'
  }

  try {
    const response = await fetch(url, requestOptions)
    const data = await response.json()

    return {
      status: response.status,
      data,
      ok: response.ok
    }
  } catch (error) {
    console.error('API请求错误:', error)
    throw error
  }
}

export const userService = {
  register: (userData) => {
    return apiRequest('/register', {
      method: 'POST',
      body: JSON.stringify(userData)
    })
  },

  login: (credentials) => {
    return apiRequest('/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      credentials: 'include'
    })
  },

  purchase: (purchaseData) => {
    return apiRequest('/purchase', {
      method: 'POST',
      body: JSON.stringify(purchaseData),
      credentials: 'include'
    })
  },

  getPurchaseStatus: () => {
    return apiRequest('/purchase/status', {
      method: 'GET',
      credentials: 'include'
    })
  },

  authcheck: () => {
    return apiRequest('/auth/check', {
      method: 'GET',
      credentials: 'include'
    })
  },

  isAuthenticated: async () => {
    const response = await userService.authcheck()
    return response.ok && response.data?.is_authenticated === true
  },

  waitForSession: () => waitForAuthState(() => userService.authcheck(), 'is_authenticated'),

  logout: () => {
    return apiRequest('/logout', {
      method: 'POST',
      credentials: 'include'
    })
  },

  getUserInfo: () => {
    return apiRequest('/user/info', {
      method: 'GET',
      credentials: 'include'
    })
  },

  reconnect: () => {
    return apiRequest('/reconnect', {
      method: 'POST',
      credentials: 'include'
    })
  },

  verifyEmail: (token) => {
    return apiRequest(`/verify-email?token=${encodeURIComponent(token)}`, {
      method: 'GET'
    })
  },

  resendVerification: (email) => {
    return apiRequest('/resend-verification', {
      method: 'POST',
      body: JSON.stringify({ email })
    })
  },

  getLatestAnnouncement: () => {
    return apiRequest('/announcement/latest', {
      method: 'GET',
      credentials: 'include'
    })
  },

  getSystemStatus: () => {
    return apiRequest('/system/status', {
      method: 'GET',
      credentials: 'include'
    })
  },

  createAnnouncement: (announcementData) => {
    return apiRequest('/admin/announcement', {
      method: 'POST',
      body: JSON.stringify(announcementData),
      credentials: 'include'
    })
  },

  updateMaintenance: (maintenanceData) => {
    return apiRequest('/admin/maintenance', {
      method: 'POST',
      body: JSON.stringify(maintenanceData),
      credentials: 'include'
    })
  }
}

export const adminService = {
  login: (credentials) => {
    return apiRequest('/admin/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      credentials: 'include'
    })
  },

  logout: () => {
    return apiRequest('/admin/logout', {
      method: 'POST',
      credentials: 'include'
    })
  },

  checkAuth: () => {
    return apiRequest('/admin/check', {
      method: 'GET',
      credentials: 'include'
    })
  },

  isAuthenticated: async () => {
    const response = await adminService.checkAuth()
    return response.ok && response.data?.is_admin === true
  },

  waitForSession: () => waitForAuthState(() => adminService.checkAuth(), 'is_admin'),

  createAnnouncement: (announcementData) => {
    return apiRequest('/admin/announcement', {
      method: 'POST',
      body: JSON.stringify(announcementData),
      credentials: 'include'
    })
  },

  updateMaintenance: (maintenanceData) => {
    return apiRequest('/admin/maintenance', {
      method: 'POST',
      body: JSON.stringify(maintenanceData),
      credentials: 'include'
    })
  },

  getSystemStatus: () => {
    return apiRequest('/system/status', {
      method: 'GET',
      credentials: 'include'
    })
  },

  listUsers: () => {
    return apiRequest('/admin/users', {
      method: 'GET',
      credentials: 'include'
    })
  },

  extendPurchase: (userId, months) => {
    return apiRequest(`/admin/users/${userId}/extend`, {
      method: 'POST',
      body: JSON.stringify({ months }),
      credentials: 'include'
    })
  },

  setUserActive: (userId, active) => {
    return apiRequest(`/admin/users/${userId}/active`, {
      method: 'POST',
      body: JSON.stringify({ active }),
      credentials: 'include'
    })
  },

  listAnnouncements: () => {
    return apiRequest('/admin/announcements', {
      method: 'GET',
      credentials: 'include'
    })
  },

  deleteAnnouncement: (id) => {
    return apiRequest(`/admin/announcement/${id}`, {
      method: 'DELETE',
      credentials: 'include'
    })
  },

  setPurchaseStatus: (userId, hasPurchased, expiresAt = null) => {
    return apiRequest(`/admin/users/${userId}/purchase`, {
      method: 'POST',
      body: JSON.stringify({ hasPurchased, expiresAt }),
      credentials: 'include'
    })
  }
}
