import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { List, Button, Input, DatePicker, Form, Card, Typography, message, Spin, Alert } from 'antd';
import api from '../api';
import type { Memo } from '../types/api';

const { Title } = Typography;

type Props = {
  role?: string;
  requesterId?: string;
};

export default function MemoManager({ role = 'student', requesterId }: Props) {
  const [memos, setMemos] = useState<Memo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!requesterId || role !== 'student') return;

    setLoading(true);
    setError(null);
    api.post('/mcp/command', {
      command: 'get_today_memo',
      user_id: requesterId,
      role: role,
      timestamp: new Date().toISOString(),
      context: {},
    }).then(resp => {
      if (resp.data?.status === 'success' && Array.isArray(resp.data.memos)) {
        const fetchedMemos = resp.data.memos.map((m: Memo) => ({ ...m, is_confirmed: false }));
        setMemos(fetchedMemos);
      } else {
        setError(resp.data?.detail ?? '获取备忘录失败');
      }
    }).catch(e => {
      setError(e.message);
    }).finally(() => {
      setLoading(false);
    });
  }, [requesterId, role]);

  const handleAddMemo = (values: { content: string; remind_date: { format: (arg0: string) => string; }; }) => {
    const { content, remind_date } = values;
    if (!content || !remind_date || !requesterId) {
      message.error('内容和日期不能为空');
      return;
    }
    const remindDate = remind_date.format('YYYY-MM-DD');

    api.post('/mcp/command', {
      command: 'add_memo',
      user_id: requesterId,
      role: 'student',
      timestamp: new Date().toISOString(),
      context: {
        content,
        remind_date: remindDate,
      }
    }).then(resp => {
      if (resp.data?.status === 'success' && resp.data.memo_id) {
        const newMemo: Memo = {
          id: resp.data.memo_id,
          content,
          remind_date: remindDate,
          is_confirmed: false,
        };
        setMemos([newMemo, ...memos]);
        form.resetFields();
        message.success('添加成功');
      } else {
        message.error('添加失败: ' + (resp.data?.detail ?? '未知错误'));
      }
    }).catch(e => {
      message.error('请求失败: ' + e.message);
    });
  };

  const handleConfirmMemo = (id: number) => {
    if (!requesterId) return;

    api.post('/mcp/command', {
      command: 'confirm_memo',
      user_id: requesterId,
      role: 'student',
      timestamp: new Date().toISOString(),
      context: {
        memo_id: id,
      }
    }).then(resp => {
      if (resp.data?.status === 'success') {
        setMemos(memos.filter(memo => memo.id !== id));
        message.success('确认成功');
      } else {
        message.error('确认失败: ' + (resp.data?.detail ?? '未知错误'));
      }
    }).catch(e => {
      message.error('请求失败: ' + e.message);
    });
  };

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card>
        <Title level={3}>备忘录管理</Title>

        {role === 'student' && (
          <Card type="inner" title="添加新备忘" style={{ marginBottom: "24px" }}>
            <Form form={form} onFinish={handleAddMemo} layout="inline">
              <Form.Item name="content" rules={[{ required: true, message: '请输入内容' }]}>
                <Input placeholder="备忘内容" style={{ minWidth: 300 }} />
              </Form.Item>
              <Form.Item name="remind_date" rules={[{ required: true, message: '请选择日期' }]}>
                <DatePicker />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit">添加</Button>
              </Form.Item>
            </Form>
          </Card>
        )}

        <Spin spinning={loading}>
          {error && <Alert message={error} type="error" style={{ marginBottom: "20px" }} />}
          <List
            header={<div>备忘列表（当前仅显示今日）</div>}
            bordered
            dataSource={memos}
            renderItem={memo => (
              <List.Item
                actions={role === 'student' ? [<Button onClick={() => handleConfirmMemo(memo.id)}>完成并移除</Button>] : []}
              >
                <List.Item.Meta
                  title={memo.content}
                  description={`提醒日期: ${memo.remind_date}`}
                />
              </List.Item>
            )}
          />
        </Spin>
      </Card>
    </div>
  );
}
