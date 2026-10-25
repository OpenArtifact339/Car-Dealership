import { useCallback, useEffect, useState } from 'react'
import { request } from './api'

const emptyCar = { make: '', model: '', category: 'Sedan', price: '', quantity: 0 }
const inputStyle = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm focus:border-blue-500'
const primaryStyle = 'rounded-xl bg-blue-700 px-5 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-800 disabled:bg-slate-300'

function Auth({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      // Register first, then log in to obtain a usable bearer token.
      if (mode === 'register') await request('/api/auth/register', { method: 'POST', body: { email, password } })
      const session = await request('/api/auth/login', { method: 'POST', body: { email, password } })
      onLogin(session)
    } catch (problem) { setError(problem.message) }
    finally { setBusy(false) }
  }

  return <div className="mx-auto flex min-h-screen max-w-6xl items-center px-5 py-12">
    <div className="grid w-full overflow-hidden rounded-3xl bg-white shadow-xl md:grid-cols-2">
      <div className="flex min-h-80 flex-col justify-between bg-slate-900 p-9 text-white md:p-12">
        <div className="text-lg font-black tracking-wide">DRIVELINE <span className="text-blue-400">/</span> INVENTORY</div>
        <div><p className="mb-3 text-sm font-bold uppercase tracking-[0.2em] text-blue-300">Your next drive starts here</p>
          <h1 className="text-4xl font-black leading-tight md:text-5xl">Find the right car, at the right time.</h1>
          <p className="mt-5 max-w-md text-slate-300">Explore available vehicles, filter your choices, and purchase from live inventory.</p></div>
        <div className="text-sm text-slate-400">Simple inventory. Clear decisions.</div>
      </div>
      <div className="flex flex-col justify-center p-8 md:p-12">
        <h2 className="text-3xl font-bold">{mode === 'login' ? 'Welcome back' : 'Create an account'}</h2>
        <p className="mt-2 text-slate-500">{mode === 'login' ? 'Sign in to browse available cars.' : 'Register to explore and purchase vehicles.'}</p>
        <form onSubmit={submit} className="mt-8 space-y-5">
          <label className="block text-sm font-semibold">Email address<input className={`${inputStyle} mt-2`} type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label>
          <label className="block text-sm font-semibold">Password<input className={`${inputStyle} mt-2`} type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength="8" required value={password} onChange={e => setPassword(e.target.value)} /></label>
          {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button className={`${primaryStyle} w-full`} disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        </form>
        <button className="mt-6 text-sm font-semibold text-blue-700 hover:underline" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'New here? Create an account' : 'Already registered? Sign in'}
        </button>
      </div>
    </div>
  </div>
}

