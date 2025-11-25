import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Select, Card, Typography, Space, message, Tabs } from "antd";
import api from "../api";
import "./Login.css";

const { Title } = Typography;
const { Option } = Select;

export default function Login() {
  const [loading, setLoading] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [registerForm] = Form.useForm();

  async function doLogin(values: { external_id: string; password: string }) {
    const { external_id, password } = values;
    if (!external_id || !password) {
      message.error("请输入账号和密码");
      return;
    }
    setLoading(true);
    try {
      console.log("开始登录请求:", external_id);
      
      // 在移动端添加更详细的日志
      if (window.cordova || window.Capacitor) {
        console.log("检测到移动端环境");
        alert("开始登录请求: " + external_id);
        
        // 检查网络连接（使用类型断言避免TypeScript错误）
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ((navigator as any).connection) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const connection = (navigator as any).connection;
          console.log("网络连接信息:", {
            type: connection.type,
            effectiveType: connection.effectiveType,
            downlink: connection.downlink,
            rtt: connection.rtt
          });
          alert(`网络类型: ${connection.effectiveType}, 速度: ${connection.downlink}Mbps`);
        } else {
          console.log("navigator.connection 不可用");
        }
      }
      
      // 测试网络连接（添加错误处理）
      try {
        const testResponse = await fetch(window.location.origin, { method: 'HEAD' });
        console.log("网络连接测试:", testResponse.status);
      } catch (testError) {
        console.error("网络连接测试失败:", testError);
        if (window.cordova || window.Capacitor) {
          alert("网络连接测试失败，请检查网络设置");
        }
      }
      
      const resp = await api.post("/mcp/auth/login", {
        external_id,
        password
      });
      
      console.log("登录响应:", resp.data);
      
      if (resp.data?.status !== "success") {
        const errorMsg = resp.data?.detail || "登录失败";
        console.error("登录失败:", errorMsg);
        if (window.cordova || window.Capacitor) {
          alert("登录失败: " + errorMsg);
        }
        message.error(errorMsg);
        setLoading(false);
        return;
      }

      const user = resp.data;
      localStorage.setItem("userId", String(user.user_id));
      localStorage.setItem("external_id", String(user.external_id));
      localStorage.setItem("username", String(user.username));
      localStorage.setItem("role", String(user.role));

      if (user.role === 'teacher' && user.managed_class_id) {
        localStorage.setItem("managed_class_id", String(user.managed_class_id));
      } else if (user.class_id) {
        localStorage.setItem("class_id", String(user.class_id));
      }

      console.log("本地存储设置完成:", {
        userId: localStorage.getItem("userId"),
        role: localStorage.getItem("role"),
        username: localStorage.getItem("username")
      });

      if (window.cordova || window.Capacitor) {
        alert("登录成功: " + user.username + " (" + user.role + ")");
      }
      
      message.success(`登录成功: ${user.username} (${user.role})`);
      
      // 如果是家长角色，检查是否已经选择了孩子
      if (user.role === 'parent') {
        try {
          const statusResp = await api.get(`/mcp/parent/status?parent_id=${encodeURIComponent(user.user_id)}`);
          if (statusResp.data?.status === 'success' && !statusResp.data.has_selected_child) {
            // 家长还没有选择孩子，跳转到选择页面
            console.log("家长未选择孩子，跳转到选择页面");
            if (window.cordova || window.Capacitor) {
              alert("家长未选择孩子，跳转到选择页面");
            }
            setTimeout(() => {
              navigate("/parent/select-child", { replace: true });
            }, 100);
            return;
          }
        } catch (err) {
          console.error("检查家长状态失败:", err);
          if (window.cordova || window.Capacitor) {
            alert("检查家长状态失败: " + err);
          }
          // 如果检查失败，仍然跳转到首页
        }
      }
      
      // 添加延迟确保存储完成
      setTimeout(() => {
        console.log("开始导航到首页");
        if (window.cordova || window.Capacitor) {
          alert("开始导航到首页");
        }
        navigate("/", { replace: true });
      }, 100);
    } catch (err: unknown) {
      console.error("login error", err);
      
      // 详细的错误处理，确保在移动端能看到具体错误信息
      let errorMessage = "登录请求失败";
      let errorDetails = "";
      
      if (err instanceof Error) {
        errorMessage = err.message;
        errorDetails = JSON.stringify({
          name: err.name,
          message: err.message,
          stack: err.stack
        }, null, 2);
      } else if (typeof err === 'object' && err !== null) {
        // 处理Axios错误或其他对象错误
        errorDetails = JSON.stringify(err, null, 2);
        if ('message' in err && typeof err.message === 'string') {
          errorMessage = err.message;
        } else if ('status' in err) {
          errorMessage = `请求失败，状态码: ${err.status}`;
        }
      } else {
        errorDetails = String(err);
      }
      
      console.error("登录错误详情:", errorMessage);
      console.error("完整错误对象:", errorDetails);
      
      if (window.cordova || window.Capacitor) {
        // 在移动端显示更详细的错误信息
        alert(`登录错误: ${errorMessage}\n\n详细信息: ${errorDetails.substring(0, 200)}...`);
      } else {
        message.error("登录失败: " + errorMessage);
      }
    } finally {
      setLoading(false);
    }
  }

  async function doRegister(values: { 
    external_id: string; 
    username: string; 
    password: string; 
    confirm_password: string; 
    role: string;
    class_code?: string;
    school_code?: string;
  }) {
    const { external_id, username, password, confirm_password, role, class_code, school_code } = values;
    
    if (!external_id || !username || !password || !confirm_password || !role) {
      message.error("请填写所有必填字段");
      return;
    }

    if (password !== confirm_password) {
      message.error("密码和确认密码不一致");
      return;
    }

    setRegisterLoading(true);
    try {
      const resp = await api.post("/mcp/auth/register", {
        external_id,
        username,
        password,
        confirm_password,
        role,
        class_code,
        school_code
      });
      
      if (resp.data?.status !== "success") {
        message.error(resp.data?.detail || "注册失败");
        setRegisterLoading(false);
        return;
      }

      message.success("注册成功，请使用新账号登录");
      registerForm.resetFields();
      // 切换到登录标签页
      const tabs = document.querySelector('.ant-tabs-tab') as HTMLElement;
      if (tabs) {
        const loginTab = tabs.querySelector('[data-node-key="login"]') as HTMLElement;
        if (loginTab) loginTab.click();
      }
    } catch (err: unknown) {
      console.error("register error", err);
      let errorMessage = "注册请求失败";
      if (err instanceof Error) {
        errorMessage = err.message;
      }
      message.error("注册失败: " + errorMessage);
    } finally {
      setRegisterLoading(false);
    }
  }

  const clearLocalStorage = () => {
    localStorage.removeItem("userId");
    localStorage.removeItem("external_id");
    localStorage.removeItem("username");
    localStorage.removeItem("role");
    localStorage.removeItem("class_id");
    localStorage.removeItem("managed_class_id");
    form.setFieldsValue({ external_id: "", password: "" });
    message.info("本地存储已清除");
  };

  const tabItems = [
    {
      key: 'login',
      label: '登录',
      children: (
        <Form
          form={form}
          onFinish={doLogin}
          layout="vertical"
        >
          <Form.Item
            label="账号 (external_id)"
            name="external_id"
            rules={[{ required: true, message: "请输入账号!" }]}
          >
            <Input placeholder="请输入您的学号/工号" />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码!" }]}
          >
            <Input.Password placeholder="请输入密码" />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'center' }}>
              <Button 
                type="primary" 
                htmlType="submit" 
                loading={loading}
                onClick={() => {
                  console.log("登录按钮被点击");
                  if (window.cordova || window.Capacitor) {
                    alert("登录按钮被点击");
                  }
                }}
              >
                登录
              </Button>
              <Button type="default" onClick={clearLocalStorage}>
                清除本地
              </Button>
            </Space>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'register',
      label: '注册',
      children: (
        <Form
          form={registerForm}
          onFinish={doRegister}
          layout="vertical"
        >
          <Form.Item
            label="账号 (external_id)"
            name="external_id"
            rules={[{ required: true, message: "请输入账号!" }]}
          >
            <Input placeholder="请输入学号/工号" />
          </Form.Item>

          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名!" }]}
          >
            <Input placeholder="请输入用户名" />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码!" }]}
          >
            <Input.Password placeholder="请输入密码" />
          </Form.Item>

          <Form.Item
            label="确认密码"
            name="confirm_password"
            rules={[{ required: true, message: "请确认密码!" }]}
          >
            <Input.Password placeholder="请再次输入密码" />
          </Form.Item>

          <Form.Item
            label="身份"
            name="role"
            rules={[{ required: true, message: "请选择身份!" }]}
          >
            <Select placeholder="请选择身份">
              <Option value="student">学生</Option>
              <Option value="teacher">教师</Option>
              <Option value="parent">家长</Option>
              <Option value="admin">管理员</Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="班级代号"
            name="class_code"
            help="学生、家长、教师需要填写班级代号"
          >
            <Input placeholder="请输入班级代号，如：202501" />
          </Form.Item>

          <Form.Item
            label="学校代号"
            name="school_code"
            help="所有用户都需要填写学校代号"
          >
            <Input placeholder="请输入学校代号，如：SCH001" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={registerLoading} style={{ width: '100%' }}>
              注册
            </Button>
          </Form.Item>
        </Form>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
      <Card className="login-card">
        <Title level={2} style={{ textAlign: 'center' }}>
          校园助手
        </Title>
        
        <Tabs defaultActiveKey="login" items={tabItems} />
      </Card>
    </div>
  );
}
