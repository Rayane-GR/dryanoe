MouHassaBa — Project Technical Documentation
An accounting application tailored for the Algerian market, compliant with the SCF (Système Comptable Financier — Financial Accounting System).
---
1. Database Schema
The proposed structure is for a relational database (PostgreSQL is preferred for its excellent support for JSON, indexing, and precise financial transactions using the `NUMERIC` data type).
1.1 Organizations and Users (Multi-tenant)
```sql
-- Each organization (company, merchant, or independent accountant) acts as an independent "tenant"
CREATE TABLE companies (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
name            VARCHAR(255) NOT NULL,
nif             VARCHAR(20),          -- Tax Identification Number (Numéro d'Identification Fiscale)
nis             VARCHAR(20),          -- Statistical Identification Number (Numéro d'Identification Statistique)
rc              VARCHAR(30),          -- Commercial Register (Registre du Commerce)
article_imposition VARCHAR(30),        -- Tax Assessment Article
address         TEXT,
activity_type   VARCHAR(20),          -- 'physical' (individual) | 'legal' (corporate) — (IRG/IBS tax regimes)
fiscal_year_start DATE,
fiscal_year_end   DATE,
currency        VARCHAR(3) DEFAULT 'DZD',
created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id),
email           VARCHAR(255) UNIQUE NOT NULL,
password_hash   VARCHAR(255) NOT NULL,
full_name       VARCHAR(255),
role            VARCHAR(20) NOT NULL,  -- 'admin' | 'accountant' | 'employee'
two_factor_enabled BOOLEAN DEFAULT false,
is_active       BOOLEAN DEFAULT true,
created_at      TIMESTAMPTZ DEFAULT now()
);
``` CREATE TABLE audit_log (
id              BIGSERIAL PRIMARY KEY,
company_id      UUID REFERENCES companies(id),
user_id         UUID REFERENCES users(id),
action          VARCHAR(50),          -- 'create' | 'update' | 'delete' | 'post'
entity_type     VARCHAR(50),
entity_id       UUID,
diff            JSONB,
created_at      TIMESTAMPTZ DEFAULT now()
);
```
1.2 Chart of Accounts (SCF - Algerian Accounting System)
```sql
CREATE TABLE chart_of_accounts (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id),
code            VARCHAR(10) NOT NULL,     -- e.g., 411, 4456, 70110
label           VARCHAR(255) NOT NULL,
label_fr        VARCHAR(255),
class           SMALLINT NOT NULL,        -- 1 to 7
parent_code     VARCHAR(10),              -- to support sub-accounts
account_nature  VARCHAR(10),              -- 'debit' | 'credit' (default nature)
is_active       BOOLEAN DEFAULT true,
UNIQUE(company_id, code)
);
-- Automatically populated with the standard SCF chart of accounts when a company is created (seed data)
```
1.3 Journals & Entries
```sql
CREATE TABLE journals (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id),
code            VARCHAR(10) NOT NULL,     -- VE (Sales), AC (Purchases), BQ (Bank), OD (Miscellaneous)
label           VARCHAR(100)
);
CREATE TABLE journal_entries (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id),
journal_id      UUID REFERENCES journals(id),
entry_number    VARCHAR(30) NOT NULL,     -- Legal sequential numbering
entry_date      DATE NOT NULL,
reference       VARCHAR(100),             -- e.g., associated invoice number
description     TEXT,
is_posted       BOOLEAN DEFAULT false,    -- Finalized/posted (immutable)
fiscal_year     SMALLINT,
created_by      UUID REFERENCES users(id),
created_at      TIMESTAMPTZ DEFAULT now(),
UNIQUE(company_id, entry_number)
);

