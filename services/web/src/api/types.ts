/**
 * TypeScript API models derived directly from contracts/openapi/selene-v1.yaml.
 */

export interface ProductMetadata {
  id: string;
  org_id: string;
  project_id: string;
  kind: "slope" | "aspect" | "roughness" | "hazard" | "hazard_mask";
  storage_uri: string;
  sha256: string;
  size_bytes: number;
  dimensions: {
    width: number;
    height: number;
  };
  resolution_m: number;
  crs_wkt: string;
  parent_dataset_version_id: string;
  parameters: Record<string, unknown>;
  created_at: string;
}

export interface ProductStats {
  id: string;
  kind: string;
  stats: {
    min?: number | null;
    max?: number | null;
    mean?: number | null;
    std?: number | null;
    percentiles?: {
      p10?: number;
      p25?: number;
      p50?: number;
      p75?: number;
      p90?: number;
    };
    hazard_fraction?: number;
    safe_fraction?: number;
    total_pixels: number;
    valid_pixels: number;
    nodata_pixels?: number;
  };
}

export interface ProjectRecord {
  id: string;
  name: string;
  slug: string;
  description: string;
  created_at: string;
}

export interface VerifyResult {
  valid: boolean;
  artifact_id: string;
  registered_sha256?: string;
  actual_sha256?: string;
  reason?: string;
}
