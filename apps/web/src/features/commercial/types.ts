export type CompanyCode = string;
export type CommercialPurpose = "rental_sale" | "preventive";
export type QuoteType = "sale" | "rental" | "preventive";

export type CustomerLite = {
  id: number; company_code: string; document: string | null; legal_name: string; trade_name: string | null;
  phone: string | null; email: string | null; city: string | null; state: string | null; is_active: boolean;
};

export type CommercialCompany = {
  id: number; company_code: CompanyCode; legal_name: string; trade_name: string | null; document: string | null;
  state_registration: string | null; email: string | null; phone: string | null; address: string | null; city: string | null;
  state: string | null; is_active: boolean; created_at: string; updated_at: string;
};

export type CommercialEquipment = {
  id: number; serial_code: string; patrimony_code: string; company_code: CompanyCode; purpose: CommercialPurpose; equipment_type: string;
  manufacturer: string | null; model: string | null; power: string | null; voltage: string | null; manufacturer_serial: string | null; quantity: number;
  unit_cost: number | null; sale_price: number | null; rental_daily_price: number | null; rental_monthly_price: number | null;
  condition: string | null; stock_status: string; rental_customer_id: number | null; location: string | null; asset_location_id: number | null; acquisition_date: string | null; notes: string | null;
  is_active: boolean; created_at: string; updated_at: string;
};

export type CommercialQuoteItem = {
  id?: number; equipment_id: number | null; description: string; manufacturer: string | null; model: string | null;
  power: string | null; voltage: string | null; serial_number: string | null; quantity: number; unit: string; unit_price: number | null;
  discount_pct: number; rental_period_count: number | null; rental_period_unit: string | null; line_total?: number | null; sort_order?: number;
};

export type CommercialQuote = {
  id: number; quote_number: string; quote_type: QuoteType; company_code: CompanyCode; customer_id: number; customer_name: string;
  revision: number; status: string; issue_date: string; valid_until: string | null; title: string | null; intro_text: string | null;
  notes: string | null; payment_terms: string | null; delivery_terms: string | null; warranty_terms: string | null;
  rental_terms: string | null; preventive_scope: string | null; exclusions: string | null; total: number | null;
  issued_at: string | null; created_at: string; updated_at: string; items: CommercialQuoteItem[];
};

export type PreventiveOrder = {
  id: number; order_number: string; quote_id: number | null; company_code: CompanyCode; customer_id: number; customer_name: string;
  status: string; scheduled_date: string | null; completed_date: string | null; technical_notes: string | null; created_at: string; updated_at: string;
};

export type CommercialAssetLocation = {
  id: number;
  area_id: number;
  rack_id: number | null;
  area_code: string;
  area_name: string;
  rack_code: string | null;
  rack_name: string | null;
  code: string;
  name: string;
  sort_order: number;
  is_active: boolean;
};

export type CommercialAssetLocationConfig = {
  areas: Array<{ id:number; code:string; name:string; sort_order:number; is_active:boolean }>;
  racks: Array<{
    id:number; area_id:number; area_code:string; area_name:string; code:string; name:string;
    position_prefix:string; rows:number; columns:number; layout_row:number; layout_column:number;
    layout_span:number; sort_order:number; is_active:boolean;
  }>;
  locations: CommercialAssetLocation[];
};

export type CommercialAssetMap = {
  total_positions: number;
  occupied_positions: number;
  free_positions: number;
  located_assets: number;
  assets_without_location: number;
  slots: Array<{
    location_id:number; location:string; area_code:string; area_name:string;
    rack_code:string|null; rack_name:string|null; rack_rows:number; rack_columns:number;
    rack_layout_row:number; rack_layout_column:number; rack_layout_span:number; slot_number:number;
    occupancy_count:number;
    occupants:Array<{
      equipment_id:number; patrimony_code:string; equipment_type:string;
      manufacturer:string|null; model:string|null; manufacturer_serial:string|null; stock_status:string;
    }>;
  }>;
};
