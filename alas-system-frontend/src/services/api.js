/**
 * API服务 - 处理与后端的通信
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

if (!API_BASE_URL) {
  console.warn('VITE_API_BASE_URL 未设置，API 请求将使用相对路径。')
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

  logout: () => {
    return apiRequest('/logout', {
      method: 'POST',
      credentials: 'include'
    })
  },

  reconnect: () => {
    return apiRequest('/reconnect', {
      method: 'POST',
      credentials: 'include'
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
  }
}
