# Code Generator Plugin

The `code_generator/` plugin automatically generates CRUD code from database table definitions.

---

## Directory Structure

```
code_generator/
├── plugin.toml              # Plugin metadata
├── README.md                # Plugin documentation
├── path_conf.py             # Path configuration
├── enums.py                 # Generator enumerations
│
├── api/                     # REST endpoints
│   └── v1/
│       ├── gen.py           # Generation endpoints
│       └── ...
│
├── schema/                  # Pydantic schemas
│   └── gen.py               # Generation DTOs
│
├── service/                 # Business logic
│   └── gen.py               # Generation service
│
├── crud/                    # Database operations
│   └── gen.py               # Generation CRUD
│
├── model/                   # SQLAlchemy models
│   └── gen.py               # Generation tracking model
│
├── templates/               # Jinja2 templates
│   ├── api.jinja2
│   ├── crud.jinja2
│   ├── model.jinja2
│   ├── schema.jinja2
│   └── service.jinja2
│
└── utils/                   # Generator utilities
    └── ...
```

---

## Features

- **Database Introspection**: Read table structure from database
- **Template-Based Generation**: Jinja2 templates for each layer
- **Pseudo 3-Tier Output**: Generates api, schema, service, crud, model files
- **Download as ZIP**: Package generated code for download

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/gen/tables` | GET | List database tables |
| `/api/v1/gen/columns/{table}` | GET | Get table columns |
| `/api/v1/gen/preview` | POST | Preview generated code |
| `/api/v1/gen/code` | POST | Generate code files |
| `/api/v1/gen/download` | GET | Download as ZIP |

---

## Usage Flow

```
┌───────────────────────┐
│ 1. List Tables        │
│ GET /gen/tables       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 2. Get Columns        │
│ GET /gen/columns/{t}  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 3. Configure Options  │
│ - Select columns      │
│ - Set naming rules    │
│ - Choose templates    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 4. Preview Code       │
│ POST /gen/preview     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ 5. Generate & Download│
│ POST /gen/code        │
│ GET /gen/download     │
└───────────────────────┘
```

---

## Generated File Structure

```
generated/
├── api/
│   └── v1/
│       └── {resource}.py
├── schema/
│   └── {resource}.py
├── service/
│   └── {resource}.py
├── crud/
│   └── {resource}.py
└── model/
    └── {resource}.py
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CODE_GENERATOR_DOWNLOAD_ZIP_FILENAME` | `fba_generator` | Output ZIP filename |

---

*Last Updated: December 2024*
