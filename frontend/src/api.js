const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** Send JSON and consistently turn HTTP errors into readable messages. */
export async function request(path, { token, method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch {
    throw new Error('Cannot reach the API. Check that the backend is running on port 8000.')
  }
  if (response.status === 204) return null
  const data = await response.json()
  if (!response.ok) {
    const detail = data.detail
    throw new Error(typeof detail === 'string' ? detail : 'Please check your entries and try again.')
  }
  return data
}
