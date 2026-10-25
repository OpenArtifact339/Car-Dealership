# Car Dealership Inventory System

A full-stack inventory app with a FastAPI REST API, SQLite storage, JWT authentication, and a responsive React/Tailwind interface. Customers can search and purchase vehicles; admins can manage inventory.

## Requirements

- Python 3.10 or newer, Node.js 18 or newer, and npm
- Two terminal windows, one for the API and one for the UI

## Start the backend

```bash
cd backend
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set `JWT_SECRET` to a long random string (do not use the example value). Set `DATABASE_PATH` if you want the database somewhere other than `backend/dealership.db`. The server reads environment variables from your shell; it does not automatically load `.env`.

```bash
# macOS / Linux example; use your own secret:
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python seed_admin.py
uvicorn app.main:app --reload
```

On Windows PowerShell, generate a value with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then set it with `$env:JWT_SECRET="your-generated-value"`. Run `python seed_admin.py` and `uvicorn app.main:app --reload` afterward. The seed command asks for an email and password without echoing the password. It creates or resets an admin account. Register normal users in the UI. The API documentation is at `http://localhost:8000/docs`.

## Start the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`. For another API host, create `frontend/.env.local` with `VITE_API_URL=http://your-host:8000`. If your frontend runs at a different origin, set `FRONTEND_ORIGIN` for the backend before starting it. No API secret belongs in the frontend environment file.

## Use the app

Register a regular account or log in with the admin account created by `seed_admin.py`. Search by make, model, category, and price range. Purchase decreases quantity by one. When quantity is zero, purchase is disabled in the UI and rejected by the API. Admin accounts can add, edit, delete, and restock vehicles.

## API routes

| Method | Path | Permission | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | Public | Register a regular user |
| POST | `/api/auth/login` | Public | Return bearer token and user role |
| GET | `/api/auth/me` | Signed in | Restore session after refresh |
| GET | `/api/vehicles` | Signed in | List vehicles |
| GET | `/api/vehicles/search` | Signed in | Filter by make, model, category, `min_price`, `max_price` |
| POST | `/api/vehicles` | Admin | Add a vehicle |
| PUT | `/api/vehicles/{id}` | Admin | Replace vehicle details |
| DELETE | `/api/vehicles/{id}` | Admin | Delete a vehicle |
| POST | `/api/vehicles/{id}/purchase` | Signed in | Decrement stock by one |
| POST | `/api/vehicles/{id}/restock` | Admin | Increment stock by JSON `amount` (defaults to 1) |

Send `Authorization: Bearer <token>` for protected routes. A vehicle contains `make`, `model`, `category`, `price`, and `quantity`. Prices are stored in integer cents to avoid floating-point storage errors. API validation rejects nonpositive prices and negative quantities.

## Tests and build

```bash
cd backend
python -m pytest -q
```

Tests use separate SQLite files and cover login, access control, search, updates, validation, purchase, restock, and persistence. To save the actual test output for submission, run `python -m pytest -q > ../test-report.txt 2>&1` and check its exit status. For the frontend, run `cd frontend && npm run build`.

## Test-driven development and Git

For each remaining change, add a failing behavior test and commit it, then implement and commit the passing behavior, then refactor and test again. Do not claim tests or commits were written earlier than they were. Explain your actual process in the submission. Use frequent descriptive commits. The assignment requests an AI co-author trailer on commits involving AI; add it according to the assignment's example when making your own commits.

## Screenshots

After running the app, capture real screenshots of login, customer inventory/search, and admin inventory controls. Place them in `screenshots/` and link them here before submitting. The folder contains capture instructions; screenshots are intentionally not fabricated.

## My AI Usage

**Tool:** ChatGPT (Codex).

**How it was used:** I requested a complete starting implementation with explanatory comments. It generated the FastAPI/SQLite API, React/Tailwind UI, tests, and setup documentation. I then ran, reviewed, debugged, and customized the project before submission. **Edit this sentence to accurately describe what you personally did.**

**Reflection:** AI accelerated the initial structure and suggested tests for permissions and stock changes. I am responsible for checking the behavior, understanding the implementation, fixing defects, and explaining the choices. 


Raw conversation logs or public chat links belong in the root `PROMPTS.md`, without summarizing or rewriting them.
