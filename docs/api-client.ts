export type ProfileType = "as_served_reference" | "ingredient_recipe" | "unreviewed";
export interface Ingredient { id: number; name_vi: string; name_en: string | null; preparation_state: string }
export interface Portion { ingredient_id: number; grams: number }
export interface Recipe {
  recipe_id: number; food_id: number; food_name: string; recipe_name: string;
  default_serving_g: number | null; profile_type: ProfileType;
  components: (Portion & { name: string; is_optional: boolean })[];
}
export interface Prediction {
  taxonomy_version: string;
  predictions: { model_index: number; canonical_id: string; name_vi: string | null;
    name_en: string | null; display_name: string; score: number }[];
  requires_confirmation: boolean; score_type: string; nutrition_status: string;
}
export interface FoodLookup {
  canonical_id: string; mapped: boolean;
  food: { id: number; canonical_id: string; model_class_index: number | null;
    name_vi: string; name_en: string | null } | null;
  recipes: { id: number; name: string; default_serving_g: number | null; profile_type: ProfileType }[];
  nutrition_status: string;
}
export interface Calculation {
  recipe_id: number; food_id: number; food_name: string; recipe_name: string;
  is_customized: boolean; profile_type: ProfileType;
  nutrition: { total_grams: number; ingredients: { id: number; name: string; grams: number }[];
    nutrients: Record<string, { name: string; amount: number | null; unit: string;
      status: "complete" | "incomplete"; missing_ingredient_ids: number[] }> };
}
export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}
const base = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(base + path, init);
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body?.detail ?? response.statusText);
  return body as T;
}
export const api = {
  ingredients: () => request<Ingredient[]>("/ingredients"),
  predict: (file: File, topK = 3) => {
    const body = new FormData(); body.append("file", file);
    return request<Prediction>(`/predict?top_k=${topK}`, { method: "POST", body });
  },
  food: (canonicalId: string) => request<FoodLookup>(`/foods/by-canonical/${encodeURIComponent(canonicalId)}`),
  recipe: (id: number) => request<Recipe>(`/recipes/${id}`),
  calculate: (id: number, components: Portion[]) => request<Calculation>(`/recipes/${id}/calculate`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ components }),
  }),
};
