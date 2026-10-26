import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, errorMessage } from './client'

describe('errorMessage', () => {
  it('reads a plain detail string', () => {
    expect(errorMessage({ detail: 'Cycle: a -> b -> a' }, 'fallback')).toBe('Cycle: a -> b -> a')
  })

  it('joins validation problems', () => {
    const body = { detail: [{ msg: 'Input should be required or optional' }, { msg: 'Field required' }] }
    expect(errorMessage(body, 'fallback')).toBe('Input should be required or optional; Field required')
  })

  it('falls back when there is nothing usable', () => {
    expect(errorMessage(null, 'fallback')).toBe('fallback')
    expect(errorMessage({ detail: [] }, 'fallback')).toBe('fallback')
    expect(errorMessage({}, 'fallback')).toBe('fallback')
  })
})

describe('request errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('turns a refused request into an ApiError carrying the status and the server message', async () => {
    vi.stubGlobal('localStorage', { getItem: () => 'k', setItem: () => {}, removeItem: () => {} })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: 'Cycle: x' }), { status: 409 })),
    )
    await expect(api.addEdge(1, 2)).rejects.toMatchObject({ status: 409, message: 'Cycle: x' })
  })

  it('says the backend is unreachable when fetch itself fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('failed'))))
    const error = await api.graph().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(0)
    expect((error as ApiError).message).toMatch(/Cannot reach the backend/)
  })

  it('sends the admin key only on admin calls', async () => {
    vi.stubGlobal('localStorage', { getItem: () => 'secret', setItem: () => {}, removeItem: () => {} })
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await api.graph()
    await api.accept(5)

    const headers = fetchMock.mock.calls.map((call) => (call as unknown as [string, RequestInit])[1].headers)
    expect(headers[0]).not.toHaveProperty('X-Admin-Key')
    expect(headers[1]).toMatchObject({ 'X-Admin-Key': 'secret' })
  })
})
