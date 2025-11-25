import { useState } from "react";
import { Link } from "react-router-dom";
import { Form, Input, Select, Button, Card, Typography, message, Space } from "antd";
import api from "../api";
import "./NoticeComposer.css";

const { Title } = Typography;
const { Option } = Select;
const { TextArea } = Input;

type NoticeContext = {
  content: string;
  priority: string;
  target_class?: string;
  target_role?: string;
};

type NoticeBody = {
  command: "post_notice";
  user_id: string;
  role: string;
  timestamp: string;
  context: NoticeContext;
};

type ApiResp = {
  status?: string;
  notice_id?: number | null;
  detail?: string;
};

export default function NoticeComposer() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState<boolean>(false);

  const storedUser = localStorage.getItem("userId") ?? "";
  const storedRole = localStorage.getItem("role") ?? "teacher";

  const submitNotice = async (values: { userId: string; role: string; content: string; priority: "normal" | "urgent"; targetClass?: string; targetRole?: string; }) => {
    const { userId, role, content, priority, targetClass, targetRole } = values;
    if (!userId) {
      message.error("请填写 user_id");
      return;
    }
    if (!content.trim()) {
      message.error("请输入内容");
      return;
    }

    setLoading(true);
    try {
      const body: NoticeBody = {
        command: "post_notice",
        user_id: String(userId),
        role: String(role),
        timestamp: new Date().toISOString(),
        context: {
          content: content.trim(),
          priority,
          target_class: targetClass || undefined,
          target_role: targetRole || undefined,
        },
      };

      const resp = await api.post<ApiResp>("/mcp/notice", body);
      if (resp.data?.status === "success") {
        message.success("发布成功: " + JSON.stringify(resp.data));
        localStorage.setItem("userId", userId);
        localStorage.setItem("role", role);
        form.resetFields(["content", "targetClass", "targetRole"]);
      } else {
        message.error("发布失败: " + JSON.stringify(resp.data));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("notice post error", err);
      message.error("请求错误: " + msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card className="notice-composer-card">
        <Title level={3}>发布通知</Title>
        <Form
          form={form}
          onFinish={submitNotice}
          layout="vertical"
          initialValues={{
            userId: storedUser,
            role: storedRole,
            priority: "normal",
          }}
        >
          <Form.Item label="User ID" name="userId" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Role" name="role" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Priority" name="priority" rules={[{ required: true }]}>
            <Select>
              <Option value="normal">Normal</Option>
              <Option value="urgent">Urgent</Option>
            </Select>
          </Form.Item>
          <Form.Item label="Target Class" name="targetClass">
            <Input placeholder=" (optional)" />
          </Form.Item>
          <Form.Item label="Target Role" name="targetRole">
            <Input placeholder=" (optional)" />
          </Form.Item>
          <Form.Item label="Content" name="content" rules={[{ required: true }]}>
            <TextArea rows={4} />
          </Form.Item>
          <Form.Item>
            <Space className="notice-composer-actions">
              <Button type="primary" htmlType="submit" loading={loading}>
                发布
              </Button>
              <Button htmlType="button" onClick={() => form.resetFields(["content", "targetClass", "targetRole"])}>
                重置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
