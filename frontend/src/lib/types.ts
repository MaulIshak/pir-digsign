export interface User {
  id: string;
  name: string;
  email: string;
  is_verified: boolean;
  totp_enabled: boolean;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  csrf_token: string;
  message: string;
  dev_verify_link?: string | null;
}

export interface TotpSetupResponse {
  secret: string;
  otpauth_uri: string;
  qr_data_url: string;
}

export interface SignatureItem {
  id: string;
  label: string;
  type: "draw" | "upload" | "type";
  image_data_url?: string | null;
  created_at: string;
}

export interface DocumentSigner {
  id: string;
  email: string;
  signer_name?: string | null;
  order_no: number;
  status: "pending" | "signed" | "revoked";
  signed_at?: string | null;
  invite_link?: string | null;
}

export interface SignatureRecord {
  id: string;
  field_name: string;
  token: string;
  verify_url: string;
  page: number;
  all_pages: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  signer_name: string;
  signer_title?: string | null;
  doc_hash_after: string;
  signed_at: string;
  revoked_at?: string | null;
}

export interface EmbeddedPdfSignature {
  field_name: string;
  signer_cn?: string | null;
  signing_time?: string | null;
  intact: boolean;
  valid: boolean;
  summary: string;
}

export interface AuditLogItem {
  id: string;
  user_id?: string | null;
  action: string;
  ip?: string | null;
  user_agent?: string | null;
  doc_hash?: string | null;
  details?: string | null;
  created_at: string;
}

export interface DocumentSummary {
  id: string;
  owner_id: string;
  title: string;
  original_filename: string;
  status: "draft" | "pending" | "completed" | "revoked";
  current_hash: string;
  page_count: number;
  signature_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentSummary {
  is_owner: boolean;
  can_sign_now: boolean;
  cannot_sign_reason?: string | null;
  signers: DocumentSigner[];
  signature_records: SignatureRecord[];
  embedded_signatures: EmbeddedPdfSignature[];
  audit_logs: AuditLogItem[];
}

export interface PublicVerifyResult {
  status: "VALID" | "TIDAK VALID" | "DICABUT";
  message: string;
  token: string;
  document_title: string;
  signer_name: string;
  signer_title?: string | null;
  signed_at: string;
  revoked_at?: string | null;
  doc_hash_sha256: string;
  field_name: string;
  page: number;
  total_signatures_on_doc: number;
}

export interface VerifyUploadResult {
  status: "VALID" | "TIDAK VALID" | "DICABUT";
  message: string;
  uploaded_sha256: string;
  expected_sha256?: string | null;
  matched_record?: PublicVerifyResult | null;
  embedded_signatures: EmbeddedPdfSignature[];
}
