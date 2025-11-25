// src/types/api.ts

export type ApiResp = {
  status: "success" | "error";
  detail?: string;
  
  // Dashboard stats
  pending_outgoing?: number;
  unconfirmed_memos?: number;
  daily_quote?: {
    total_active?: number;
    scheduled_now?: {
      id: number;
      class_id: string;
      broadcast_time: string;
    }[];
    enqueued_today?: number;
  };
  
  // Other possible fields
  [key: string]: unknown;
  user_profile?: UserProfile;
};

export interface UserProfile {
  name: string;
  external_id?: string; // 学号/工号
  class_name?: string;
  school_name?: string;
  enrollment_year?: string; // 入学年份, might not be available
}

export interface Memo {
  id: number;
  content: string;
  remind_date: string; // YYYY-MM-DD
  is_confirmed?: boolean; // 前端状态
}
