import React, { useState, useEffect } from 'react';
import { Alert } from 'antd';

const OfflineStatus: React.FC = () => {
  const [isOnline, setIsOnline] = useState<boolean>(navigator.onLine);
  const [queuedRequests, setQueuedRequests] = useState<number>(0);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    const checkQueuedRequests = async () => {
      if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        try {
          setQueuedRequests(0);
        } catch (error) {
          console.error('Error checking queued requests:', error);
        }
      }
    };

    const interval = setInterval(checkQueuedRequests, 5000);
    checkQueuedRequests();

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, []);

  if (isOnline && queuedRequests === 0) {
    return null;
  }

  const message = !isOnline
    ? "您处于离线状态。请求将在网络恢复后重试。"
    : `队列中有 ${queuedRequests} 个待重试请求`;

  return (
    <Alert
      message={message}
      type={isOnline ? 'success' : 'warning'}
      showIcon
      banner
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
      }}
    />
  );
};

export default OfflineStatus;
