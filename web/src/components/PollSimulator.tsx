import { useState } from "react";
import { Link } from "react-router-dom";
import { Form, Input, InputNumber, Checkbox, Button, Table, Card, Typography, Alert, message, Space } from "antd";
import api from "../api";

const { Title } = Typography;

type OutgoingItem = {
  id: number;
  payload?: Record<string, unknown>;
  priority?: string;
  created_at?: string | null;
  deliver_after?: string | null;
};

type PollResp = {
  status: "success" | "error";
  items?: OutgoingItem[];
  detail?: string;
};

export default function PollSimulator() {
  const [form] = Form.useForm();
  const [items, setItems] = useState<OutgoingItem[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [processingIds, setProcessingIds] = useState<number[]>([]);

  const storedUid = localStorage.getItem("userId") ?? "";

  const doPoll = async (values: { userId: string; timeout: number; autoAck: boolean; }) => {
    const { userId, timeout, autoAck } = values;
    if (!userId) {
      message.error("请填写 user_id");
      return;
    }
    setErrMsg(null);
    setLoading(true);
    try {
      localStorage.setItem("userId", userId);
      const params: Record<string, string | number> = { user_id: userId, timeout: timeout };

      const resp = await api.get<PollResp>("/mcp/poll", { params });
      if (resp.data?.status === "success") {
        const its = resp.data.items ?? [];
        setItems(its);
        if (autoAck && its.length > 0) {
          const ids = its.map((i) => i.id);
          await ackIds(ids, userId);
        }
      } else {
        setErrMsg(resp.data?.detail ?? "server returned error");
      }
    } catch (err: unknown) {
      setErrMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const ackIds = async (ids: number[], userId: string) => {
    if (!ids.length) return;
    setProcessingIds((p) => [...p, ...ids]);
    try {
      await api.post("/mcp/ack", { ids, user_id: userId });
      setItems((cur) => cur.filter((it) => !ids.includes(it.id)));
      message.success(`Acknowledged ${ids.length} items.`);
    } catch (err: unknown) {
      message.error("ack 失败: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setProcessingIds((p) => p.filter((i) => !ids.includes(i)));
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    {
      title: 'Payload', dataIndex: 'payload', key: 'payload',
      render: (payload: Record<string, unknown>) => <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(payload ?? {}, null, 2)}</pre>
    },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    {
      title: 'Timestamps', key: 'timestamps',
      render: (_: unknown, record: OutgoingItem) => (
        <>
          <div>created: {record.created_at ?? "-"}</div>
          <div>deliver_after: {record.deliver_after ?? "-"}</div>
        </>
      )
    },
    {
      title: 'Action', key: 'action',
      render: (_: unknown, record: OutgoingItem) => (
        <Button
          size="small"
          onClick={() => ackIds([record.id], form.getFieldValue('userId'))}
          disabled={processingIds.includes(record.id)}
        >
          Ack
        </Button>
      )
    },
  ];

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card>
        <Title level={3}>Poll 模拟器</Title>
        <Form
          form={form}
          onFinish={doPoll}
          layout="inline"
          initialValues={{ userId: storedUid, timeout: 0, autoAck: false }}
          style={{ marginBottom: "20px" }}
        >
          <Form.Item label="User ID" name="userId" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Timeout (s)" name="timeout">
            <InputNumber min={0} />
          </Form.Item>
          <Form.Item name="autoAck" valuePropName="checked">
            <Checkbox>Auto Ack</Checkbox>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>
              Poll
            </Button>
          </Form.Item>
        </Form>

        {errMsg && <Alert message={errMsg} type="error" style={{ marginBottom: "20px" }} />}

        <Space style={{ marginBottom: "16px" }}>
          <Button
            onClick={() => ackIds(items.map((i) => i.id), form.getFieldValue('userId'))}
            disabled={processingIds.length > 0 || items.length === 0}
          >
            Ack 全部 ({items.length})
          </Button>
        </Space>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          pagination={false}
        />
      </Card>
    </div>
  );
}
