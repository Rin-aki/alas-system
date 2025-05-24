/**
 * API服务 - 处理与后端的通信
 */

// 后端API基础URL
const API_BASE_URL = 'http://localhost:8000';

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
  
  // 如果存在令牌，添加到请求头
  const token = localStorage.getItem('token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // 合并选项
  const requestOptions = {
    ...options,
    headers
  };
  
  try {
    const response = await fetch(url, requestOptions);
    
    // 解析响应JSON
    const data = await response.json();
    
    // 返回状态和数据
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
  /**
   * 用户注册
   * @param {Object} userData - 用户数据 {email, password}
   * @returns {Promise} - 返回响应Promise
   */
  register: (userData) => {
    return apiRequest('/register', {
      method: 'POST',
      body: JSON.stringify(userData)
    });
  },
  
  /**
   * 用户登录
   * @param {Object} credentials - 登录凭证 {email, password}
   * @returns {Promise} - 返回响应Promise
   */
  login: (credentials) => {
    return apiRequest('/login', {
      method: 'POST',
      body: JSON.stringify(credentials)
    });
  },
  
  /**
   * 购买服务
   * @param {Object} purchaseData - 购买数据 {days}
   * @returns {Promise} - 返回响应Promise
   */
  purchase: (purchaseData) => {
    return apiRequest('/purchase', {
      method: 'POST',
      body: JSON.stringify(purchaseData)
    });
  },
  
  /**
   * 获取购买状态
   * @returns {Promise} - 返回响应Promise
   */
  getPurchaseStatus: () => {
    return apiRequest('/purchase/status', {
      method: 'GET'
    });
  }

//   /**
//    * 创建容器
//    * @returns {Promise} - 返回响应Promise
//    */
//   createContainer: () => {
//     return apiRequest('/create_container', {
//       method: 'POST'
//     });
//   }
// };
  /**
   * 获取购买状态
   * @returns {Promise} - 返回响应Promise
   */


  
}