function CarForm({ car, onSave, onCancel, busy }) {
  const [form, setForm] = useState(car || emptyCar)
  function change(event) { setForm({ ...form, [event.target.name]: event.target.value }) }
  function submit(event) {
    event.preventDefault()
    // The API validates again; numeric conversion keeps the request schema clear.
    onSave({ ...form, price: Number(form.price), quantity: Number(form.quantity) })
  }
  return <form onSubmit={submit} className="mt-5 grid gap-4 rounded-2xl border border-blue-100 bg-blue-50 p-5 sm:grid-cols-2 lg:grid-cols-5">
    {['make', 'model', 'category'].map(field => <label className="text-xs font-bold uppercase tracking-wide text-slate-600" key={field}>{field}
      <input name={field} className={`${inputStyle} mt-1`} value={form[field]} onChange={change} required maxLength="80" /></label>)}
    <label className="text-xs font-bold uppercase tracking-wide text-slate-600">Price
      <input name="price" className={`${inputStyle} mt-1`} type="number" min="0.01" step="0.01" value={form.price} onChange={change} required /></label>
    <label className="text-xs font-bold uppercase tracking-wide text-slate-600">Quantity
      <input name="quantity" className={`${inputStyle} mt-1`} type="number" min="0" step="1" value={form.quantity} onChange={change} required /></label>
    <div className="flex gap-3 sm:col-span-2 lg:col-span-5">
      <button disabled={busy} className={primaryStyle}>{car ? 'Save changes' : 'Add vehicle'}</button>
      <button type="button" onClick={onCancel} className="rounded-xl px-4 text-sm font-semibold text-slate-600 hover:bg-white">Cancel</button>
    </div>
  </form>
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('dealership_token') || '')
  const [user, setUser] = useState(null)
  const [cars, setCars] = useState([])
  const [filters, setFilters] = useState({ make: '', model: '', category: '', min_price: '', max_price: '' })
  const [editing, setEditing] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async (activeFilters = filters) => {
    if (!token) return
    try {
      const query = new URLSearchParams(Object.entries(activeFilters).filter(([, value]) => value !== ''))
      const data = await request(`/api/vehicles/search?${query}`, { token })
      setCars(data)
      setError('')
    } catch (problem) { setError(problem.message) }
  }, [token])

  useEffect(() => {
    if (!token) return
    // Verify saved tokens after refreshing the browser; expired sessions return to login.
    request('/api/auth/me', { token }).then(setUser).catch(() => logout())
    load()
  }, [token, load])

  function login(session) {
    localStorage.setItem('dealership_token', session.access_token)
    setToken(session.access_token)
    setUser(session.user)
  }
  function logout() {
    localStorage.removeItem('dealership_token')
    setToken(''); setUser(null); setCars([])
  }
  async function action(callback, success) {
    setBusy(true); setError(''); setMessage('')
    try { await callback(); await load(); setMessage(success); setShowForm(false); setEditing(null) }
    catch (problem) { setError(problem.message) }
    finally { setBusy(false) }
  }
  function saveCar(data) {
    const path = editing ? `/api/vehicles/${editing.id}` : '/api/vehicles'
    action(() => request(path, { method: editing ? 'PUT' : 'POST', token, body: data }), editing ? 'Vehicle updated.' : 'Vehicle added.')
  }
  function removeCar(car) {
    if (!window.confirm(`Delete ${car.make} ${car.model}?`)) return
    action(() => request(`/api/vehicles/${car.id}`, { method: 'DELETE', token }), 'Vehicle deleted.')
  }

  if (!token) return <Auth onLogin={login} />
  return <div className="min-h-screen">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-5">
        <div className="text-lg font-black tracking-wide">DRIVELINE <span className="text-blue-600">/</span> INVENTORY</div>
        <div className="flex items-center gap-4 text-sm"><span className="hidden text-slate-500 sm:inline">{user?.email} {user?.role === 'admin' && '· Admin'}</span>
          <button className="font-semibold text-blue-700 hover:underline" onClick={logout}>Sign out</button></div>
      </div>
    </header>
    <main className="mx-auto max-w-7xl px-5 pb-20 pt-10">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div><p className="text-xs font-bold uppercase tracking-[0.22em] text-blue-700">The collection</p>
          <h1 className="mt-2 text-4xl font-black tracking-tight">Find your next vehicle</h1>
          <p className="mt-2 text-slate-500">Live availability, clear prices, easy browsing.</p></div>
        {user?.role === 'admin' && <button className={primaryStyle} onClick={() => { setEditing(null); setShowForm(true) }}>+ Add vehicle</button>}
      </div>
      {showForm && <CarForm key={editing?.id || 'new'} car={editing} onSave={saveCar} onCancel={() => { setShowForm(false); setEditing(null) }} busy={busy} />}
      <form onSubmit={e => { e.preventDefault(); load(filters) }} className="mt-8 grid gap-3 rounded-2xl bg-white p-5 shadow-sm sm:grid-cols-2 lg:grid-cols-6">
        {['make', 'model', 'category'].map(field => <input key={field} className={inputStyle} aria-label={`Search by ${field}`} placeholder={field[0].toUpperCase() + field.slice(1)} value={filters[field]} onChange={e => setFilters({ ...filters, [field]: e.target.value })} />)}
        <input className={inputStyle} aria-label="Minimum price" type="number" min="0" placeholder="Min price" value={filters.min_price} onChange={e => setFilters({ ...filters, min_price: e.target.value })} />
        <input className={inputStyle} aria-label="Maximum price" type="number" min="0" placeholder="Max price" value={filters.max_price} onChange={e => setFilters({ ...filters, max_price: e.target.value })} />
        <button className={primaryStyle}>Search</button>
        <button type="button" className="text-sm font-semibold text-slate-500 hover:text-blue-700 lg:col-span-6 lg:justify-self-start" onClick={() => { const reset = { make: '', model: '', category: '', min_price: '', max_price: '' }; setFilters(reset); load(reset) }}>Clear filters</button>
      </form>
      {error && <p role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-red-700">{error}</p>}
      {message && <p role="status" className="mt-5 rounded-xl bg-green-50 p-4 text-green-800">{message}</p>}
      <div className="mt-8 flex items-center justify-between"><h2 className="text-xl font-bold">Available inventory</h2><span className="text-sm text-slate-500">{cars.length} vehicles</span></div>
      {cars.length === 0 ? <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">No vehicles found. Try different filters{user?.role === 'admin' ? ' or add your first car' : ''}.</div> :
        <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{cars.map(car => <article key={car.id} className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
          <div className="flex h-36 items-center justify-center bg-gradient-to-br from-slate-800 to-blue-900"><span className="text-5xl text-white/80" aria-hidden="true">✦</span></div>
          <div className="p-6"><div className="flex items-start justify-between gap-3"><div><div className="text-xs font-bold uppercase tracking-wider text-blue-700">{car.category}</div>
            <h3 className="mt-1 text-xl font-extrabold">{car.make} {car.model}</h3></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${car.quantity ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'}`}>{car.quantity ? `${car.quantity} in stock` : 'Sold out'}</span></div>
            <div className="mt-6 flex items-center justify-between gap-3"><span className="text-2xl font-black">${Number(car.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              <button disabled={busy || car.quantity === 0} className={primaryStyle} onClick={() => action(() => request(`/api/vehicles/${car.id}/purchase`, { method: 'POST', token }), 'Purchase complete. Inventory updated.')}>Purchase</button></div>
            {user?.role === 'admin' && <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-100 pt-4 text-sm font-semibold">
              <button className="text-blue-700 hover:underline" onClick={() => { setEditing(car); setShowForm(true); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Edit</button>
              <button className="text-blue-700 hover:underline" onClick={() => action(() => request(`/api/vehicles/${car.id}/restock`, { method: 'POST', token, body: { amount: 1 } }), 'One vehicle added to stock.')}>Restock +1</button>
              <button className="text-red-600 hover:underline" onClick={() => removeCar(car)}>Delete</button></div>}
          </div></article>)}</div>}
    </main>
  </div>
}

export default App
