import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Form, Input, Button, Table, Typography, message, Space, Card, Select } from "antd";
import api from "../api";

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

type Message = {
  id: number;
  sender_id: number;
  content: string;
  priority: string;
  timestamp: string;
};

type CmdResp = {
  status: string;
  message_id?: number;
  detail?: string;
  messages?: Message[];
};

type Contact = {
  id: number;
  name: string;
  role: string;
};

export default function SimpleChat() {
  const userId = localStorage.getItem("userId") ?? "";
  const role = localStorage.getItem("role") ?? "";
  const [loading, setLoading] = useState(false);
  const [inbox, setInbox] = useState<Message[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    if (userId) {
      fetchContacts();
    }
  }, [userId]);

  async function fetchContacts() {
    setLoading(true);
    try {
      const resp = await api.get<{ status: string; contacts: Contact[] }>("/mcp/contacts", {
        params: { user_id: userId },
      });
      if (resp.data?.status === "success") {
        setContacts(resp.data.contacts || []);
      } else {
        message.error("获取联系人列表失败: " + JSON.stringify(resp.data));
      }
    } catch (err) {
      console.error(err);
      message.error("请求联系人列表错误: " + String(err));
    } finally {
      setLoading(false);
    }
  }

  async function sendMessage(values: { targetId: number; content: string }) {
    const { targetId, content } = values;
    if (!userId) {
      message.error("请先登录");
      return;
    }
    if (!targetId) {
      message.error("请选择收信人");
      return;
    }
    if (!content.trim()) {
      message.error("请输入内容");
      return;
    }
    setLoading(true);
    try {
      const body = {
        command: "leave_message",
        user_id: String(userId),
        role: String(role),
        timestamp: new Date().toISOString(),
        context: {
          receiver_id: String(targetId),
          content: content,
          priority: "normal",
        },
      };
      const resp = await api.post<CmdResp>("/mcp/command", body);
      if (resp.data?.status === "success") {
        message.success("消息已发送 message_id=" + resp.data.message_id);
        form.resetFields(["content"]);
      } else {
        message.error("发送失败: " + JSON.stringify(resp.data?.detail || resp.data));
      }
    } catch (err) {
      console.error(err);
      message.error("请求错误: " + String(err));
    } finally {
      setLoading(false);
    }
  }

  async function fetchInbox() {
    if (!userId) {
      message.error("请先登录");
      return;
    }
    setLoading(true);
    try {
      const body = {
        command: "get_messages",
        user_id: String(userId),
        role: String(role),
        timestamp: new Date().toISOString(),
        context: {},
      };
      const resp = await api.post<{
        status: string;
        messages: Message[];
        detail?: string;
      }>("/mcp/command", body);
      if (resp.data?.status === "success") {
        setInbox(resp.data.messages || []);
        message.success("消息拉取成功");
      } else {
        message.error("拉取失败: " + JSON.stringify(resp.data?.detail || resp.data));
      }
    } catch (err) {
      console.error(err);
      message.error("请求错误: " + String(err));
    } finally {
      setLoading(false);
    }
  }

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: '发送者', dataIndex: 'name', key: 'name' },
    { title: '内容', dataIndex: 'content', key: 'content' },
    { title: '优先级', dataIndex: 'priority', key: 'priority' },
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp' },
  ];

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card>
        <Title level={2}>简单会话 / 留言</Title>
        <Text>
          当前用户: <strong>{userId}</strong> (角色: <strong>{role}</strong>)
        </Text>
        <Form form={form} onFinish={sendMessage} layout="vertical" style={{ marginTop: "20px" }}>
          <Form.Item
            label="收信人"
            name="targetId"
            rules={[{ required: true, message: "请选择收信人!" }]}
          >
            <Select placeholder="选择收信人">
              {contacts.map((contact) => (
                <Option key={contact.id} value={contact.id}>
                  {contact.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="内容"
            name="content"
            rules={[{ required: true, message: "请输入内容!" }]}
          >
            <TextArea rows={4} placeholder="输入要发送的内容" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                发送
              </Button>
              <Button onClick={fetchInbox} loading={loading}>
                拉取我的消息
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Card title="我的消息 / 最近" style={{ marginTop: "24px" }}>
        <Table
          dataSource={inbox}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 5 }}
        />
      </Card>
    </div>
  );
}
