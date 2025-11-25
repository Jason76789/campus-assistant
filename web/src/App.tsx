import React, { useState } from "react";
import { Routes, Route, Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Layout, Menu, Breadcrumb, Button } from 'antd';
import "./AppLayout.css";
import Dashboard from "./components/Dashboard";
import Login from "./components/Login";
import NoticeComposer from "./components/NoticeComposer";
import PollSimulator from "./components/PollSimulator";
import OutgoingList from "./components/OutgoingList";
import SimpleChat from "./components/SimpleChat";
import Chatting from "./components/Chatting";
import MemoManager from "./components/MemoManager";
import OpenWindowsManager from "./components/OpenWindowsManager";
import GradeManager from "./components/GradeManager";
import OfflineStatus from "./components/OfflineStatus";
import ParentChildSelection from "./components/ParentChildSelection";

const { Header, Content, Footer, Sider } = Layout;

type Auth = {
  ok: boolean;
  requesterId?: string;
  role?: string;
  classId?: string;
  managedClassId?: string;
};

function requireAuth(): Auth {
  const requesterId = localStorage.getItem("userId") || undefined;
  const role = localStorage.getItem("role") || undefined;
  const classId = localStorage.getItem("class_id") || undefined;
  const managedClassId = localStorage.getItem("managed_class_id") || undefined;
  return { ok: !!requesterId, requesterId, role, classId, managedClassId };
}

function AppLayout({ children }: React.PropsWithChildren) {
  const auth = requireAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const menuItems = [
    { key: '/', label: <Link to="/">首页</Link> },
    { key: '/grades', label: <Link to="/grades">成绩管理</Link> },
    ...(auth.role === "admin" ? [
      { key: '/outgoing', label: <Link to="/outgoing">Outgoing</Link> },
      { key: '/memos', label: <Link to="/memos">Memos</Link> },
    ] : []),
    ...(auth.role === "student" ? [
      { key: '/memos', label: <Link to="/memos">备忘录</Link> },
    ] : []),
    ...(auth.role === "admin" || auth.role === "teacher" ? [
      { key: '/notice', label: <Link to="/notice">Notice</Link> },
      { key: '/open-windows', label: <Link to="/open-windows">Open Windows</Link> },
    ] : []),
    ...(auth.role === "student" ? [
      { key: '/poll', label: <Link to="/poll">Poll</Link> },
      { key: '/chat', label: <Link to="/chat">Chat</Link> },
    ] : []),
    ...(auth.role === "teacher" || auth.role === "parent" ? [
      { key: '/chatting', label: <Link to="/chatting">Chatting</Link> },
    ] : []),
  ];

  return (
    <Layout className="app-layout" style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        collapsedWidth="0"
      >
        <div className="logo" />
        <Menu theme="dark" selectedKeys={[location.pathname]} mode="inline" items={menuItems} />
      </Sider>
      <Layout>
        <Header>
          <span />
        </Header>
        <Content className="app-layout-content">
          <div className="breadcrumb-container">
            <Breadcrumb
              items={[
                { title: 'User' },
                { title: auth.requesterId || '未登录' }
              ]}
            />
            <Button type="link" onClick={() => {
              localStorage.clear();
              navigate("/login");
            }}>
              登出
            </Button>
          </div>
          <div className="site-layout-background">
            {children}
          </div>
        </Content>
        <Footer style={{ textAlign: 'center' }}>Campus Assistant ©2023</Footer>
      </Layout>
    </Layout>
  );
}

function Protected({ children }: React.PropsWithChildren) {
  const auth = requireAuth();
  const childrenWithProps = React.Children.map(children, child => {
    if (React.isValidElement(child)) {
      // @ts-expect-error - We are injecting props into the routed components.
      return React.cloneElement(child, { requesterId: auth.requesterId, role: auth.role, classId: auth.classId, managedClassId: auth.managedClassId });
    }
    return child;
  });
  return auth.ok ? <AppLayout>{childrenWithProps}</AppLayout> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      <OfflineStatus />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/parent/select-child" element={<ParentChildSelection />} />
        <Route path="/" element={<Protected><Dashboard /></Protected>} />
        <Route path="/grades" element={<Protected><GradeManager /></Protected>} />
        <Route path="/outgoing" element={<Protected><OutgoingList /></Protected>} />
        <Route path="/memos" element={<Protected><MemoManager /></Protected>} />
        <Route path="/notice" element={<Protected><NoticeComposer /></Protected>} />
        <Route path="/open-windows" element={
          <Protected>
            <OpenWindowsManager key={`open-windows-${requireAuth().requesterId}-${requireAuth().role}`} />
          </Protected>
        } />
        <Route path="/poll" element={<Protected><PollSimulator /></Protected>} />
        <Route path="/chat" element={<Protected><SimpleChat /></Protected>} />
        <Route path="/chatting" element={<Protected><Chatting /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
