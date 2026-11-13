/**
 * Componentes para gerenciamento de Funcionários
 * apps/web/src/features/employees/components/
 */

import React, { useState, useEffect } from "react";
import { Upload, Download, Trash2, Eye, Plus, ChevronDown } from "lucide-react";
import { Employee, EmployeeDocument, EmployeeListItem, EmployeeFormData } from "../types";

// ============================================================================
// EmployeeForm.tsx - Formulário de cadastro/edição
// ============================================================================

interface EmployeeFormProps {
  employee?: Employee;
  onSubmit: (data: EmployeeFormData) => Promise<void>;
  isLoading?: boolean;
}

export const EmployeeForm: React.FC<EmployeeFormProps> = ({
  employee,
  onSubmit,
  isLoading = false,
}) => {
  const [formData, setFormData] = useState<EmployeeFormData>({
    company_code: "universo_eletronica",
    full_name: "",
    document: "",
    department: "",
    position: "",
    salary_base: 0,
    hiring_date: new Date().toISOString().split("T")[0],
    ...employee,
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "salary_base" ? parseFloat(value) : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
      {/* Dados Pessoais */}
      <fieldset className="border rounded p-4">
        <legend className="font-bold text-lg">Dados Pessoais</legend>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <input
            type="text"
            name="full_name"
            placeholder="Nome Completo *"
            value={formData.full_name}
            onChange={handleChange}
            required
            className="px-3 py-2 border rounded col-span-2"
          />

          <input
            type="text"
            name="document"
            placeholder="CPF (11 dígitos) *"
            value={formData.document}
            onChange={handleChange}
            required
            className="px-3 py-2 border rounded"
          />

          <input
            type="date"
            name="date_birth"
            value={formData.date_birth || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
            placeholder="Data Nascimento"
          />

          <input
            type="email"
            name="email"
            placeholder="Email"
            value={formData.email || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded col-span-2"
          />

          <input
            type="tel"
            name="phone"
            placeholder="Telefone"
            value={formData.phone || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
          />

          <input
            type="tel"
            name="whatsapp"
            placeholder="WhatsApp"
            value={formData.whatsapp || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
          />
        </div>
      </fieldset>

      {/* Dados Profissionais */}
      <fieldset className="border rounded p-4">
        <legend className="font-bold text-lg">Dados Profissionais</legend>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <input
            type="text"
            name="department"
            placeholder="Departamento *"
            value={formData.department}
            onChange={handleChange}
            required
            className="px-3 py-2 border rounded"
          />

          <input
            type="text"
            name="position"
            placeholder="Cargo *"
            value={formData.position}
            onChange={handleChange}
            required
            className="px-3 py-2 border rounded"
          />

          <input
            type="number"
            name="salary_base"
            placeholder="Salário Base *"
            value={formData.salary_base}
            onChange={handleChange}
            step="0.01"
            required
            className="px-3 py-2 border rounded"
          />

          <select
            name="employment_type"
            value={formData.employment_type || "clt"}
            onChange={handleChange}
            className="px-3 py-2 border rounded"
          >
            <option value="clt">CLT</option>
            <option value="pj">PJ</option>
            <option value="trainee">Trainee</option>
          </select>

          <input
            type="date"
            name="hiring_date"
            placeholder="Data Contratação *"
            value={formData.hiring_date}
            onChange={handleChange}
            required
            className="px-3 py-2 border rounded"
          />
        </div>
      </fieldset>

      {/* Dados Bancários */}
      <fieldset className="border rounded p-4">
        <legend className="font-bold text-lg">Dados Bancários</legend>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <input
            type="text"
            name="bank_name"
            placeholder="Banco"
            value={formData.bank_name || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded col-span-2"
          />

          <input
            type="text"
            name="pix_key"
            placeholder="Chave PIX"
            value={formData.pix_key || ""}
            onChange={handleChange}
            className="px-3 py-2 border rounded col-span-2"
          />
        </div>
      </fieldset>

      {/* Botões */}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isLoading}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Salvando..." : "Salvar"}
        </button>
        <button
          type="reset"
          className="bg-gray-300 text-gray-800 px-4 py-2 rounded hover:bg-gray-400"
        >
          Limpar
        </button>
      </div>
    </form>
  );
};

// ============================================================================
// EmployeeList.tsx - Listagem de funcionários
// ============================================================================

interface EmployeeListProps {
  employees: EmployeeListItem[];
  loading: boolean;
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  onSelectEmployee: (employee: EmployeeListItem) => void;
  onDelete?: (employee_id: number) => Promise<void>;
}

export const EmployeeList: React.FC<EmployeeListProps> = ({
  employees,
  loading,
  total,
  limit,
  offset,
  onPageChange,
  onSelectEmployee,
  onDelete,
}) => {
  const pageCount = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  if (loading) {
    return <div className="text-center py-8">Carregando...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="text-left p-3 border">Nome</th>
              <th className="text-left p-3 border">CPF</th>
              <th className="text-left p-3 border">Email</th>
              <th className="text-left p-3 border">Cargo</th>
              <th className="text-right p-3 border">Salário</th>
              <th className="text-center p-3 border">Status</th>
              <th className="text-center p-3 border">Ações</th>
            </tr>
          </thead>
          <tbody>
            {employees.map((emp) => (
              <tr key={emp.id} className="border-b hover:bg-gray-50">
                <td className="p-3">{emp.full_name}</td>
                <td className="p-3 font-mono text-sm">{emp.document}</td>
                <td className="p-3">{emp.email || "-"}</td>
                <td className="p-3">{emp.position}</td>
                <td className="p-3 text-right font-mono">
                  R$ {emp.salary_base.toFixed(2)}
                </td>
                <td className="p-3 text-center">
                  <span
                    className={`px-2 py-1 rounded text-sm ${
                      emp.is_active
                        ? "bg-green-100 text-green-700"
                        : "bg-red-100 text-red-700"
                    }`}
                  >
                    {emp.is_active ? "Ativo" : "Inativo"}
                  </span>
                </td>
                <td className="p-3 text-center space-x-2">
                  <button
                    onClick={() => onSelectEmployee(emp)}
                    className="text-blue-600 hover:text-blue-800"
                    title="Visualizar"
                  >
                    <Eye size={18} />
                  </button>
                  {onDelete && (
                    <button
                      onClick={() => onDelete(emp.id)}
                      className="text-red-600 hover:text-red-800"
                      title="Deletar"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      <div className="flex justify-between items-center">
        <div className="text-sm text-gray-600">
          Mostrando {offset + 1} a {Math.min(offset + limit, total)} de {total}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-3 py-1 border rounded disabled:opacity-50"
          >
            ← Anterior
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: pageCount }).map((_, i) => (
              <button
                key={i}
                onClick={() => onPageChange(i * limit)}
                className={`px-2 py-1 border rounded ${
                  i + 1 === currentPage ? "bg-blue-600 text-white" : ""
                }`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <button
            onClick={() =>
              onPageChange(Math.min(offset + limit, (pageCount - 1) * limit))
            }
            disabled={offset + limit >= total}
            className="px-3 py-1 border rounded disabled:opacity-50"
          >
            Próxima →
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// DocumentUpload.tsx - Upload de documentos
// ============================================================================

interface DocumentUploadProps {
  employeeId: number;
  onSuccess: (doc: any) => void;
  isLoading?: boolean;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({
  employeeId,
  onSuccess,
  isLoading = false,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("contracheque");
  const [isPublic, setIsPublic] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    formData.append("is_public", isPublic.toString());

    try {
      const response = await fetch(
        `/api/employees/${employeeId}/documents?document_type=${documentType}&is_public=${isPublic}`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (response.ok) {
        const data = await response.json();
        onSuccess(data);
        setFile(null);
      }
    } catch (error) {
      console.error("Erro ao enviar:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border rounded p-4">
      <div>
        <label className="block text-sm font-bold mb-2">Tipo de Documento</label>
        <select
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          className="px-3 py-2 border rounded w-full"
        >
          <option value="contracheque">Contracheque</option>
          <option value="cnh">CNH</option>
          <option value="rg">RG</option>
          <option value="certificate">Certificado</option>
          <option value="aso">ASO</option>
          <option value="training">Treinamento</option>
          <option value="contract">Contrato</option>
          <option value="other">Outro</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-bold mb-2">Arquivo</label>
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="px-3 py-2 border rounded w-full"
          required
        />
        {file && <p className="text-sm text-gray-600 mt-1">{file.name}</p>}
      </div>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={isPublic}
          onChange={(e) => setIsPublic(e.target.checked)}
          className="rounded"
        />
        <span className="text-sm">Funcionário pode visualizar?</span>
      </label>

      <button
        type="submit"
        disabled={!file || isLoading}
        className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50"
      >
        <Upload size={18} />
        {isLoading ? "Enviando..." : "Enviar"}
      </button>
    </form>
  );
};

// ============================================================================
// EmployeeDocuments.tsx - Lista de documentos do funcionário
// ============================================================================

interface EmployeeDocumentsProps {
  documents: EmployeeDocument[];
  loading: boolean;
  onDownload: (documentId: number) => Promise<void>;
  onDelete?: (documentId: number) => Promise<void>;
}

export const EmployeeDocuments: React.FC<EmployeeDocumentsProps> = ({
  documents,
  loading,
  onDownload,
  onDelete,
}) => {
  if (loading) {
    return <div className="text-center py-4">Carregando documentos...</div>;
  }

  if (documents.length === 0) {
    return <div className="text-center py-4 text-gray-500">Nenhum documento</div>;
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex justify-between items-center p-3 border rounded hover:bg-gray-50"
        >
          <div className="flex-1">
            <p className="font-bold">{doc.original_name}</p>
            <p className="text-sm text-gray-600">
              {doc.document_type} • {(doc.file_size / 1024).toFixed(1)} KB •{" "}
              {new Date(doc.created_at).toLocaleDateString("pt-BR")}
            </p>
            {doc.expiration_date && (
              <p className="text-xs text-orange-600">
                Expira em: {new Date(doc.expiration_date).toLocaleDateString("pt-BR")}
              </p>
            )}
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => onDownload(doc.id)}
              className="text-blue-600 hover:text-blue-800"
              title="Baixar"
            >
              <Download size={18} />
            </button>
            {onDelete && (
              <button
                onClick={() => onDelete(doc.id)}
                className="text-red-600 hover:text-red-800"
                title="Deletar"
              >
                <Trash2 size={18} />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
