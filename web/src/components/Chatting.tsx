import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message, Avatar, List } from "antd";
import { SendOutlined, UserOutlined } from "@ant-design/icons";
import api from "../api";
import "./Chatting.css";

const { Title, Text } = Typography;
const { TextArea } = Input;

type Message = {
  id: number;
  sender_id: number;
  sender_name: string;
  content: string;
  timestamp: string;
  is_own?: boolean;
};

type Contact = {
  id: number;
  name: string;
  role: string;
};

type ChatSession = {
  contact: Contact;
  messages: Message[];
};

export default function Chatting() {
  const userId = localStorage.getItem("userId") ?? "";
  const role = localStorage.getItem("role") ?? "";
  const [loading, setLoading] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [chatSessions, setChatSessions] = useState<Record<number, ChatSession>>({});
  const [form] = Form.useForm();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatSessions, selectedContact]);

  useEffect(() => {
    if (userId) {
      fetchContacts();
      startPolling();
    }
    return () => {
      // 清理轮询
    };
  }, [userId]);

  // 轮询获取新消息
  const startPolling = () => {
    const pollInterval = setInterval(() => {
      if (userId) {
        fetchMessages();
      }
    }, 3000); // 每3秒轮询一次

    return () => clearInterval(pollInterval);
  };

  async function fetchContacts() {
    setLoading(true);
    try {
      const resp = await api.get<{ status: string; contacts: Contact[] }>("/mcp/contacts", {
        params: { user_id: userId },
      });
      if (resp.data?.status === "success") {
        const filteredContacts = resp.data.contacts || [];
        setContacts(filteredContacts);
        
        // 初始化聊天会话
        const sessions: Record<number, ChatSession> = {};
        filteredContacts.forEach(contact => {
          sessions[contact.id] = {
            contact,
            messages: []
          };
        });
        setChatSessions(sessions);
      } else {
        message.error("获取联系人列表失败");
      }
    } catch (err) {
      console.error(err);
      message.error("请求联系人列表错误");
    } finally {
      setLoading(false);
    }
  }

  async function fetchMessages() {
    if (!userId) return;

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
        const newMessages = resp.data.messages || [];
        
        // 更新所有聊天会话的消息
        setChatSessions(prevSessions => {
          const updatedSessions = { ...prevSessions };
          
          newMessages.forEach(message => {
            const contactId = message.sender_id;
            if (updatedSessions[contactId]) {
              // 标记消息是否为自己发送
              const messageWithOwnFlag = {
                ...message,
                is_own: message.sender_id === parseInt(userId)
              };
              
              // 避免重复消息
              const existingMessageIds = new Set(updatedSessions[contactId].messages.map(m => m.id));
              if (!existingMessageIds.has(messageWithOwnFlag.id)) {
                updatedSessions[contactId].messages = [
                  ...updatedSessions[contactId].messages,
                  messageWithOwnFlag
                ].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
              }
            }
          });
          
          return updatedSessions;
        });
      }
    } catch (err) {
      console.error("获取消息错误:", err);
    }
  }

  async function sendMessage(values: { content: string }) {
    const { content } = values;
    if (!userId || !selectedContact) {
      message.error("请先选择联系人");
      return;
    }
    if (!content.trim()) {
      message.error("请输入消息内容");
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
          receiver_id: String(selectedContact.id),
          content: content,
          priority: "normal",
        },
      };
      const resp = await api.post<{ status: string; message_id?: number; detail?: string }>("/mcp/command", body);
      
      if (resp.data?.status === "success") {
        // 立即在本地添加发送的消息
        const newMessage: Message = {
          id: resp.data.message_id || Date.now(),
          sender_id: parseInt(userId),
          sender_name: "我",
          content: content,
          timestamp: new Date().toISOString(),
          is_own: true
        };

        setChatSessions(prev => ({
          ...prev,
          [selectedContact.id]: {
            ...prev[selectedContact.id],
            messages: [...prev[selectedContact.id].messages, newMessage]
          }
        }));

        message.success("消息发送成功");
        form.resetFields();
      } else {
        message.error("发送失败: " + JSON.stringify(resp.data?.detail || resp.data));
      }
    } catch (err) {
      console.error(err);
      message.error("发送消息错误");
    } finally {
      setLoading(false);
    }
  }

  const handleContactSelect = (contactId: number) => {
    const contact = contacts.find(c => c.id === contactId) || null;
    setSelectedContact(contact);
  };

  const currentMessages = selectedContact ? chatSessions[selectedContact.id]?.messages || [] : [];

  return (
    <div className="chat-container">
      <Link to="/">
        <Button type="primary" style={{ marginBottom: "24px" }}>返回主页</Button>
      </Link>
      
      <Card className="chat-card">
        <Title level={2}>Chatting</Title>
        <Text>
          当前用户: <strong>{userId}</strong> (角色: <strong>{role}</strong>)
        </Text>

        <div className="chat-main">
          {/* 联系人列表 */}
          <Card title="联系人" className="contacts-card">
            <List
              dataSource={contacts}
              renderItem={contact => (
                <List.Item 
                  style={{ 
                    cursor: "pointer", 
                    backgroundColor: selectedContact?.id === contact.id ? "#e6f7ff" : "transparent",
                    padding: "8px",
                    borderRadius: "4px"
                  }}
                  onClick={() => handleContactSelect(contact.id)}
                >
                  <List.Item.Meta
                    avatar={<Avatar icon={<UserOutlined />} />}
                    title={contact.name}
                    description={contact.role}
                  />
                </List.Item>
              )}
            />
          </Card>

          {/* 聊天区域 */}
          <Card 
            title={selectedContact ? `与 ${selectedContact.name} 的对话` : "选择联系人开始聊天"} 
            className="chat-area-card"
          >
            {selectedContact ? (
              <>
                {/* 消息列表 */}
                <div className="messages-list">
                  <List
                    dataSource={currentMessages}
                    renderItem={message => (
                      <List.Item style={{ border: "none", padding: "8px 0" }}>
                        <div style={{ 
                          display: "flex", 
                          justifyContent: message.is_own ? "flex-end" : "flex-start",
                          width: "100%"
                        }}>
                          <div style={{
                            maxWidth: "70%",
                            padding: "8px 12px",
                            borderRadius: "8px",
                            backgroundColor: message.is_own ? "#1890ff" : "#f5f5f5",
                            color: message.is_own ? "white" : "black"
                          }}>
                            <div style={{ fontSize: "12px", opacity: 0.7 }}>
                              {message.sender_name}
                            </div>
                            <div>{message.content}</div>
                            <div style={{ fontSize: "10px", opacity: 0.6, textAlign: "right" }}>
                              {new Date(message.timestamp).toLocaleTimeString()}
                            </div>
                          </div>
                        </div>
                      </List.Item>
                    )}
                  />
                  <div ref={messagesEndRef} />
                </div>

                {/* 消息输入框 */}
                <Form form={form} onFinish={sendMessage} className="message-input-form">
                  <Form.Item name="content">
                    <TextArea 
                      rows={3} 
                      placeholder="输入消息..." 
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          form.submit();
                        }
                      }}
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button 
                      type="primary" 
                      htmlType="submit" 
                      loading={loading}
                      icon={<SendOutlined />}
                    >
                      发送
                    </Button>
                  </Form.Item>
                </Form>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "40px", color: "#999" }}>
                请从左侧选择联系人开始聊天
              </div>
            )}
          </Card>
        </div>
      </Card>
    </div>
  );
}
