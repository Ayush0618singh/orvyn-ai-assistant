"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "@/services/authService";

import type {
  LoginPayload,
  RegisterPayload,
  User,
} from "@/types/auth";


interface AuthContextValue {
  user: User | null;
  loading: boolean;

  login: (
    payload: LoginPayload
  ) => Promise<void>;

  register: (
    payload: RegisterPayload
  ) => Promise<void>;

  logout: () => Promise<void>;

  refreshUser: () => Promise<void>;
}


const AuthContext =
  createContext<AuthContextValue | null>(
    null
  );


export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] =
    useState<User | null>(null);

  const [loading, setLoading] =
    useState(true);


  const refreshUser =
    useCallback(async () => {
      try {
        const currentUser =
          await getCurrentUser();

        setUser(currentUser);
      } catch {
        setUser(null);
      }
    }, []);


  useEffect(() => {
    async function initializeAuth() {
      try {
        await refreshUser();
      } finally {
        setLoading(false);
      }
    }

    initializeAuth();
  }, [refreshUser]);


  async function login(
    payload: LoginPayload
  ) {
    const result =
      await loginUser(payload);

    setUser(result.user);
  }


  async function register(
    payload: RegisterPayload
  ) {
    await registerUser(payload);

    const loginResult =
      await loginUser(payload);

    setUser(loginResult.user);
  }


  async function logout() {
    await logoutUser();

    setUser(null);
  }


  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}


export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider."
    );
  }

  return context;
}