CREATE TABLE journal_entry_lines (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
entry_id        UUID REFERENCES journal_entries(id) ON DELETE CASCADE,
account_code    VARCHAR(10) NOT NULL,
label           VARCHAR(255),
debit           NUMERIC(15,2) DEFAULT 0,
credit          NUMERIC(15,2) DEFAULT 0,
partner_id       UUID,                    -- Optional reference to a customer/vendor (auxiliary account)
CHECK (debit >= 0 AND credit >= 0)
); -- Integrity constraint: The sum of debits must equal the sum of credits for each `entry_id` (to be verified at the application level before `is_posted` is set to `true`).
```
1.4 Customers and Suppliers
```sql
CREATE TABLE partners (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id),
type            VARCHAR(10) NOT NULL,     -- 'customer' | 'supplier' | 'both'
name            VARCHAR(255) NOT NULL,
nif             VARCHAR(20),
nis             VARCHAR(20),
rc              VARCHAR(30),
article_imposition VARCHAR(30),
address         TEXT,
phone           VARCHAR(30),
email           VARCHAR(255),
account_code    VARCHAR(10),              -- Subsidiary account code (e.g., 411xxx / 401xxx)
payment_terms   INTEGER DEFAULT 30,
created_at      TIMESTAMPTZ DEFAULT now()
);
```
1.5 Products and Inventory
```sql
CREATE TABLE products (
id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
company_id      UUID REFERENCES companies(id), 
sku VARCHAR(50), 
name VARCHAR(255) NOT NULL, 
type VARCHAR(10), -- 'good' | 'service' 
unit_price_ht NUMERIC(15,2), 
tva_rate NUMERIC(5,2) DEFAULT 19, -- 19 / 9 / 0 
sales_account VARCHAR(10), -- linked 70x account 
purchase_account VARCHAR(10), -- associated 60x/61x account 
stock_qty NUMERIC(15,3) DEFAULT 0, 
stock_min_alert NUMERIC(15,3) DEFAULT 0, 
is_active BOOLEAN DEFAULT true
);

CREATE TABLE stock_movements( 
id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
company_id UUID REFERENCES companies(id), 
product_id UUID REFERENCES products(id), 
movement_type VARCHAR(10), -- 'in' | 'out' | 'inventory' 
quantity NUMERIC(15,3), 
reference_doc UUID, -- invoice or inventory 
movement_date DATE, 
created_at TIMESTAMPTZ DEFAULT now()
);
```
1.6 Invoices (Factures / Devices / Avoirs)
```sql
CREATE TABLE invoices ( 
id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
company_id UUID REFERENCES companies(id), 
partner_id UUID REFERENCES partners(id), 
type VARCHAR(15) NOT NULL, -- 'sale' | 'purchase' | 'credit_note' | 'quote' 
invoice_number VARCHAR(30), -- empty until officially numbered (Davis is not numbered as an invoice) 
issue_date DATE NOT NULL, 
due_date DATE, 
status VARCHAR(15) DEFAULT 'draft', -- draft | confirmed | paid | cancelled 
total_ht NUMERIC(15,2), 
total_tva NUMERIC(15,2), 
total_ttc NUMERIC(15,2), 
journal_entry_id UUID REFERENCES journal_entries(id), -- automatically generated entry 
converted_from UUID REFERENCES invoices(id), -- Track conversion Devis → Factor 
created_at TIMESTAMPTZ DEFAULT now(), 
UNIQUE(company_id, type, invoice_number)
);

