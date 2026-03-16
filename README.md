# Passagium - Handover System

This project is an MVP (Minimum Viable Product) for a **handover/pass-down** system that can be used in any domain (healthcare, security, concierge, operations, etc.).
It is designed to run **primarily inside Django Admin**, using **Django Unfold**, minimizing custom UI.

Key features:
- Multi-company (tenant-like) model with `Company`
- Automatic company settings creation via **signals**
- Handover workflow: Draft → Delivered → Acknowledged → Closed
- Per-recipient receipts (confirmation) with optional “all required receipts” policy
- Teams and team membership (deliver to teams, expand to users)
- Soft delete for auditability
- Attachments (FileField) and media support in development

---

## Requirements
- Python 3.11+ recommended
- Django 6.0
- Django Unfold installed and configured
- SQLite (default) or any supported DB

---

## 1) Create and activate a virtual environment

### Linux/macOS
```bash
python -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

---

## 2) Install dependencies
```bash
pip install -r requirements.txt
```

---

## 3) Verify settings module
This repository uses a settings structure under:

```
app/settings/
  base.py
  local.py
  staging.py
  production.py
```

Make sure your `DJANGO_SETTINGS_MODULE` points to the correct module.
For local development, use:

```bash
export DJANGO_SETTINGS_MODULE=app.settings.local
```

On Windows (PowerShell):
```powershell
$env:DJANGO_SETTINGS_MODULE="app.settings.local"
```

If your project uses `app/settings.py` directly, keep using it. The important part is that:
- `INSTALLED_APPS` includes Unfold and the project apps
- accounts app uses the AppConfig so signals are registered:
  - `app.accounts.apps.AccountsConfig`

---

## 4) Configure `INSTALLED_APPS`
In your active settings file (`app/settings/base.py` or `app/settings/local.py`), ensure:

```python
INSTALLED_APPS = [
    # ...
    "app.core",
    "app.accounts.apps.AccountsConfig",  # required for signals
    "app.handover",
]
```

---

## 5) Configure media (attachments) for development
Attachments are stored using Django `FileField`.

In your development settings (`app/settings/local.py` recommended), ensure:

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

Also ensure your `app/urls.py` serves media when `DEBUG=True`:

```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 6) Run migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 7) Create an admin user
```bash
python manage.py createsuperuser
```

---

## 8) Start the server
```bash
python manage.py runserver
```

Then open:
- http://127.0.0.1:8000/admin/

---

## 9) Quick functional sanity check (recommended)
1) In Admin, create a **Company**
   - A **CompanySettings** row should be created automatically (signal).
2) Create:
   - Site(s)
   - Shift(s)
   - Team(s)
   - TeamMember(s)
   - ItemCategory and Tag(s)
3) Create a Handover, add at least one item, add recipients, then:
   - Deliver (Admin action)
   - Confirm receipt(s)
   - Close

---

## Troubleshooting

### CompanySettings is not created automatically
- Ensure `INSTALLED_APPS` uses:
  - `app.accounts.apps.AccountsConfig`
- Ensure `app/accounts/apps.py` has `ready()` importing `signals`
- Restart the server after changes

### Attachments not accessible in development
- Verify `MEDIA_ROOT` and `MEDIA_URL`
- Verify `app/urls.py` serves media when `DEBUG=True`
- Verify file permissions in the `media/` directory

---

## Notes
This MVP intentionally focuses on:
- robust business rules
- auditability (soft delete)
- operational simplicity in Admin

A future phase can introduce:
- dedicated end-user UI
- database-per-company routing
- signature capture (beyond boolean confirmation)
- permissions refinement per role/team/site
