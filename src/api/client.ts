import type { ApiCourse, ApiEdit, ApiGraph, EdgeType } from './types'

export const API_URL: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

const KEY_STORAGE = 'qna-quest-admin-key'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getAdminKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? ''
  } catch {
    return ''
  }
}

export function setAdminKey(key: string) {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key)
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    // Storage can be blocked. The key then lasts only until the page reloads.
  }
}

/** FastAPI sends `detail` as a string, or as a list of validation problems. */
export function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((d) => (d as { msg?: string }).msg).filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  return fallback
}

async function request<T>(path: string, init: RequestInit = {}, admin = false): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (admin) headers['X-Admin-Key'] = getAdminKey()

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}. Is it running?`)
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, errorMessage(body, `Request failed (${response.status})`))
  }
  return (await response.json()) as T
}

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  courses: () => request<ApiCourse[]>('/courses'),
  graph: (courseId?: number) =>
    request<ApiGraph>(courseId === undefined ? '/graph' : `/graph?course_id=${courseId}`),

  // Everything below changes the graph, needs the admin key, and returns the resulting graph.
  accept: (edgeId: number) => request<ApiGraph>(`/admin/graph/edges/${edgeId}/accept`, post(), true),
  reject: (edgeId: number) => request<ApiGraph>(`/admin/graph/edges/${edgeId}/reject`, post(), true),
  retype: (edgeId: number, type: EdgeType) =>
    request<ApiGraph>(`/admin/graph/edges/${edgeId}`, { method: 'PATCH', body: JSON.stringify({ type }) }, true),
  deleteEdge: (edgeId: number) =>
    request<ApiGraph>(`/admin/graph/edges/${edgeId}`, { method: 'DELETE' }, true),
  addEdge: (srcNode: number, dstNode: number, type: EdgeType = 'required') =>
    request<ApiGraph>('/admin/graph/edges', post({ src_node: srcNode, dst_node: dstNode, type }), true),
  approve: (acceptRemaining: boolean) =>
    request<ApiGraph>('/admin/graph/approve', post({ accept_remaining: acceptRemaining }), true),
  edits: () => request<ApiEdit[]>('/admin/graph/edits', {}, true),
}
