import type {
  AuthResponse,
  DocumentDetail,
  DocumentSummary,
  PublicVerifyResult,
  SignatureItem,
  TotpSetupResponse,
  VerifyUploadResult,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let memoryCsrfToken = "";

export function setCsrfToken(token: string) {
  if (token) {
    memoryCsrfToken = token;
  }
}

export function getCsrfToken(): string {
  if (typeof document !== "undefined") {
    const match = document.cookie.match(/(?:^|;\s*)digsign_csrf_token=([^;]+)/);
    if (match && match[1]) {
      return decodeURIComponent(match[1]);
    }
  }
  return memoryCsrfToken;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});

  if (
    !(options.body instanceof FormData) &&
    options.body &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrf = getCsrfToken();
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : typeof body === "string" && body
        ? body
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }

  return body as T;
}

export const api = {
  // Auth
  async register(name: string, email: string, password: string) {
    const res = await apiFetch<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    setCsrfToken(res.csrf_token);
    return res;
  },
  async login(email: string, password: string, totp_code?: string) {
    const res = await apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        totp_code: totp_code || undefined,
      }),
    });
    setCsrfToken(res.csrf_token);
    return res;
  },
  async logout() {
    await apiFetch("/auth/logout", { method: "POST" });
    memoryCsrfToken = "";
  },
  async me() {
    const res = await apiFetch<AuthResponse>("/auth/me");
    setCsrfToken(res.csrf_token);
    return res;
  },
  async verifyEmail(token: string) {
    return apiFetch<{ message: string; email: string }>(
      `/auth/verify-email?token=${encodeURIComponent(token)}`
    );
  },
  async setup2FA() {
    return apiFetch<TotpSetupResponse>("/auth/2fa/setup", { method: "POST" });
  },
  async enable2FA(code: string) {
    return apiFetch<{ message: string }>("/auth/2fa/enable", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  },
  async disable2FA(code: string) {
    return apiFetch<{ message: string }>("/auth/2fa/disable", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
  },

  // Signatures
  async listSignatures() {
    return apiFetch<SignatureItem[]>("/signatures");
  },
  async createSignatureBase64(payload: {
    label: string;
    type: "draw" | "upload" | "type";
    image_base64: string;
    remove_background?: boolean;
  }) {
    return apiFetch<SignatureItem>("/signatures", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async createSignatureFile(
    file: File,
    label: string,
    removeBackground: boolean
  ) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("label", label);
    fd.append("type", "upload");
    fd.append("remove_background", String(removeBackground));
    return apiFetch<SignatureItem>("/signatures", {
      method: "POST",
      body: fd,
    });
  },
  async deleteSignature(id: string) {
    return apiFetch<void>(`/signatures/${id}`, { method: "DELETE" });
  },

  // Documents
  async listDocuments(statusFilter?: string) {
    const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
    return apiFetch<DocumentSummary[]>(`/documents${qs}`);
  },
  async uploadDocument(file: File, title?: string) {
    const fd = new FormData();
    fd.append("file", file);
    if (title) fd.append("title", title);
    return apiFetch<DocumentDetail>("/documents", {
      method: "POST",
      body: fd,
    });
  },
  async getDocument(id: string) {
    return apiFetch<DocumentDetail>(`/documents/${id}`);
  },
  async fetchDocumentPdfBytes(id: string): Promise<ArrayBuffer> {
    const res = await fetch(`${API_URL}/documents/${id}/download`, {
      credentials: "include",
    });
    if (!res.ok) {
      throw new ApiError(res.status, "Gagal memuat file PDF.");
    }
    return res.arrayBuffer();
  },
  getDownloadUrl(id: string) {
    return `${API_URL}/documents/${id}/download`;
  },
  async signDocument(
    id: string,
    payload: {
      signature_id: string;
      page: number;
      x: number;
      y: number;
      w: number;
      h: number;
      all_pages: boolean;
      signer_title?: string;
      signer_display_name?: string;
    }
  ) {
    return apiFetch<DocumentDetail>(`/documents/${id}/sign`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async inviteSigners(
    id: string,
    signers: Array<{ email: string; name?: string; order_no: number }>
  ) {
    return apiFetch<DocumentDetail>(`/documents/${id}/invite`, {
      method: "POST",
      body: JSON.stringify({ signers }),
    });
  },
  async resolveInvite(token: string) {
    return apiFetch<{
      document_id: string;
      order_no: number;
      status: string;
      message: string;
    }>(`/documents/invite/${encodeURIComponent(token)}`);
  },
  async revokeDocument(id: string, reason?: string) {
    return apiFetch<DocumentDetail>(`/documents/${id}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || "Dicabut oleh pemilik dokumen" }),
    });
  },

  // Public Verification
  async verifyToken(token: string) {
    return apiFetch<PublicVerifyResult>(
      `/verify/${encodeURIComponent(token)}`
    );
  },
  async verifyUpload(file: File, token?: string) {
    const fd = new FormData();
    fd.append("file", file);
    if (token) fd.append("token", token);
    return apiFetch<VerifyUploadResult>("/verify/upload", {
      method: "POST",
      body: fd,
    });
  },
};
