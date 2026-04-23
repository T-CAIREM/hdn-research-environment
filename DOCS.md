# HDN Research Environment — Developer Documentation

## What Is This Project?

HDN Research Environment is a **Django web application** that lets researchers create and manage cloud-based data science workspaces on **Google Cloud Platform (GCP)**. Think of it as a self-service portal where a researcher can:

1. Log in with their institutional account
2. Provision a personal GCP project ("workspace")
3. Launch a Jupyter or RStudio server ("environment") on a VM they configure
4. Share data buckets or billing access with collaborators
5. Stop/start/resize their VM without losing data

The app sits between the user and GCP — it calls a set of internal microservices (Cloud Run) which in turn talk to GCP APIs and Cloud Workflows to create/destroy real infrastructure.

---

## High-Level Architecture

```
Browser
  │
  ▼
Django App  (this repo — environment/)
  │   Views → Services → API Client
  │
  ▼  OIDC JWT auth
External Backend API  (CLOUD_RESEARCH_ENVIRONMENTS_API_URL)
  │
  └── Manages GCP Resources:
        ├── Cloud Identity (user accounts)
        ├── Compute Engine (VMs for Jupyter/RStudio)
        ├── Cloud Storage (buckets)
        ├── Cloud IAM (permissions & billing)
        └── Cloud Workflows (task orchestration)
```

**External service calls are never made directly from Django to GCP.** All GCP work goes through the external backend API configured in `settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL`. Django only stores lightweight state (identities, invite tokens, workflow IDs, VM pricing) in Postgres.

> **Note:** This repository contains a `workspace-controller-repo/` directory with old Cloud Run microservice code. This is a historical artifact and is no longer used — the backend is now a separate external service.

---

## Repository Layout

```
hdn-research-environment/
├── environment/                   # The Django app (all main code lives here)
│   ├── models.py                  # Database models
│   ├── views.py                   # HTML views (legacy server-side rendering)
│   ├── react_views.py             # JSON API views (new React frontend)
│   ├── services.py                # Business logic layer
│   ├── api/
│   │   ├── __init__.py            # HTTP client for Cloud Run microservices
│   │   └── decorators.py          # Adds Google OIDC auth headers to requests
│   ├── entities.py                # Plain dataclasses (no DB) for API responses
│   ├── serializers.py             # Entities → JSON dicts (for React API)
│   ├── deserializers.py           # API JSON responses → Entities
│   ├── api_types.py               # TypedDicts for type-safe API responses
│   ├── forms.py                   # Django forms with validation
│   ├── urls.py                    # URL routing (HTML + /api/ JSON endpoints)
│   ├── tasks.py                   # Background tasks (django-background-tasks)
│   ├── signals.py                 # Django signals wiring models to tasks
│   ├── mailers.py                 # Transactional email helpers
│   ├── decorators.py              # Auth/access guard decorators for views
│   ├── utilities.py               # Shared helper functions
│   ├── exceptions.py              # Custom exception classes
│   ├── constants.py               # App-wide constants (limits, pricing)
│   ├── validators.py              # Field-level validators (billing ID format)
│   ├── migrations/                # Django DB migrations (21 files)
│   ├── templates/environment/     # HTML templates (server-side pages)
│   ├── static/environment/        # CSS, JS, images
│   ├── templatetags/              # Custom Django template filters
│   └── tests/                     # Unit & integration tests
├── workspace-controller-repo/     # Cloud Run microservices (separate deployments)
│   ├── API-gateway/               # Swagger spec that routes to Cloud Run services
│   ├── workflow-invoker/          # Triggers Cloud Workflows
│   ├── user-creation/             # Provisions GCP Cloud Identity user
│   ├── workbench/                 # Creates/manages Jupyter & RStudio VMs
│   ├── workspace/                 # Creates/destroys GCP projects
│   ├── get_uoft_workspace/        # Returns workspace details
│   └── appengine-default-service-stop/
├── credentials/
│   ├── dev/credentials.enc.json   # SOPS-encrypted dev credentials
│   └── prod/credentials.enc.json  # SOPS-encrypted prod credentials
├── setup.cfg                      # Package metadata & Python dependencies
└── .github/workflows/black.yml    # CI: enforces Black code formatting
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| Python 3.7+ | Runtime |
| Django 4.2+ | Web framework |
| PostgreSQL | Database |
| `sops` | Decrypt local credentials (`brew install sops`) |
| GCP access | Required to call Cloud Run services and decrypt credentials |
| `google-cloud-workflows` | Python library for workflow tracking |

**Key Python dependencies** (from `setup.cfg`):

```
django >= 4.2.18
djangorestframework >= 3.15.2
google-cloud-workflows >= 1.6.1
django-background-tasks-updated >= 1.2.7
```

---

## Credentials Setup

Credentials are encrypted with **SOPS** using GCP Cloud KMS. You need GCP credentials on your machine before you can decrypt them.

```bash
# Authenticate with GCP first
gcloud auth application-default login

