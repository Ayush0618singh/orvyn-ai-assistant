import {
  API_URL,
  parseApiError,
} from "@/services/api";

import type {
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  User,
} from "@/types/auth";


export async function registerUser(
  payload: RegisterPayload
): Promise<User> {
  const response = await fetch(
    `${API_URL}/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      credentials: "include",
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function loginUser(
  payload: LoginPayload
): Promise<LoginResponse> {
  const response = await fetch(
    `${API_URL}/auth/login`,
    {
      method: "POST",
      headers: {
        "Content-Type":
          "application/json",
      },
      credentials: "include",
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function getCurrentUser(): Promise<User> {
  const response = await fetch(
    `${API_URL}/auth/me`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(
      await parseApiError(response)
    );
  }

  return response.json();
}


export async function logoutUser(): Promise<void> {
  const response = await fetch(
    `${API_URL}/auth/logout`,
    {
      method: "POST",
      credentials: "include",
    }
  );

  if (
    !response.ok &&
    response.status !== 204
  ) {
    throw new Error(
      await parseApiError(response)
    );
  }
}