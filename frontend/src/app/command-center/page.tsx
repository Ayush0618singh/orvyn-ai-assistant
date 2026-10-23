
import type { Metadata } from "next";

import OrvynCommandCenter from "./OrvynCommandCenter";

export const metadata: Metadata = {
  title: "ORVYN | AI Command Center",
  description:
    "ORVYN secure multilingual agentic AI command center.",
};

export default function CommandCenterPage() {
  return <OrvynCommandCenter />;
}