# Decrypt dev credentials
cd credentials/dev
sops --decrypt credentials.enc.json > credentials.json

# After editing, re-encrypt (only the .enc.json goes to Git)
sops --encrypt credentials.json > credentials.enc.json
rm credentials.json
```

Never commit unencrypted `credentials.json` files.

---

## Database Models

Models live in `environment/models.py`. Django's built-in `User` model comes from the `physionet` package (a dependency) — the environment app extends it.

| Model | What it represents |
|-------|-------------------|
| `CloudIdentity` | A user's GCP Cloud Identity account (email + GCP user ID). One per user. |
| `CloudGroup` | A GCP Cloud Identity Group (Google Group). Used for IAM role assignment. |
| `BillingAccountSharingInvite` | Token-based invite for sharing a GCP billing account with another user. |
| `BucketSharingInvite` | Token-based invite for sharing a GCS storage bucket. Permissions: `read` or `read_write`. |
| `Workflow` | Tracks an in-flight Cloud Workflow execution (create/delete workspace, etc.). |
| `GCPRegion` | Supported GCP regions (us-central1, northamerica-northeast1, etc.). |
| `InstanceType` | VM family classification (general, compute, memory, storage, accelerator). |
| `VMInstance` | A specific machine type with CPU, memory, region, and price. |
| `GPUAccelerator` | GPU spec attached to a region with price and memory type. |

`VMInstance` and `GPUAccelerator` are populated from GCP pricing data and used to populate the environment creation form dropdowns.

---

## Core Concepts

### Workspace
A **workspace** is a GCP project created on behalf of a user. It is the billing and IAM boundary for all resources. A user can have up to **4 active workspaces** (`MAX_RUNNING_WORKSPACES = 4`).

### Research Environment (Workbench)
An **environment** is a VM inside a workspace running either:
- **Jupyter** — standard Jupyter notebook server
- **RStudio** — RStudio Server with SSL certificate
- **Collaborative** — multi-user Jupyter environment

Environments can be stopped (VM off, data preserved), started, resized, or deleted.

### Shared Workspace / Bucket
A **shared workspace** is a separate GCP project for collaboration. Inside it, **shared buckets** (GCS) store data that can be shared with specific users (read or read+write).

### Collaborative Environment
A `COLLABORATIVE` environment type lets multiple users work inside the same Jupyter instance. The owner adds collaborators by email — they appear in the environment's user list and can join via the shared URL. A collaborator can also **leave** the environment themselves without the owner having to remove them.

### Billing Account
The GCP billing account that pays for a workspace's resources. A workspace is created under one billing account, but the linked billing account can be **changed** later via the admin action (`POST /api/workspace/update-billing`). Billing accounts can also be **shared** with other users so they can create their own workspaces under the same billing account.

### Cloud Identity
Before creating any workspace, users must provision a **GCP Cloud Identity account** — a `@hdn.research...` email tied to their institutional login. This is a one-time setup step.

---

## Request Flow: Creating a Workspace

Here is what happens end-to-end when a user clicks "Create Workspace":

```
1. Browser → POST /api/workspace/create
2. react_views.py: CreateWorkspaceView
   - Validates billing_account_id
   - Calls services.create_workspace()
