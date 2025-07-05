/**
 * API服务 - 处理与后端的通信
 */

const API_BASE_URL = 'https://api.gjiang.xyz:58000';

/**
 * 发送请求到后端API
 * @param {string} endpoint - API端点
 * @param {Object} options - 请求选项
 * @returns {Promise} - 返回响应Promise
 */
export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  // 默认请求头
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };

  // 如果你用 Cookie 存token，下面这段可以去掉，避免重复认证
  // const token = localStorage.getItem('token');
  // if (token && !options.credentials) {
  //   headers['Authorization'] = `Bearer ${token}`;
  // }

  // 合并请求配置，确保 credentials 传递给 fetch
  const requestOptions = {
    ...options,
    headers,
    credentials: options.credentials || 'same-origin'  // 默认同源请求携带cookie，跨域必须传 'include'
  };

  try {
    const response = await fetch(url, requestOptions);

    const data = await response.json();

    return {
      status: response.status,
      data,
      ok: response.ok
    };
  } catch (error) {
    console.error('API请求错误:', error);
    throw error;
  }
}

/**
 * 用户API服务
 */
export const userService = {
  register: (userData) => {
    return apiRequest('/register', {
      method: 'POST',
      body: JSON.stringify(userData)
    });
  },

  login: (credentials) => {
    return apiRequest('/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      credentials: 'include'  // **关键：携带跨域cookie**
    });
  },

  purchase: (purchaseData) => {
    return apiRequest('/purchase', {
      method: 'POST',
      body: JSON.stringify(purchaseData),
      credentials: 'include'  // 需要认证请求也要加
    });
  },

  getPurchaseStatus: () => {
    return apiRequest('/purchase/status', {
      method: 'GET',
      credentials: 'include'  // 需要认证请求也要加
    });
  },
  authcheck: () => {
    return apiRequest('/auth/check', {
      method: "GET",
      credentials: 'include'  // 需要认证请求也要加
    });
  },
  logout: () => {
    return apiRequest('/logout', {
      method: "POST",
      credentials: 'include'  // 需要认证请求也要加
    });
  },
};
