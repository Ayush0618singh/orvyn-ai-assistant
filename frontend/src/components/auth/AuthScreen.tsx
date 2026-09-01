"use client";

import {
  FormEvent,
  useState,
} from "react";

import { useAuth } from "@/contexts/AuthContext";


type AuthMode =
  | "login"
  | "register";


export default function AuthScreen() {
  const {
    login,
    register,
  } = useAuth();

  const [mode, setMode] =
    useState<AuthMode>("login");

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        await login({
          email,
          password,
        });
      } else {
        await register({
          email,
          password,
        });
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Authentication failed."
      );
    } finally {
      setLoading(false);
    }
  }


  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-950 px-6">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold tracking-tight text-white">
            ORVYN
          </h1>

          <p className="mt-3 text-sm text-gray-400">
            Personal Multilingual
            Agentic AI Assistant
          </p>
        </div>

        <div className="rounded-3xl border border-gray-800 bg-gray-900 p-7 shadow-2xl">
          <h2 className="text-xl font-semibold text-white">
            {mode === "login"
              ? "Welcome back"
              : "Create your account"}
          </h2>

          <p className="mt-1 text-sm text-gray-400">
            {mode === "login"
              ? "Sign in to continue to ORVYN."
              : "Create an account to start using ORVYN."}
          </p>

          <form
            onSubmit={handleSubmit}
            className="mt-7 space-y-5"
          >
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Email
              </label>

              <input
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(
                    event.target.value
                  )
                }
                required
                autoComplete="email"
                className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 text-sm text-white outline-none transition focus:border-gray-500"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Password
              </label>

              <input
                type="password"
                value={password}
                onChange={(event) =>
                  setPassword(
                    event.target.value
                  )
                }
                required
                minLength={8}
                autoComplete={
                  mode === "login"
                    ? "current-password"
                    : "new-password"
                }
                className="w-full rounded-xl border border-gray-700 bg-gray-950 px-4 py-3 text-sm text-white outline-none transition focus:border-gray-500"
                placeholder="Minimum 8 characters"
              />
            </div>

            {error && (
              <div className="rounded-xl border border-red-900 bg-red-950/50 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-white px-4 py-3 text-sm font-semibold text-gray-950 transition hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading
                ? "Please wait..."
                : mode === "login"
                ? "Sign in"
                : "Create account"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => {
              setMode(
                mode === "login"
                  ? "register"
                  : "login"
              );

              setError(null);
            }}
            className="mt-6 w-full text-center text-sm text-gray-400 hover:text-white"
          >
            {mode === "login"
              ? "Don't have an account? Create one"
              : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </main>
  );
}