3. services.py: create_workspace()
   - Calls api.create_workspace(email, billing_account_id, user_groups)
4. api/__init__.py: create_workspace()
   - HTTP POST to Cloud Run API Gateway
   - Headers include Google OIDC Bearer token
5. API Gateway → Cloud Run: workflow-invoker
   - Triggers a Cloud Workflow execution
6. Cloud Workflow runs steps:
   a. Create GCP project
   b. Link billing account
   c. Enable required APIs
   d. Set IAM permissions
7. Django saves Workflow model (execution_resource_name)
8. Frontend polls GET /api/workflows until status = SUCCESS
```

Long-running operations (workspace/environment creation) are **async**. Django starts the workflow and returns immediately. The frontend polls the `/api/workflows` endpoint to track progress.

---

## Request Flow: Creating an Environment

```
1. Browser → POST /api/environment/create/<workspace_id>
2. react_views.py: CreateEnvironmentView
   - Validates machine_type, region, environment_type, disk_size, gpu_accelerator
3. services.py: create_research_environment()
   - Resolves billing account, cloud identity email
   - Calls api.create_workbench(...)
4. api/__init__.py: create_workbench()
   - HTTP POST to Cloud Run workbench service
   - Passes VM specs (machine_type, region, disk_size, GPU)
5. Cloud Run → Cloud Workflow → Compute Engine
   - Provisions the VM
   - Configures Jupyter/RStudio
   - Returns URL for the notebook server
