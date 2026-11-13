/**
 * Types para o módulo de Funcionários
 * apps/web/src/features/employees/types.ts
 */

export interface EmploymentHistory {
  id: number;
  employee_id: number;
  start_date: string; // YYYY-MM-DD
  end_date: string | null;
  department: string;
  position: string;
  salary: number;
  employment_type: "clt" | "pj" | "trainee";
  reason_end?: string;
  created_at: string;
}

export interface EmployeeDocument {
  id: number;
  employee_id: number;
  document_type: string;
  original_name: string;
  mime_type: string;
  file_size: number;
  version: number;
  metadata_period?: string; // "2026-08" para contracheques
  expiration_date?: string; // YYYY-MM-DD
  is_public: boolean;
  accessed_count: number;
  downloaded_count: number;
  last_accessed_at?: string;
  last_downloaded_at?: string;
  created_at: string;
}

export interface Employee {
  id: number;
  company_code: string;
  user_id?: number;
  full_name: string;
  document: string; // CPF
  document_type: "cpf" | "cnpj";
  date_birth?: string; // YYYY-MM-DD
  gender?: "M" | "F" | "O";
  nationality?: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  
  postal_code?: string;
  address?: string;
  address_number?: string;
  complement?: string;
  district?: string;
  city?: string;
  state?: string;
  
  department: string;
  position: string;
  salary_base: number;
  hiring_date: string; // YYYY-MM-DD
  termination_date?: string;
  employment_type: "clt" | "pj" | "trainee";
  
  bank_name?: string;
  pix_key?: string;
  
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmployeeDetail extends Employee {
  city?: string;
  state?: string;
  address?: string;
  postal_code?: string;
  pis?: string;
  ctps?: string;
  rg_number?: string;
  marital_status?: string;
  dependents: number;
  notes?: string;
  
  employment_history: EmploymentHistory[];
  documents: EmployeeDocument[];
}

export interface EmployeeListItem {
  id: number;
  full_name: string;
  document: string;
  email?: string;
  department: string;
  position: string;
  salary_base: number;
  hiring_date: string;
  termination_date?: string;
  is_active: boolean;
  created_at: string;
}

export interface EmployeeFormData {
  company_code: string;
  user_id?: number;
  full_name: string;
  document: string;
  document_type?: "cpf" | "cnpj";
  date_birth?: string;
  gender?: "M" | "F" | "O";
  email?: string;
  phone?: string;
  whatsapp?: string;
  
  postal_code?: string;
  address?: string;
  address_number?: string;
  complement?: string;
  district?: string;
  city?: string;
  state?: string;
  
  department: string;
  position: string;
  salary_base: number;
  hiring_date: string;
  employment_type?: "clt" | "pj" | "trainee";
  
  bank_name?: string;
  bank_account?: string;
  pix_key?: string;
  
  pis?: string;
  rg_number?: string;
  marital_status?: string;
  dependents?: number;
  notes?: string;
}

export interface EmployeeTerminateData {
  termination_date: string; // YYYY-MM-DD
  reason_end: string;
}

export interface EmployeeAuditEvent {
  id: number;
  employee_id?: number;
  document_id?: number;
  action: string;
  description: string;
  user_id: number;
  ip_address?: string;
  created_at: string;
}

export interface PaginatedEmployeesResponse {
  total: number;
  limit: number;
  offset: number;
  data: EmployeeListItem[];
}

export interface DocumentUploadResponse {
  id: number;
  employee_id: number;
  document_type: string;
  original_name: string;
  file_size: number;
  version: number;
  created_at: string;
}
