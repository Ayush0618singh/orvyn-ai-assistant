import type { Metadata } from "next";

import ToolApprovalDashboard from
  "@/components/agent/ToolApprovalDashboard";

export const metadata: Metadata = {
  title: "Tool Approvals | ORVYN",
  description:
    "Review and manage secure agent tool approvals.",
};

export default function ToolApprovalsPage() {
  return <ToolApprovalDashboard />;
}