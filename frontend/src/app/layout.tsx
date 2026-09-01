import type { Metadata } from "next";

import { AuthProvider } from "@/contexts/AuthContext";

import "./globals.css";


export const metadata: Metadata = {
  title: "ORVYN",
  description:
    "Personal Multilingual Agentic AI Assistant",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}