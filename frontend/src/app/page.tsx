"use client";

import AuthScreen from "@/components/auth/AuthScreen";
import ChatInterface from "@/components/chat/ChatInterface";
import { useAuth } from "@/contexts/AuthContext";


export default function Home() {
  const {
    user,
    loading,
  } = useAuth();


  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-950">
        <p className="text-sm text-gray-400">
          Loading ORVYN...
        </p>
      </main>
    );
  }


  if (!user) {
    return <AuthScreen />;
  }


  return <ChatInterface />;
}