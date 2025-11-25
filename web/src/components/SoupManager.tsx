import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Input, Spin, Alert, Typography, message, Space } from 'antd';
import api from '../api';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

interface Soup {
  id: number;
  content: string;
}

interface SoupManagerProps {
  userRole: 'teacher' | 'admin';
  requesterId?: string;
  classId?: string;
}

const SoupManager: React.FC<SoupManagerProps> = ({ userRole, requesterId, classId }) => {
  const [soup, setSoup] = useState<Soup | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSoup = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get(`/mcp/daily_quote/${classId}`);
      if (resp.data?.status === 'success' && resp.data.quote) {
        setSoup(resp.data.quote);
      } else {
        setError(resp.data?.detail || '未能加载到鸡汤');
        setSoup(null);
      }
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      setError(errorMessage || '请求失败');
    } finally {
      setLoading(false);
    }
  }, [classId]);

  useEffect(() => {
    if (classId) {
      fetchSoup();
    }
  }, [classId, fetchSoup]);

  const triggerSoup = async () => {
    if (!soup) return;
    try {
      const resp = await api.post(`/mcp/trigger_daily_quote/${soup.id}`);
      if (resp.data?.status === 'success') {
        message.success(`成功为 ${resp.data.enqueued} 个用户触发了鸡汤！`);
      } else {
        message.error('触发失败: ' + resp.data?.detail);
      }
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      message.error('请求失败: ' + errorMessage);
    }
  };

  const handleEdit = () => {
    if (soup) {
      setEditedContent(soup.content);
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (!soup || !requesterId) return;
    try {
      const resp = await api.put(`/mcp/daily_quote/${soup.id}?requester_id=${requesterId}`, {
        content: editedContent,
      });
      if (resp.data?.status === 'success') {
        setSoup({ ...soup, content: editedContent });
        setIsEditing(false);
        message.success('保存成功！');
      } else {
        message.error('保存失败: ' + resp.data?.detail);
      }
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      message.error('请求失败: ' + errorMessage);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
  };

  return (
    <Card style={{ margin: '16px 0' }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: '16px' }}>返回主页</Button>
      </Link>
      <Title level={2}>每日鸡汤管理</Title>
      {loading && <Spin />}
      {error && <Alert message={`错误: ${error}`} type="error" showIcon />}
      {!loading && !error && (
        <>
          {soup ? (
            isEditing ? (
              <div>
                <TextArea
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  rows={4}
                  style={{ marginBottom: '8px' }}
                />
                <Space>
                  <Button type="primary" onClick={handleSave}>保存</Button>
                  <Button onClick={handleCancel}>取消</Button>
                </Space>
              </div>
            ) : (
              <div>
                <Paragraph><strong>当前鸡汤:</strong> {soup.content}</Paragraph>
                <Space>
                  <Button onClick={triggerSoup}>触发</Button>
                  {userRole === 'teacher' && (
                    <Button onClick={handleEdit}>编辑</Button>
                  )}
                </Space>
              </div>
            )
          ) : (
            <Paragraph>今日无鸡汤。</Paragraph>
          )}
        </>
      )}
    </Card>
  );
};

export default SoupManager;
