
"use client";

import AuthScreen from "@/components/auth/AuthScreen";
import OrvynHomeDashboard from "@/components/command-center/OrvynHomeDashboard";
import { useAuth } from "@/contexts/AuthContext";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#030916] text-cyan-100">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-2 border-cyan-400/20 border-t-cyan-300" />
          <p className="text-sm tracking-[0.25em]">INITIALIZING ORVYN</p>
          <p className="mt-2 text-xs text-slate-500">
            Checking secure session...
          </p>
        </div>
      </main>
    );
  }

  if (!user) {
    return <AuthScreen />;
  }

  return <OrvynHomeDashboard />;
}
