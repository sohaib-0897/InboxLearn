export interface StatusResponse {
  active_version: {
    id: number;
    label: string;
    kind: string;
    parent_id: number | null;
    created_at: string;
    training_mode: string;
    seed_count: number;
    feedback_count: number;
  };
  metrics: {
    emails_stored: number;
    pending_reviews: number;
    available_feedback: number;
    uncommitted_feedback: number;
    total_models: number;
  };
  candidate: {
    version_id: number;
    label: string;
    parent_id: number;
    mode: string;
    feedback_count: number;
    is_evaluated: boolean;
  } | null;
  thresholds: {
    category: number;
    priority: number;
  };
  datasets: {
    seed: number;
    validation: number;
    eval: number;
    eval_expanded: number;
  };
  categories: string[];
  priorities: string[];
}

export interface ExtractedEntity {
  type: string;
  value: string;
  raw_phrase: string;
  confidence: number;
}

export interface PredictRequest {
  subject: string;
  sender?: string;
  body: string;
  category_threshold?: number;
  priority_threshold?: number;
}

export interface PredictResponse {
  category: string;
  priority: string;
  category_confidence: number;
  priority_confidence: number;
  all_category_scores: Record<string, number>;
  all_priority_scores: Record<string, number>;
  status: 'classified' | 'needs_review';
  needs_review: boolean;
  routing_reason: string;
  suggested_action: string;
  latency_ms: number;
  model_version_id: number;
  model_label: string;
  feature_dimensions: number;
  extracted_entities: ExtractedEntity[];
  has_calendar_event: boolean;
}

export interface EmailRow {
  id: number;
  subject: string;
  sender: string;
  body: string;
  source: string;
  source_type: string;
  created_at: string;
  date_header?: string;
  predicted_category: string;
  predicted_priority: string;
  category_confidence: number;
  priority_confidence: number;
  model_version_id: number;
  status: 'classified' | 'needs_review' | 'corrected';
  effective_category: string;
  effective_priority: string;
  feedback_id?: number | null;
  suggested_action?: string;
  routing_reason?: string;
  entities?: ExtractedEntity[];
}

export interface ModelVersion {
  id: number;
  label: string;
  kind: string;
  parent_id: number | null;
  created_at: string;
  is_active: number | boolean;
  metadata: {
    description?: string;
    training_mode?: string;
    trained_feedback_count?: number;
    feedback_count?: number;
    seed_count?: number;
    random_state?: number;
    parent_version?: string;
    recipe_version?: string;
  };
  has_evaluation: boolean;
  evaluation_summary?: {
    category_accuracy: number;
    priority_accuracy: number;
  };
}

export interface DiffRow {
  id: number;
  subject: string;
  human_category?: string;
  human_priority?: string;
  before_category: string;
  after_category: string;
  before_priority: string;
  after_priority: string;
  before_category_confidence: number;
  after_category_confidence: number;
  before_priority_confidence: number;
  after_priority_confidence: number;
  before_training_member: boolean;
  after_training_member: boolean;
  category_changed: boolean;
  priority_changed: boolean;
  changed: boolean;
}

export interface DiffResponse {
  rows: DiffRow[];
  total: number;
  changed: number;
  category_changed: number;
  priority_changed: number;
}

export interface MetricBlock {
  category_accuracy: number;
  category_macro_f1: number;
  priority_accuracy: number;
  priority_macro_f1: number;
  confusion?: {
    category: {
      labels: string[];
      matrix: number[][];
    };
    priority: {
      labels: string[];
      matrix: number[][];
    };
  };
}

export interface EvaluationResponse {
  evaluation_id: number;
  baseline_version: string;
  updated_version: string;
  parent_version?: string;
  heldout_hash: string;
  note: string;
  baseline: MetricBlock;
  updated: MetricBlock;
  delta: {
    category_accuracy: number;
    category_macro_f1: number;
    priority_accuracy: number;
    priority_macro_f1: number;
  };
}

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = `Request failed: ${res.statusText}`;
    try {
      const err = await res.json();
      errorDetail = err.detail || err.message || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  getStatus: () => fetchJson<StatusResponse>('/status'),
  
  predict: (req: PredictRequest) => 
    fetchJson<PredictResponse>('/predict', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  getInbox: (params?: {
    include_confident?: boolean;
    order?: string;
    category?: string;
    priority?: string;
    unresolved?: boolean;
  }) => {
    const q = new URLSearchParams();
    if (params?.include_confident !== undefined) q.append('include_confident', String(params.include_confident));
    if (params?.order) q.append('order', params.order);
    if (params?.category) q.append('category', params.category);
    if (params?.priority) q.append('priority', params.priority);
    if (params?.unresolved) q.append('unresolved', String(params.unresolved));
    return fetchJson<{ total: number; rows: EmailRow[] }>(`/inbox?${q.toString()}`);
  },

  importDemo: (dataset = 'demo_feedback.csv') =>
    fetchJson<{ status: string; imported: number; duplicates: number }>(`/inbox/demo-import?dataset=${encodeURIComponent(dataset)}`, {
      method: 'POST',
    }),

  saveFeedback: (emailId: number, category: string, priority: string) =>
    fetchJson<{ status: string; feedback_id: number; is_revision: boolean; email_id: number }>('/feedback', {
      method: 'POST',
      body: JSON.stringify({ email_id: emailId, category, priority }),
    }),

  getModels: () => fetchJson<{ versions: ModelVersion[] }>('/models'),

  prepareCandidate: () =>
    fetchJson<{
      status: string;
      version_id?: number;
      parent_id?: number;
      mode?: string;
      feedback_count?: number;
      reused?: boolean;
      message: string;
    }>('/models/prepare', { method: 'POST' }),

  diffModels: (beforeId: number, afterId: number) =>
    fetchJson<DiffResponse>('/models/diff', {
      method: 'POST',
      body: JSON.stringify({ before_id: beforeId, after_id: afterId }),
    }),

  evaluateModel: (versionId?: number, datasetName = 'demo_eval.csv') =>
    fetchJson<EvaluationResponse>('/models/evaluate', {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId, dataset_name: datasetName }),
    }),

  activateModel: (versionId: number) =>
    fetchJson<{ status: string; active_version: ModelVersion }>('/models/activate', {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId }),
    }),

  rollbackModel: (versionId: number) =>
    fetchJson<{ status: string; rolled_back_to: ModelVersion }>('/models/rollback', {
      method: 'POST',
      body: JSON.stringify({ version_id: versionId }),
    }),

  getFollowUps: () => fetchJson<{ follow_ups: any[] }>('/actions/follow-ups'),
};
