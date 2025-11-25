import axios from "axios";

// 移动端和Web端的API基础URL配置
const getBaseURL = () => {
  // 如果是移动端环境
  if (window.cordova || window.Capacitor) {
    // 在移动端，我们需要使用与页面相同的协议
    // 由于Capacitor使用https，我们需要确保后端也使用https
    // 或者配置Capacitor允许混合内容
    const protocol = window.location.protocol;
    if (protocol === 'https:') {
      // 如果页面是https，API也需要是https，或者配置允许混合内容
      // 对于开发环境，我们仍然使用http，但需要配置Android允许明文流量
      return "http://10.0.2.2:8000";
    }
    return "http://10.0.2.2:8000";
  }
  
  // Web环境使用环境变量或默认值
  if (typeof process !== "undefined" && process.env.REACT_APP_API_BASE) {
    return process.env.REACT_APP_API_BASE;
  }
  
  if (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }
  
  // 后端服务运行在固定的 127.0.0.1:8000
  // 无论前端通过 localhost:5174 还是 192.168.52.1:5174 访问，都连接到同一个后端
  return "http://127.0.0.1:8000";
};

const baseURL = getBaseURL();

console.log("API Base URL:", baseURL);

export { baseURL as API_BASE_URL };

const api = axios.create({
  baseURL,
  timeout: 30000, // 增加超时时间
  headers: {
    "Content-Type": "application/json",
  },
});

// 添加请求拦截器用于调试
api.interceptors.request.use(
  (config) => {
    console.log("API Request:", config.method?.toUpperCase(), config.url);
    if (window.cordova || window.Capacitor) {
      console.log("Full Request Config:", config);
    }
    return config;
  },
  (error) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// 添加响应拦截器用于调试
api.interceptors.response.use(
  (response) => {
    console.log("API Response:", response.status, response.data);
    return response;
  },
  (error) => {
    console.error("API Response Error:", error);
    if (error.code === 'ECONNABORTED') {
      console.error("请求超时，请检查网络连接");
    } else if (error.response) {
      console.error("服务器响应错误:", error.response.status, error.response.data);
    } else if (error.request) {
      console.error("网络请求失败，请检查API服务是否运行");
    }
    return Promise.reject(error);
  }
);

export default api;
