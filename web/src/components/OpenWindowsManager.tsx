import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Form, Input, TimePicker, Checkbox, Button, List, Card, Typography, message, Spin, Alert, Popconfirm } from 'antd';
import { API_BASE_URL } from '../api';

const { Title, Text } = Typography;

type OpenWindow = {
  id: number;
  class_id: number;
  start_time: string;
  end_time: string;
  days_json: string[];
};

interface User {
  id: number;
  username: string;
  role: 'teacher' | 'student' | 'parent' | 'admin';
  class_id?: number;
  managed_class_id?: number;
}

// 与GradeManager相同的方式 - 不通过props接收用户信息，而是内部获取
const OpenWindowsManager: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [windows, setWindows] = useState<OpenWindow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adminClassId, setAdminClassId] = useState('');
  const [form] = Form.useForm();

  // 从localStorage和API获取用户信息 - 与GradeManager相同
  const fetchUser = useCallback(async () => {
    const userId = localStorage.getItem('userId');
    if (userId) {
      try {
        const response = await fetch(`${API_BASE_URL}/mcp/user/${userId}`);
        if (response.ok) {
          const data = await response.json();
          setUser(data.user);
        } else {
          setError('无法获取用户信息');
        }
      } catch {
        setError('无法获取用户信息');
      }
    } else {
      setError('未找到用户ID');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const currentClassId = user?.role === 'teacher' ? user.managed_class_id?.toString() : adminClassId;

  const fetchWindows = useCallback(async () => {
    if (!currentClassId || !user?.id) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/mcp/open_windows/${currentClassId}?requester_id=${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setWindows(data);
      } else {
        setWindows([]);
        setError('Failed to fetch open windows');
      }
    } catch (error) {
      console.error('Failed to fetch open windows:', error);
      setWindows([]);
      setError('An error occurred while fetching data.');
    } finally {
      setLoading(false);
    }
  }, [currentClassId, user?.id]);

  useEffect(() => {
    if (currentClassId && user?.id) {
      fetchWindows();
    } else {
      setWindows([]);
    }
  }, [currentClassId, user?.id, fetchWindows]);

  const handleCreate = async (values: { time_range: [{ format: (arg0: string) => string; }, { format: (arg0: string) => string; }]; days_json: string[]; }) => {
    if (!currentClassId || !user?.id) return;
    const { time_range, days_json } = values;
    const [start_time, end_time] = time_range;

    try {
      const response = await fetch(`${API_BASE_URL}/mcp/open_windows?requester_id=${user.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          class_id: parseInt(currentClassId),
          start_time: start_time.format('HH:mm'),
          end_time: end_time.format('HH:mm'),
          days_json,
        }),
      });
      if (response.ok) {
        message.success('创建成功');
        fetchWindows();
        form.resetFields();
      } else {
        message.error('创建失败');
      }
    } catch (error) {
      console.error('Failed to create open window:', error);
      message.error('创建时发生错误');
    }
  };

  const handleDelete = async (windowId: number) => {
    if (!user?.id) return;
    try {
      const response = await fetch(`${API_BASE_URL}/mcp/open_windows/${windowId}?requester_id=${user.id}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        message.success('删除成功');
        fetchWindows();
      } else {
        message.error('删除失败');
      }
    } catch (error) {
      console.error('Failed to delete open window:', error);
      message.error('删除时发生错误');
    }
  };

  if (user?.role !== 'teacher' && user?.role !== 'admin') {
    return <Alert message="您没有权限管理开放时段。" type="warning" />;
  }

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card>
        <Title level={3}>管理开放时段</Title>

        {user?.role === 'admin' && (
          <Form layout="inline" style={{ marginBottom: '20px' }}>
            <Form.Item label="班级ID">
              <Input
                value={adminClassId}
                onChange={(e) => setAdminClassId(e.target.value)}
                placeholder="请输入班级ID"
              />
            </Form.Item>
          </Form>
        )}

        {user?.role === 'teacher' && user.managed_class_id && (
          <Text strong>您管理的班级: {user.managed_class_id}</Text>
        )}

        {currentClassId ? (
          <>
            <Card type="inner" title={`为班级 ${currentClassId} 创建新开放时段`} style={{ marginTop: '20px' }}>
              <Form form={form} onFinish={handleCreate} layout="vertical">
                <Form.Item name="time_range" label="时间范围" rules={[{ required: true }]}>
                  <TimePicker.RangePicker format="HH:mm" />
                </Form.Item>
                <Form.Item name="days_json" label="适用日期" rules={[{ required: true }]}>
                  <Checkbox.Group options={['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']} />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" htmlType="submit">创建</Button>
                </Form.Item>
              </Form>
            </Card>

            <Spin spinning={loading}>
              {error && <Alert message={error} type="error" style={{ marginTop: '20px' }} />}
              <List
                header={<div>班级 {currentClassId} 的现有开放时段</div>}
                bordered
                dataSource={windows}
                renderItem={(w) => (
                  <List.Item
                    actions={[
                      <Popconfirm title="确定删除?" onConfirm={() => handleDelete(w.id)}>
                        <Button type="link" danger>删除</Button>
                      </Popconfirm>
                    ]}
                  >
                    <List.Item.Meta
                      title={`${w.start_time} - ${w.end_time}`}
                      description={w.days_json.join(', ')}
                    />
                  </List.Item>
                )}
                style={{ marginTop: '20px' }}
              />
            </Spin>
          </>
        ) : (
          <Text type="secondary" style={{ marginTop: '20px', display: 'block' }}>
            {user?.role === 'admin' ? '请输入班级ID开始管理。' : '您没有被分配到任何班级。'}
          </Text>
        )}
      </Card>
    </div>
  );
};

export default OpenWindowsManager;
