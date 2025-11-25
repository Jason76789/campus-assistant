import UserProfile from "./UserProfile";

type Props = {
  requesterId?: string | undefined;
  role?: string | undefined;
  classId?: string | undefined;
};

export default function Dashboard({ requesterId, role }: Props) {
  if (!requesterId || !role) return null;

  return (
    <div style={{ padding: "24px", background: "#f0f2f5" }}>
      <UserProfile requesterId={requesterId} role={role} />
    </div>
  );
}