CREATE TABLE invoice_lines( 
id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE, 
product_id UUID REFERENCES products(id), 
description VARCHAR(255), 
quantity NUMERIC(15,3) DEFAULT 1, 
unit_price_ht NUMERIC(15,2), 
tva_rate NUMERIC(5,2), 
line_total_ht NUMERIC(15,2), 
line_total_tva NUMERIC(15,2)
);
```
1.7 Collection (TVA / TAP / IBS / IRG)
```sql
CREATE TABLE tax_declarations ( 
id UUID PRIMARY KEY DEFAULT gen_random_uuid(), 
company_id UUID REFERENCES companies(id), 
type VARCHAR(10) NOT NULL, -- 'G50' | 'IBS' | 'IRG' | 'TAP' 
period_start DATE, 
period_end DATE, 
tva_collected NUMERIC(15,2), -- from account 4457 
tva_deductible NUMERIC(15,2), -- from account 4456 
tva_due NUMERIC(15,2), 
tap_amount NUMERIC(15,2), 
status VARCHAR(15) DEFAULT 'draft', -- draft | filed | paid. paid 
due_date DATE, 
filed_at TIMESTAMPTZ
);
Simplified Table Relationships
`companies (1) → (N) users / partners / products / invoices / journal_entries`
`journal_entries (1) → (N) journal_entry_lines`
`invoices (1) → (N) invoice_lines`, and `invoices (1) → (1) journal_entries` (the automatically generated entry)
---
2. Proposed Tech Stack
Recommended Approach: Web-first application + PWA for mobile
Layer	Proposed Technology	Reason
Backend	Node.js (NestJS) or Django (Python)	Both offer rapid support for: authentication, role-based permissions, PDF generation, and task scheduling (e.g., tax reminders)
Database	PostgreSQL	`NUMERIC` precision for financial calculations, JSON support for flexibility, and reliable transaction handling
Frontend Web	React + TypeScript (with Vite)	Rich component ecosystem; easy support for RTL/i18n (Arabic/French)
Mobile	React Native or Flutter	Maximizes shared code between iOS/Android; supports local SQLite for offline mode
Offline Sync	Local SQLite/IndexedDB + synchronization via an event queue (using "last-write-wins" logic or manual conflict resolution)	Essential given the frequent internet interruptions in the Algerian context
PDF/Excel Export	Backend: pdf-lib or WeasyPrint; Excel: ExcelJS/openpyxl	For generating official invoices and reports
Authentication	JWT + optional 2FA (TOTP)	Explicitly required by the specifications
Hosting	Server located in Algeria or nearby in Europe (for fast access), with encrypted daily backups	Ensures compliance with financial data sovereignty requirements
> Note: If the objective is a mobile-only application without a web interface... ...web, **Flutter** remains the most suitable choice for achieving optimal performance in the intensive offline mode required by this project.
---
3. Phased Implementation Plan
Phase 1 — MVP (Estimated 6–8 weeks)
Infrastructure setup: database, authentication, and organization/user management
Loading the Standard Chart of Accounts (SCF) as seed data
Customer and supplier management (comprehensive profiles)
Creation of sales/purchase invoices with automated VAT (TVA) calculation and sequential numbering
Automatic generation of journal entries from each invoice (debit/credit logic)
Invoice export to PDF format
Basic general journal (view/search functionality)
Phase 2 — Full Accounting (4–6 weeks)
General Ledger for each account
Trial Balance with period-based filtering
Fiscal year-end closing and posting, with restrictions preventing modifications to posted entries
Balance Sheet (B...Balance Sheet and Income Statement (Compte de Résultat)
Dashboard with visual charts (revenue, expenses, profits, cash flow)
Credit/debit notes (Avoir) and conversion between quotes (Devis) and invoices (Facture)
Phase 3 — Automated Tax Filing + Advanced Inventory + Offline Mode (6–8 weeks)
Automated G50 tax return calculation (monthly/quarterly VAT) based on accounts 4456/4457
Calculation of the Professional Activity Tax (TAP) and estimation of Corporate Tax (IBS) / Personal Income Tax (IRG) based on the nature of the business
Automated reminders for tax filing deadlines (via notifications/email)
Comprehensive inventory management: low-stock alerts, periodic stocktaking, and inventory movement tracking
Full offline mode with smart synchronization and conflict resolution
Exportable account statements for each customer/supplier
Complete audit log and granular, role-based access permissions
Cross-phase considerations
Legal compliance: Verify the latest updates to the Algerian Accounting System (SCF) and current tax rates (VAT/TAP/IBS) with a certified Algerian accountant prior to launch, as these rates and regulations are subject to legal change.
Testing: Every automatically generated accounting entry must be validated to ensure the balance (debit = credit) before being posted.
Security: Encryption of sensitive data (Tax Identification Number/NIF, account numbers) both within the database and during transmission (TLS).
