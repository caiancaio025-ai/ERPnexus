export type CompanyCode = "universo_eletronica" | "universo_automacao" | "solucoes_eletronica";
export type CommercialPurpose = "rental_sale" | "preventive";

export type CommercialEquipment = {
  id: number;
  serial_code: string;
  company_code: CompanyCode;
  purpose: CommercialPurpose;
  equipment_type: string;
  manufacturer: string | null;
  model: string | null;
  power: string | null;
  voltage: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