6. Django saves Workflow model
7. Frontend polls until environment status = RUNNING
8. User clicks the URL to open their notebook
```

---

## Service Layer (`services.py`)

The service layer is the heart of the application. Views call services; services call the API client. **Never call `api/` directly from views.**

Key service functions:

| Function | What it does |
|----------|-------------|
| `create_workspace()` | Starts workspace creation workflow |
| `delete_workspace()` | Tears down GCP project and all resources |
| `get_workspaces_list()` | Fetches all user workspaces with their environments |
| `create_research_environment()` | Provisions Jupyter/RStudio VM |
| `stop_running_environment()` | Pauses VM (keeps disk) |
| `start_stopped_environment()` | Resumes paused VM |
| `change_environment_machine_type()` | Resizes CPU/memory/GPU |
| `delete_environment()` | Deletes VM and associated resources |
| `share_billing_account()` | Sends email invite + creates DB record |
| `create_shared_bucket()` | Creates GCS bucket in shared workspace |
| `share_bucket()` | Sends email invite for bucket access |
| `consume_bucket_sharing_token()` | Accepts invite, calls IAM API |
| `add_workbench_collaborator()` | Grants edit access to another user's env |
| `remove_workbench_collaborator()` | Revokes collaborator access |
| `leave_collaborative_environment()` | Removes the current user from someone else's env |
| `update_workspace_billing_account()` | Swaps the billing account linked to a workspace |
| `get_billing_accounts_list()` | Returns user's available billing accounts |
| `search_users_by_cloud_email()` | Searches users by GCP Cloud Identity email (used by the collaborator picker) |

Error handling: most service functions use a `@handle_api_error` decorator that catches API failures and raises typed exceptions from `exceptions.py`.

### Error Display Utilities (`utilities.py`)

A set of helpers used by views and templates to classify and render `ServiceError` objects returned by the API:

| Function | Purpose |
|----------|---------|
| `has_service_errors()` | Whether a workspace/workbench has any errors |
| `has_billing_issues()` / `requires_billing_change()` | Detect billing-specific problems (e.g. billing account detached) |
| `get_billing_link()` | Returns the URL to fix the billing issue |
| `get_critical_errors()` | Filters errors that block the workspace from being usable |
| `group_errors_by_severity()` | Buckets errors into `critical` / `warning` / `info` |
| `format_error_message()` | Human-readable error string for display |
| `get_error_action_text()` / `get_error_action_link()` | CTA button text and URL for retryable errors |
| `get_error_css_class()` / `get_error_severity()` | CSS class and severity label for UI badges |
| `workspace_is_functional()` / `workbench_is_accessible()` | Top-level checks used to decide whether to render action buttons |

These are called from templates and serializers — they translate raw API `ServiceError` payloads into something the UI can render with the right styling and retry actions.

---

## API Client (`environment/api/__init__.py`)

This module contains all the HTTP calls to the Cloud Run services. It never contains business logic — just request construction and response parsing.

**Authentication**: Every call goes through the `@api_request` decorator in `api/decorators.py`, which fetches a short-lived **Google OIDC ID token** from the metadata server and adds it as a `Bearer` token header.

The base URL is read from `settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL`.

---

## URL Routing (`environment/urls.py`)

There are two categories of URLs:

**HTML views** (server-side rendered, legacy):
- `/` — Research environments dashboard
- `/workspace/create` — Create workspace form
- `/environment/create/<workspace_id>` — Create environment form
- `/environment/update` / `/environment/stop` / `/environment/start` / `/environment/delete`
- `/environment/renew` — Renew RStudio SSL certificate
- `/sharing/...` — Bucket and billing sharing pages
- `/identity-provisioning/` — Cloud Identity setup wizard

**JSON API views** (`/api/` prefix, for React frontend):

Workspaces & environments:
- `GET /api/workspaces` — List user's workspaces with their environments
- `POST /api/workspace/create` — Create workspace (async, returns workflow ID)
- `DELETE /api/workspace/delete` — Delete workspace
- `POST /api/workspace/shared/create` — Create shared workspace
- `DELETE /api/workspace/shared/delete` — Delete shared workspace
- `POST /api/workspace/update-billing` — Change the billing account linked to a workspace
- `GET /api/available-projects` — List physionet projects available as dataset identifiers
- `POST /api/environment/create/<workspace_id>` — Create environment (async)
- `DELETE /api/environment/delete` — Delete environment
- `PATCH /api/environment/stop` — Stop (pause) environment
- `PATCH /api/environment/start` — Start (resume) environment
- `PATCH /api/environment/update` — Resize environment (CPU/memory/GPU)
- `POST /api/environment/leave` — Leave a collaborative environment you joined as a collaborator
- `GET /api/quotas/<workspace_id>` — GCP quota usage for a workspace
- `GET /api/available-resources` — VM types + GPU options + pricing (used to populate creation form)

Shared workspaces & buckets:
- `GET /api/shared-workspaces` — List accessible shared workspaces
- `POST /api/sharing/bucket/create/<workspace_id>` — Create a shared bucket
- `DELETE /api/sharing/bucket/delete` — Delete a shared bucket
- `POST /api/sharing/share/<workspace>/<bucket>` — Invite a user to a bucket (sends email)
- `GET /api/sharing/<bucket>/shares` — List current shares for a bucket
- `POST /api/sharing/<bucket>/revoke` — Revoke a user's bucket access
- `GET /api/sharing/<bucket>/confirm` — Landing page for bucket share invite token
- `POST /api/sharing/bucket/<bucket>/signed-url` — Generate a temporary signed download URL
- `GET /api/sharing/bucket/<bucket>/content` — List files/folders in a bucket
- `POST /api/sharing/bucket/<bucket>/content/create` — Create a folder in a bucket
- `DELETE /api/sharing/bucket/<bucket>/content/delete` — Delete a file or folder

Billing sharing:
- `GET /api/billing` — List user's billing accounts
- `POST /api/billing/<billing_account_id>/share` — Invite a user to a billing account (sends email)
- `GET /api/billing/<billing_account_id>/shares` — List current shares for a billing account
- `POST /api/billing/<billing_account_id>/revoke` — Revoke billing account access
- `GET /api/billing/confirm` — Landing page for billing share invite token

Collaborative environments:
- `GET /api/environment/collaborative/<workspace_id>/<service_account>` — Get shared environment details
- `POST /api/environment/collaborative/<workspace_id>/<service_account>/collaborators` — Add a collaborator
- `DELETE /api/environment/collaborative/<workspace_id>/<service_account>/collaborators` — Remove a collaborator
- `GET /api/users/search` — Search users by cloud email (used in the collaborator picker UI)
- `GET /api/workbench/notifications/<workspace_id>/<service_account>` — Get collaborator notifications
- `POST /api/workbench/notifications/viewed` — Mark a notification as read
- `DELETE /api/workbench/notifications/<workspace_id>/<service_account>` — Clear all notifications

User & auth:
- `GET /api/user` — Current user info + permissions
- `GET /api/workflows` — Latest workflow executions for the current user
- `GET /api/execution-status` — Poll a single workflow execution status

Misc React helpers:
- `GET /api/static-pages/` — Serves static React page routes (catch-all)
- `GET /api/front-page-buttons` — Partial rendering front-page action buttons

---

## View Layers

### Traditional Views (`views.py`)
Server-side rendered HTML using Django templates. These are the original views and are gradually being replaced by the React frontend.

### React API Views (`react_views.py`)
Return JSON responses consumed by the React SPA. These views:
1. Run auth decorators
2. Call services
3. Serialize the result via `serializers.py`
4. Return `JsonResponse`

The React frontend lives in a separate repository and is served separately. The `/api/` endpoints are the interface between them.

---

## Access Control

Every view is protected by a chain of decorators (defined in `environment/decorators.py`):

```python
@login_required                    # Django: must be logged in
@cloud_identity_required           # Must have provisioned GCP account
@billing_account_required          # Must have ≥1 billing account
```

Additional checks in services:
- **Workspace ownership**: users can only act on their own workspaces
- **Environment ownership**: `is_environment_owner(user, workbench_owner_username)`
- **Bucket ownership**: `is_shared_bucket_owner()`, `is_shared_bucket_admin()`
- **Admin console**: `has_access_to_admin_console()` (from physionet)

API calls authenticated with Google OIDC JWT — the token is issued to the Django app's service account and verified by the API Gateway.

---

## Background Tasks (`tasks.py` + `signals.py`)

Long-running operations triggered by model saves run as background tasks via **django-background-tasks-updated**.

| Task | When triggered | What it does |
|------|---------------|-------------|
| `give_user_permission_to_access_billing_account` | `BillingAccountSharingInvite` consumed | Calls IAM API to grant billing IAM role |
| `stop_environments_with_expired_access` | User's credentialing revoked | Stops all running environments for that user |
| `stop_event_participants_environments_with_expired_access` | Event ends | Stops environments for all event participants |
| `terminate_environments_if_access_still_expired` | 14 days after access expires | Permanently deletes environments if access not restored |

Signals in `signals.py` connect Django model `post_save` events to these tasks. For example, when a `DataAccessRequest` record is saved with an expiry date, a signal schedules the environment cleanup task.

---

## Email Notifications (`mailers.py`)

Three types of transactional emails are sent:

| Mailer | When | Contains |
|--------|------|---------|
| `send_billing_sharing_confirmation` | Billing account shared | Confirmation link with UUID token |
| `send_bucket_sharing_confirmation` | Bucket shared | Confirmation link with UUID token, permissions |
| `send_environment_access_expired` | Access expires | Notification that environments were stopped |

Invite tokens are UUIDs stored in `BillingAccountSharingInvite` / `BucketSharingInvite`. The confirmation URL includes the token and the recipient clicks it to accept.

---

## Entity Types (`entities.py`)

These are plain Python dataclasses (not DB models) that represent data returned from the Cloud Run API. They are constructed by `deserializers.py` from raw JSON.

| Entity | Description |
|--------|-------------|
| `ResearchWorkspace` | A GCP project with its list of environments |
| `ResearchEnvironment` | A single Jupyter/RStudio VM with status, specs, URL |
| `SharedWorkspace` | A collaboration GCP project |
| `SharedBucket` | A GCS bucket in a shared workspace |
| `Workflow` | A Cloud Workflow execution (id, type, status) |
| `ServiceError` | Structured error from a microservice |
| `EntityScaffolding` | Partial/in-progress entity during workflow execution |
| `QuotaInfo` | GCP quota usage for a workspace |
| `VMInstance` | Machine type with specs and price |
| `GPUAccelerator` | GPU hardware with price and memory spec |

Key `ResearchEnvironment` properties:
- `is_running` — status is RUNNING
- `is_paused` — status is STOPPED
- `is_in_progress` — status is CREATING / STARTING / UPDATING / STOPPING / DESTROYING
- `is_active` — running or in progress

---

## Supported GCP Regions

| Region ID | Location |
|-----------|---------|
| `us-central1` | Iowa, USA |
| `northamerica-northeast1` | Montréal, Canada |
| `europe-west3` | Frankfurt, Germany |
| `australia-southeast1` | Sydney, Australia |

---

## Supported Environment Types

| Type | Description |
|------|-------------|
| `JUPYTER` | Single-user Jupyter notebook server |
| `RSTUDIO` | RStudio Server with SSL certificate auto-provisioned |
| `COLLABORATIVE` | Multi-user Jupyter — collaborators can join the same notebook |

---

## Limits and Constants (`constants.py`)

| Constant | Value | Meaning |
|----------|-------|---------|
| `MAX_RUNNING_WORKSPACES` | 4 | Maximum concurrent workspaces per user |
| `MAX_CPU_USAGE` | 32 | Maximum vCPU cores per environment |
| `PERSISTENT_DATA_DISK_NAME` | `"Persistent data disk 1GB"` | Label for the attached data disk |

---

## External Backend API

Django calls a single external backend API at `settings.CLOUD_RESEARCH_ENVIRONMENTS_API_URL`. This service handles all GCP infrastructure operations — Django never calls GCP APIs directly.

Authentication uses **Google OIDC ID tokens**: the `@api_request` decorator in `environment/api/decorators.py` fetches a short-lived token from the GCP metadata server and attaches it as a `Bearer` header on every request.

Operation timeouts can be long (workspace creation can take up to 10 minutes) — this is why workspace/environment creation is async and uses the workflow polling pattern.

> The `workspace-controller-repo/` directory in this repo contains old Cloud Run microservice source code (Flask services + API Gateway Swagger spec). It is no longer actively used and can be ignored.

---

## Admin Console

A set of views gated behind the `user.can_view_admin_console` permission (from physionet). All routes are under the `/console/` prefix. Regular researchers never see these pages.

**Access guard:** `@console_permission_required("user.can_view_admin_console")` defined in `environment/decorators.py`.

### Cloud Groups (`/console/group/`)

Manages **GCP Cloud Identity Groups** (Google Groups) used for IAM role assignment. Groups are stored in the `CloudGroup` model and synced to GCP via the API.

| URL | What it does |
|-----|-------------|
| `GET /console/group` | List all groups with their members |
| `POST /console/group/create` | Create a new Cloud Identity Group |
| `DELETE /console/group/delete` | Delete a group |
| `POST /console/group/user/add/<user_id>` | Add a user to a group |
| `POST /console/group/user/remove/<user_id>` | Remove a user from a group |
| `GET /console/group/management` | View groups with their assigned IAM roles |
| `POST /console/group/<id>/roles/add` | Assign GCP IAM roles to a group |
| `POST /console/group/<id>/roles/remove` | Remove GCP IAM roles from a group |

Groups are how bulk IAM access is managed — rather than granting roles to individual users, users are added to a group that has the appropriate roles.

### Dataset Monitoring (`/console/monitoring/datasets`)

A read-only dashboard showing usage analytics for datasets. Calls `services.get_datasets_monitoring_data()` which hits the `/monitoring/datasets` backend endpoint and renders the results in `environment/admin/get_datasets_monitoring_data.html`.

---

## Fixtures (Seed Data)

Django fixtures pre-populate static reference data that doesn't change often. Load them with:

```bash
python manage.py loaddata environment/fixtures/initial_data.json
```

### `initial_data.json`

Seeds the VM pricing catalogue used to populate environment creation dropdowns. Contains:

- **`GCPRegion`** — the 4 supported regions (`us-central1`, `northamerica-northeast1`, `europe-west3`, `australia-southeast1`)
- **`InstanceType`** — machine type families (e.g. `general / n1`)
- **`VMInstance`** — specific machine configurations per region, each with CPU count, memory (GB), hourly price (USD), and a `gpu_attachable` flag

Example entry: `n1-standard` with 4 vCPU / 15 GB RAM in `us-central1` at $0.18/hr.

There are 28 VM entries across the 4 regions. If pricing changes or new machine types are added, this fixture file (and the `GPUAccelerator` table, managed separately) need to be updated and re-loaded.

### `demo-identities.json`

Seeds sample `CloudIdentity` records for local development/demo purposes. Not used in production.

---

## Testing

Tests live in `environment/tests/`. The main test files:

| File | What it tests |
|------|-------------|
| `test_services.py` | Service layer functions (largest file, ~35 KB) |
| `test_views.py` | HTTP view responses and redirects |
| `test_signals.py` | Signal handlers and background task scheduling |
| `test_decorators.py` | Auth/access decorator behavior |
| `test_utilities.py` | Utility helper functions |
| `test_validators.py` | Form field validators |
| `mocks.py` | Mock API responses used across all tests |
| `helpers.py` | Test setup utilities |

Run tests with:
```bash
python manage.py test environment
```

The test suite mocks the Cloud Run API client (`environment/api/`) so tests don't make real GCP calls.

---

## CI/CD

**GitHub Actions** (`.github/workflows/black.yml`):
- Triggered on every push
- Runs `black --check` to enforce Python code formatting
- Uses Python 3.11

To auto-fix formatting locally:
```bash
pip install black
black environment/
```

---

## Integration with physionet

This app is installed as a Django app inside a larger **physionet** platform. It depends on models and utilities from physionet's other apps:

| physionet component | Used for |
|--------------------|---------|
| `User` model | All user authentication |
| `has_access_to_admin_console()` | Admin feature gating |
| `can_access_project()` | Per-project access checks |
| `Event`, `EventApplication` | Event-based environment access |
| `Training` | Training-gated environment access |
| `DataAccessRequest` | Data access request gating |
| `PublishedProject` | Project-linked environments |

When a user's data access request expires or a training period ends, Django signals fire background tasks that stop the user's environments.

---

## Common Failure Modes

| Symptom | Likely cause |
|---------|-------------|
| "Cloud identity required" redirect | User hasn't completed the identity provisioning wizard |
| "No billing account" error | User has no billing account linked or shared with them |
| Workspace stuck in CREATING | Cloud Workflow failed — check the workflow execution in GCP Console |
| Environment URL not accessible | SSL cert expired (RStudio) — use the "Renew Certificate" action |
| Environment stuck in STOPPING/STARTING | Workflow invocation failed — retry from the UI |
| Sharing invite not found | Token is invalid/expired or already consumed/revoked |

---

## Environment Variables

| Variable | Where set | Purpose |
|----------|----------|---------|
| `CLOUD_RESEARCH_ENVIRONMENTS_API_URL` | Django settings | Base URL for Cloud Run API Gateway |
| GCP credentials | Application Default Credentials | Used by `google.oauth2.id_token` to get OIDC tokens |

---

## Glossary

| Term | Meaning |
|------|---------|
| Workspace | A GCP project owned by a researcher |
| Environment / Workbench | A VM (Jupyter or RStudio) inside a workspace |
| Cloud Identity | A GCP-managed user account provisioned for the researcher |
| Cloud Workflow | A GCP-managed YAML workflow that orchestrates multi-step infrastructure tasks |
| Cloud Run | GCP's managed serverless container runtime (hosts the microservices) |
| Bucket | A GCP Cloud Storage bucket used for data storage |
| Shared Workspace | A GCP project for collaboration, containing shared buckets |
| SOPS | Secrets OPerationS — tool for encrypting/decrypting credential files using KMS |
| OIDC JWT | OpenID Connect JSON Web Token — used for service-to-service authentication |
| Scaffolding | A partial entity returned by the API while a workflow is still in progress |