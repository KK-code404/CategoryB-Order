import { afterEach, describe, expect, it, vi } from 'vitest'
import { authApi, dataApi } from './client'

afterEach(() => {
  vi.unstubAllGlobals()
})
describe('existing API contract', () => {
  it('keeps cookie authentication and the login payload', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 1 })))
    vi.stubGlobal('fetch', fetchMock)
    await authApi.login('test-admin', 'test-only-password')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
        body: JSON.stringify({ email: 'test-admin', password: 'test-only-password' }),
      }),
    )
  })
  it('sends native multipart uploads without a JSON content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: 'test-token' })))
    vi.stubGlobal('fetch', fetchMock)
    await dataApi.previewOrderImport(new File(['test'], 'orders.xlsx'))
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/orders/import/preview',
      expect.objectContaining({ body: expect.any(FormData), headers: undefined, credentials: 'include' }),
    )
  })
  it('clears expired sessions on protected endpoints, not a rejected login', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ detail: '未登录' }), { status: 401 }))),
    )
    const expired = vi.fn()
    window.addEventListener('auth-expired', expired)
    try {
      await expect(authApi.login('test', 'test')).rejects.toThrow('未登录')
      await expect(authApi.me()).rejects.toThrow('未登录')
      expect(expired).not.toHaveBeenCalled()
      await expect(dataApi.orders()).rejects.toThrow('未登录')
      expect(expired).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener('auth-expired', expired)
    }
  })
  it('normalizes backend validation errors and accepts no-content responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: [{ loc: ['body', 'quantity'], msg: 'must be positive' }] }), {
            status: 422,
          }),
        )
        .mockResolvedValueOnce(new Response(null, { status: 204 })),
    )
    await expect(dataApi.updateLine(1, { quantity: -1 })).rejects.toThrow('quantity：must be positive')
    await expect(authApi.logout()).resolves.toBeUndefined()
  })
})
