# HSA Demo (Fresh Build)

A local-only Flask app showing the HSA lifecycle:

- Create Account (public)
- Login/Logout
- Deposit Funds (auth)
- Issue Virtual Card (auth) + table of cards (full PAN + cardholder)
- Purchase (auth) using dropdown of your card numbers (PAN)
- MCC / item eligibility (demo data)

## Run

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows cmd:        .venv\Scripts\activate.bat
# macOS/Linux:        source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Notes
- Home and Create Account are public to avoid prefetch redirect loops.
- All APIs and app pages except Home, Login, Create Account are behind auth.
- Database: SQLite `hsa.db` auto-created.
