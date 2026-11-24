/** 市场 —— 市场状态、列表、详情与版本。 */

export interface MarketState {
  baseUrl: string;
  consentVersion: number;
  requiredVersion: number;
  accepted: boolean;
}

export interface MarketItem {
  id: string;
  name: string;
  summary: string;
  author: string;
  tags: string[];
  coverUrl?: string | null;
  latestVersion: string;
  sdkVersion: string;
  sizeBytes: number;
  sha256: string;
  downloadUrl: string;
  updatedAt: string;
  downloads: number;
  downloads7Days: number;
  downloads30Days: number;
  featured: boolean;
  platforms: string[];
}

export interface MarketListResult {
  ok: boolean;
  error?: string;
  total?: number;
  page?: number;
  pageSize?: number;
  tags?: string[];
  items?: MarketItem[];
}

export interface MarketVersion {
  version: string;
  downloadUrl: string;
  sourceUrl?: string;
  hosted?: boolean;
  sha256?: string;
  sizeBytes?: number;
  sdkVersion?: string;
  permissions?: number;
  changelog?: string;
  publishedAt?: string;
  downloads?: number;
}

export interface MarketDetail {
  id: string;
  name: string;
  summary: string;
  description: string;
  author: string;
  tags: string[];
  repositoryUrl?: string;
  license?: string;
  readme?: string;
  coverUrl?: string | null;
  featured?: boolean;
  createdAt?: string;
  updatedAt?: string;
  latestVersion?: string;
  downloads?: number;
  versions?: MarketVersion[];
}

export interface MarketDetailResult {
  ok: boolean;
  error?: string;
  detail?: MarketDetail;
}
