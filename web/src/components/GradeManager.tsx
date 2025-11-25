import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Table, Button, Modal, Form, Input, Select, Card, Typography, message, Spin, Alert, Popconfirm, Space } from 'antd';
import api from '../api';
import './GradeManager.css';

const { Title } = Typography;
const { Option } = Select;

interface User {
  id: number;
  username: string;
  role: 'teacher' | 'student' | 'parent' | 'admin';
  class_id?: number;
  managed_class_id?: number;
}

interface Grade {
  id: number;
  student_id: number;
  subject: string;
  score: number;
  semester: string;
  teacher_id: number;
}

interface Student {
  id: number;
  username: string;
}

const GradeManager: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingGrade, setEditingGrade] = useState<Grade | null>(null);
  const [form] = Form.useForm();
  const [adminClassId, setAdminClassId] = useState('');
  const [currentChild, setCurrentChild] = useState<Student | null>(null);
  const [children, setChildren] = useState<Student[]>([]);

  const fetchUser = useCallback(async () => {
    const userId = localStorage.getItem('userId');
    if (userId) {
      try {
        const response = await api.get(`/mcp/user/${userId}`);
        setUser(response.data.user);
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

  const fetchStudents = useCallback(async (classId: number) => {
    try {
      const requesterId = localStorage.getItem('userId');
      const response = await api.get(`/mcp/class/${classId}/students?requester_id=${requesterId}`);
      setStudents(response.data.students);
    } catch {
      setError('无法获取学生列表');
    }
  }, []);

  const fetchClassGrades = useCallback(async (classId: number) => {
    setLoading(true);
    try {
      const requesterId = localStorage.getItem('userId');
      const response = await api.get(`/mcp/grades/class/${classId}?requester_id=${requesterId}`);
      setGrades(response.data.items);
    } catch {
      setError('无法获取班级成绩');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStudentGrades = useCallback(async (studentId: string) => {
    setLoading(true);
    try {
      const requesterId = localStorage.getItem('userId');
      const response = await api.get(`/mcp/grades/student/${studentId}?requester_id=${requesterId}`);
      setGrades(response.data.grades || []);
    } catch {
      setError('无法获取成绩');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchParentChildren = useCallback(async (parentId: string) => {
    try {
      const response = await api.get(`/mcp/parent/${parentId}/children?requester_id=${parentId}`);
      if (response.data.children && response.data.children.length > 0) {
        setChildren(response.data.children);
        setCurrentChild(response.data.children[0]);
        fetchStudentGrades(String(response.data.children[0].id));
      } else {
        setError('您还没有关联的孩子，请先选择孩子');
      }
    } catch {
      setError('无法获取孩子信息');
    }
  }, [fetchStudentGrades]);

  const handleChildChange = (childId: string) => {
    const selectedChild = children.find(child => child.id.toString() === childId);
    if (selectedChild) {
      setCurrentChild(selectedChild);
      fetchStudentGrades(childId);
    }
  };

  useEffect(() => {
    if (user?.role === 'teacher' && user.managed_class_id) {
      fetchStudents(user.managed_class_id);
      fetchClassGrades(user.managed_class_id);
    } else if (user?.role === 'admin' && adminClassId) {
      fetchStudents(parseInt(adminClassId));
      fetchClassGrades(parseInt(adminClassId));
    } else if (user?.role === 'student') {
      const studentId = localStorage.getItem('userId');
      if (studentId) {
        fetchStudentGrades(studentId);
      }
    } else if (user?.role === 'parent') {
      const parentId = localStorage.getItem('userId');
      if (parentId) {
        fetchParentChildren(parentId);
      }
    }
  }, [user, adminClassId, fetchStudents, fetchClassGrades, fetchStudentGrades, fetchParentChildren]);

  const handleAddOrUpdateGrade = async (values: Grade) => {
    const requesterId = localStorage.getItem('userId');
    const classId = user?.role === 'teacher' ? user.managed_class_id : parseInt(adminClassId);
    try {
      if (editingGrade) {
        await api.put(`/mcp/grades/${editingGrade.id}?requester_id=${requesterId}`, values);
        message.success('成绩更新成功');
      } else {
        await api.post('/mcp/grades/add', { ...values, requester_id: requesterId });
        message.success('成绩添加成功');
      }
      if (classId) fetchClassGrades(classId);
      setIsModalVisible(false);
      setEditingGrade(null);
      form.resetFields();
    } catch {
      setError('操作失败');
    }
  };

  const handleDeleteGrade = async (gradeId: number) => {
    try {
      const requesterId = localStorage.getItem('userId');
      await api.delete(`/mcp/grades/${gradeId}?requester_id=${requesterId}`);
      message.success('成绩删除成功');
      const classId = user?.role === 'teacher' ? user.managed_class_id : parseInt(adminClassId);
      if (classId) fetchClassGrades(classId);
    } catch {
      setError('删除失败');
    }
  };

  const columns = [
    { title: '学生ID', dataIndex: 'student_id', key: 'student_id' },
    { title: '学期', dataIndex: 'semester', key: 'semester' },
    { title: '科目', dataIndex: 'subject', key: 'subject' },
    { title: '分数', dataIndex: 'score', key: 'score' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Grade) => (
        <Space size="middle">
          <Button onClick={() => { setEditingGrade(record); setIsModalVisible(true); form.setFieldsValue(record); }}>编辑</Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDeleteGrade(record.id)}>
            <Button danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (loading) return <Spin />;
  if (error) return <Alert message={error} type="error" />;

  return (
    <div style={{ padding: "24px" }}>
      <Link to="/"><Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button></Link>
      <Card className="grade-manager-card">
        <Title level={3}>成绩管理</Title>
        {(user?.role === 'teacher' || user?.role === 'admin') && (
          <>
            {user.role === 'admin' && (
              <Input.Search
                className="admin-search"
                placeholder="输入班级ID"
                enterButton="搜索班级"
                onSearch={value => setAdminClassId(value)}
              />
            )}
            <Button className="add-grade-button" type="primary" onClick={() => { setEditingGrade(null); setIsModalVisible(true); form.resetFields(); }}>
              录入成绩
            </Button>
            <Table columns={columns} dataSource={grades} rowKey="id" scroll={{ x: 'max-content' }} />
          </>
        )}
        {user?.role === 'student' && <Table columns={columns.slice(1, 4)} dataSource={grades} rowKey="id" scroll={{ x: 'max-content' }} />}
        {user?.role === 'parent' && (
          <>
            {children.length > 0 && (
              <div style={{ marginBottom: '20px' }}>
                <span style={{ marginRight: '10px' }}>选择孩子：</span>
                <Select 
                  value={currentChild?.id.toString()} 
                  onChange={handleChildChange}
                  style={{ width: 200 }}
                >
                  {children.map(child => (
                    <Option key={child.id} value={child.id.toString()}>
                      {child.username}
                    </Option>
                  ))}
                </Select>
              </div>
            )}
            {currentChild && (
              <div style={{ marginBottom: '20px' }}>
                <span>正在查看：<strong>{currentChild.username}</strong> 的成绩</span>
              </div>
            )}
            <Table columns={columns.slice(1, 4)} dataSource={grades} rowKey="id" scroll={{ x: 'max-content' }} />
          </>
        )}
      </Card>

      <Modal
        title={editingGrade ? '编辑成绩' : '录入成绩'}
        visible={isModalVisible}
        onCancel={() => { setIsModalVisible(false); setEditingGrade(null); }}
        onOk={() => form.submit()}
      >
        <Form form={form} onFinish={handleAddOrUpdateGrade} layout="vertical">
          <Form.Item name="student_id" label="学生" rules={[{ required: true }]}>
            <Select placeholder="选择学生">
              {students.map(s => <Option key={s.id} value={s.id}>{s.username}</Option>)}
            </Select>
          </Form.Item>
          <Form.Item name="subject" label="科目" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="score" label="分数" rules={[{ required: true }]}>
            <Input type="number" />
          </Form.Item>
          <Form.Item name="semester" label="学期" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default GradeManager;
