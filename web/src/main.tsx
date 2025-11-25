import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import './index.css'
import 'antd/dist/reset.css';
import App from './App'

// 配置 React Router 未来标志以消除警告
if (typeof window !== 'undefined') {
  // 在全局对象上设置 React Router 未来标志
  Object.assign(window, {
    __reactRouterVersion: '6',
    __reactRouterFutureFlags__: {
      v7_startTransition: true,
      v7_relativeSplatPath: true,
    },
  });
}

// 完全禁用 Service Worker 并清除所有缓存
if ('serviceWorker' in navigator) {
  // 注销所有已注册的 Service Worker
  navigator.serviceWorker.getRegistrations().then(function(registrations) {
    for(const registration of registrations) {
      registration.unregister();
      console.log('Service Worker unregistered:', registration);
    }
  }).catch(function(error) {
    console.log('Service Worker unregistration failed:', error);
  });
  
  // 清除所有缓存
  caches.keys().then(function(cacheNames) {
    return Promise.all(
      cacheNames.map(function(cacheName) {
        return caches.delete(cacheName);
      })
    );
  }).catch(function(error) {
    console.log('Cache deletion failed:', error);
  });
  
  // 防止新的 Service Worker 注册
  navigator.serviceWorker.addEventListener('controllerchange', function(event) {
    console.log('Service Worker controller changed:', event);
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
)
