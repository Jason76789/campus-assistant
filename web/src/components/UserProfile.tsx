import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Spin, Alert, Descriptions } from 'antd';
import api from '../api';
import type { UserProfile as UserProfileType } from '../types/api';

type Props = {
  requesterId: string;
  role: string;
};

export default function UserProfile({ requesterId, role }: Props) {
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<UserProfileType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!requesterId) return;
    setLoading(true);
    setError(null);
    api
      .get(`/mcp/user/profile?requester_id=${encodeURIComponent(requesterId)}`)
      .then((resp) => {
        if (resp.data?.status === 'success' && resp.data.user_profile) {
          setProfile(resp.data.user_profile as UserProfileType);
          form.setFieldsValue(resp.data.user_profile);
        } else {
          setError(resp.data?.detail ?? 'unknown response');
        }
      })
      .catch((e: unknown) => {
        let msg = String(e);
        if (e instanceof Error) msg = e.message;
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, [requesterId]);

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    if (profile) {
      form.setFieldsValue(profile);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      setError(null);
      await api.put(`/mcp/user/profile?requester_id=${encodeURIComponent(requesterId)}`, values);
      setProfile(values);
      setIsEditing(false);
    } catch (e) {
      let msg = String(e);
      if (e instanceof Error) msg = e.message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Spin size="large" />;
  if (error) return <Alert message={`获取个人信息失败: ${error}`} type="error" showIcon />;
  if (!profile) return null;

  return (
    <Card title="个人信息">
      {isEditing ? (
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名">
            <Input disabled={role === 'parent'} />
          </Form.Item>
          {role !== 'parent' && (
            <Form.Item name="external_id" label={role === 'teacher' ? '工号' : '学号'}>
              <Input />
            </Form.Item>
          )}
          <Form.Item label="班别">
            <Input value={profile.class_name} disabled />
          </Form.Item>
          <Form.Item label="学校">
            <Input value={profile.school_name} disabled />
          </Form.Item>
          <Form.Item label="入学年份">
            <Input value={profile.enrollment_year} disabled />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSave} style={{ marginRight: 8 }}>
              保存
            </Button>
            <Button onClick={handleCancel}>取消</Button>
          </Form.Item>
        </Form>
      ) : (
        <>
          <Descriptions bordered column={1}>
            <Descriptions.Item label="姓名">{profile.name}</Descriptions.Item>
            {role !== 'parent' && (
              <Descriptions.Item label={role === 'teacher' ? '工号' : '学号'}>
                {profile.external_id}
              </Descriptions.Item>
            )}
            <Descriptions.Item label="班别">{profile.class_name}</Descriptions.Item>
            <Descriptions.Item label="学校">{profile.school_name}</Descriptions.Item>
            <Descriptions.Item label="入学年份">{profile.enrollment_year}</Descriptions.Item>
          </Descriptions>
          <Button type="link" onClick={handleEdit} style={{ marginTop: 16 }}>
            编辑
          </Button>
        </>
      )}
    </Card>
  );
}
