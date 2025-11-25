import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Select, Button, Spin, Alert, Typography, Space, message } from 'antd';
import api from '../api';

const { Title, Text } = Typography;
const { Option } = Select;

interface Student {
  id: number;
  external_id: string;
  username: string;
  class_id: number;
}

export default function ParentChildSelection() {
  const [loading, setLoading] = useState(false);
  const [students, setStudents] = useState<Student[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const parentId = localStorage.getItem('userId');

  useEffect(() => {
    if (!parentId) {
      message.error('未找到用户信息，请重新登录');
      navigate('/login');
      return;
    }

    fetchAvailableStudents();
  }, [parentId, navigate]);

  const fetchAvailableStudents = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get(`/mcp/parent/available_students?parent_id=${encodeURIComponent(parentId!)}`);
      if (resp.data?.status === 'success') {
        setStudents(resp.data.students || []);
        if (resp.data.students.length === 0) {
          setError('当前班级中没有可关联的学生');
        }
      } else {
        setError(resp.data?.detail || '获取学生列表失败');
      }
    } catch (e: unknown) {
      let msg = String(e);
      if (e instanceof Error) msg = e.message;
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectStudent = async () => {
    if (!selectedStudent) {
      message.error('请选择您的孩子');
      return;
    }

    setLoading(true);
    try {
      const resp = await api.post('/mcp/parent/select_child', {
        parent_id: String(parentId),
        student_id: String(selectedStudent)
      });

      if (resp.data?.status === 'success') {
        message.success('孩子选择成功');
        // 更新本地存储中的用户名，显示为"孩子姓名+家长"
        const selectedStudentInfo = students.find(s => s.id.toString() === selectedStudent);
        if (selectedStudentInfo) {
          const newUsername = `${selectedStudentInfo.username}家长`;
          localStorage.setItem('username', newUsername);
        }
        navigate('/', { replace: true });
      } else {
        message.error(resp.data?.detail || '选择孩子失败');
      }
    } catch (e: unknown) {
      let msg = String(e);
      if (e instanceof Error) msg = e.message;
      message.error('选择孩子失败: ' + msg);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login', { replace: true });
  };

  if (loading && students.length === 0) {
    return <Spin size="large" style={{ display: 'block', margin: '50px auto' }} />;
  }

  if (error) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
        <Card style={{ width: 500 }}>
          <Alert
            message="获取学生列表失败"
            description={error}
            type="error"
            showIcon
            action={
              <Space direction="vertical">
                <Button size="small" onClick={fetchAvailableStudents}>
                  重试
                </Button>
                <Button size="small" onClick={handleLogout}>
                  重新登录
                </Button>
              </Space>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
      <Card style={{ width: 500 }}>
        <Title level={2} style={{ textAlign: 'center', marginBottom: 30 }}>
          选择您的孩子
        </Title>
        
        <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 20 }}>
          请从同班级的学生中选择您的孩子
        </Text>

        <div style={{ marginBottom: 20 }}>
          <Text strong>选择孩子：</Text>
          <Select
            style={{ width: '100%', marginTop: 8 }}
            placeholder="请选择您的孩子"
            value={selectedStudent || undefined}
            onChange={setSelectedStudent}
            loading={loading}
          >
            {students.map(student => (
              <Option key={student.id} value={student.id}>
                {student.username} (学号: {student.external_id})
              </Option>
            ))}
          </Select>
        </div>

        <div style={{ textAlign: 'center' }}>
          <Space>
            <Button 
              type="primary" 
              onClick={handleSelectStudent}
              disabled={!selectedStudent}
              loading={loading}
            >
              确认选择
            </Button>
            <Button onClick={handleLogout}>
              重新登录
            </Button>
          </Space>
        </div>

        {students.length === 0 && !loading && (
          <Alert
            style={{ marginTop: 20 }}
            message="提示"
            description="当前班级中没有可关联的学生。请联系学校管理员确认班级信息。"
            type="info"
            showIcon
          />
        )}
      </Card>
    </div>
  );
}
