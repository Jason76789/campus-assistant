import React, { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Table, Button, Input, Select, Form, Card, Typography, Space, message, Tag, Popconfirm, Alert } from "antd";
import api from "../api";

const { Title } = Typography;
const { Option } = Select;

type OutgoingItem = {
  id: number;
  target_user_id: number;
  payload: Record<string, unknown>;
  priority: string;
  deliver_after: string | null;
  delivered: boolean;
  created_at: string | null;
  delivered_at: string | null;
};

type OutgoingListResp = {
  status: "success" | "error";
  page?: number;
  size?: number;
  total?: number;
  items?: OutgoingItem[];
  detail?: string;
};

export default function OutgoingList() {
  const [form] = Form.useForm();
  const [items, setItems] = useState<OutgoingItem[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const fetchPage = useCallback(async (page: number, pageSize: number, filters: Record<string, unknown>) => {
    const requesterId = localStorage.getItem("userId");
    if (!requesterId) {
      setError("请先登录。");
      setItems([]);
      setPagination(p => ({ ...p, total: 0 }));
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = {
        requester_id: requesterId,
        page,
        size: pageSize,
        ...filters,
      };
      const resp = await api.get<OutgoingListResp>("/mcp/outgoing/list", { params });
      if (resp.data?.status === "success") {
        setItems(resp.data.items ?? []);
        setPagination({
          current: resp.data.page ?? page,
          pageSize: resp.data.size ?? pageSize,
          total: resp.data.total ?? 0,
        });
      } else {
        setError(resp.data?.detail ?? "server returned error");
      }
    } catch (err: unknown) {
      const s = err instanceof Error ? err.message : String(err);
      setError("请求失败: " + s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const filters = form.getFieldsValue();
    fetchPage(pagination.current, pagination.pageSize, filters);
  }, [pagination.current, pagination.pageSize, fetchPage, form]);

  const handleTableChange = (newPagination: { current?: number, pageSize?: number }) => {
    setPagination(prev => ({ ...prev, ...newPagination }));
  };

  const onFinish = (values: Record<string, unknown>) => {
    setPagination(prev => ({ ...prev, current: 1 }));
    // 使用函数式更新后的 pageSize
    const currentPageSize = pagination.pageSize;
    fetchPage(1, currentPageSize, values);
  };

  const markDelivered = async (ids: React.Key[]) => {
    if (!ids.length) return;
    try {
      await api.post("/mcp/outgoing/mark_delivered", { ids });
      message.success("标记成功");
      setSelectedRowKeys([]);
      fetchPage(pagination.current, pagination.pageSize, form.getFieldsValue());
    } catch (err: unknown) {
      message.error("操作失败: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const deleteItems = async (ids: React.Key[]) => {
    if (!ids.length) return;
    try {
      await api.post("/mcp/outgoing/delete", { ids });
      message.success("删除成功");
      setSelectedRowKeys([]);
      fetchPage(pagination.current, pagination.pageSize, form.getFieldsValue());
    } catch (err: unknown) {
      message.error("删除失败: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id' },
    { title: 'Target User', dataIndex: 'target_user_id', key: 'target_user_id' },
    {
      title: 'Priority', dataIndex: 'priority', key: 'priority',
      render: (priority: string) => <Tag color={priority === 'urgent' ? 'red' : 'blue'}>{priority}</Tag>
    },
    {
      title: 'Payload', dataIndex: 'payload', key: 'payload',
      render: (payload: Record<string, unknown>) => <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(payload, null, 2)}</pre>
    },
    { title: 'Created At', dataIndex: 'created_at', key: 'created_at' },
    {
      title: 'Delivered', dataIndex: 'delivered', key: 'delivered',
      render: (delivered: boolean) => <Tag color={delivered ? 'green' : 'gold'}>{String(delivered)}</Tag>
    },
    {
      title: 'Actions', key: 'actions',
      render: (_: unknown, record: OutgoingItem) => (
        <Space size="middle">
          <Button size="small" onClick={() => markDelivered([record.id])} disabled={record.delivered}>Mark Delivered</Button>
          <Popconfirm title="确定删除?" onConfirm={() => deleteItems([record.id])}>
            <Button size="small" danger>Delete</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
  };

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      <Card>
        <Title level={3}>Outgoing Queue 浏览</Title>
        <Form form={form} onFinish={onFinish} layout="inline" style={{ marginBottom: "20px" }}>
          <Form.Item name="target_user_id">
            <Input placeholder="Target User ID" />
          </Form.Item>
          <Form.Item name="delivered">
            <Select placeholder="Delivered Status" style={{ width: 150 }} allowClear>
              <Option value="0">Undelivered</Option>
              <Option value="1">Delivered</Option>
            </Select>
          </Form.Item>
          <Form.Item name="priority">
            <Select placeholder="Priority" style={{ width: 120 }} allowClear>
              <Option value="urgent">Urgent</Option>
              <Option value="normal">Normal</Option>
            </Select>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">查询</Button>
          </Form.Item>
        </Form>

        {error && <Alert message={error} type="error" style={{ marginBottom: "20px" }} />}

        <Space style={{ marginBottom: "16px" }}>
          <Button onClick={() => markDelivered(selectedRowKeys)} disabled={!selectedRowKeys.length}>
            标记已投递 (选中)
          </Button>
          <Popconfirm title="确定删除选中的项?" onConfirm={() => deleteItems(selectedRowKeys)}>
            <Button danger disabled={!selectedRowKeys.length}>
              删除 (选中)
            </Button>
          </Popconfirm>
        </Space>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          pagination={pagination}
          loading={loading}
          onChange={handleTableChange}
          rowSelection={rowSelection}
        />
      </Card>
    </div>
  );
}
