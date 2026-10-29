-- 001_initial_schema.sql
-- MouHassaBa initial schema: SCF accounting (Système Comptable Financier).
-- Generated from backend/app/models.py; keep the two in sync.

CREATE TABLE companies (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	nif VARCHAR(20), 
	nis VARCHAR(20), 
	rc VARCHAR(30), 
	article_imposition VARCHAR(30), 
	address TEXT, 
	activity_type VARCHAR(20), 
	fiscal_year_start DATE, 
	fiscal_year_end DATE, 
	currency VARCHAR(3) DEFAULT 'DZD' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE chart_of_accounts (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	code VARCHAR(10) NOT NULL, 
	label VARCHAR(255) NOT NULL, 
	label_fr VARCHAR(255), 
	class SMALLINT NOT NULL, 
	parent_code VARCHAR(10), 
	account_nature VARCHAR(10), 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_accounts_company_code UNIQUE (company_id, code), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE TABLE journals (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	code VARCHAR(10) NOT NULL, 
	label VARCHAR(100), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_journals_company_code UNIQUE (company_id, code), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
);

CREATE TABLE partners (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	type VARCHAR(10) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	nif VARCHAR(20), 
	nis VARCHAR(20), 
	rc VARCHAR(30), 
	article_imposition VARCHAR(30), 
	address TEXT, 
	phone VARCHAR(30), 
	email VARCHAR(255), 
	account_code VARCHAR(10), 
	payment_terms SMALLINT DEFAULT 30 NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id)
);

CREATE TABLE products (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	sku VARCHAR(50), 
	name VARCHAR(255) NOT NULL, 
	type VARCHAR(10), 
	unit_price_ht NUMERIC(15, 2), 
	tva_rate NUMERIC(5, 2) DEFAULT 19 NOT NULL, 
	sales_account VARCHAR(10), 
	purchase_account VARCHAR(10), 
	stock_qty NUMERIC(15, 3) DEFAULT 0 NOT NULL, 
	stock_min_alert NUMERIC(15, 3) DEFAULT 0 NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id)
);

CREATE TABLE tax_declarations (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	type VARCHAR(10) NOT NULL, 
	period_start DATE, 
	period_end DATE, 
	tva_collected NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	tva_deductible NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	tva_due NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	tap_amount NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	status VARCHAR(15) DEFAULT 'draft' NOT NULL, 
	due_date DATE, 
	filed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id)
);

CREATE TABLE users (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(255), 
	role VARCHAR(20) NOT NULL, 
	two_factor_enabled BOOLEAN DEFAULT false NOT NULL, 
	is_active BOOLEAN DEFAULT true NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE, 
	UNIQUE (email)
);

CREATE TABLE audit_log (
	id BIGSERIAL NOT NULL, 
	company_id UUID, 
	user_id UUID, 
	action VARCHAR(50), 
	entity_type VARCHAR(50), 
	entity_id UUID, 
	diff JSONB, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE journal_entries (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	journal_id UUID NOT NULL, 
	entry_number VARCHAR(30) NOT NULL, 
	entry_date DATE NOT NULL, 
	reference VARCHAR(100), 
	description TEXT, 
	is_posted BOOLEAN DEFAULT false NOT NULL, 
	fiscal_year SMALLINT, 
	created_by UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_entries_company_number UNIQUE (company_id, entry_number), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(journal_id) REFERENCES journals (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE stock_movements (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	product_id UUID NOT NULL, 
	movement_type VARCHAR(10) NOT NULL, 
	quantity NUMERIC(15, 3) NOT NULL, 
	reference_doc UUID, 
	movement_date DATE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE invoices (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	company_id UUID, 
	partner_id UUID, 
	type VARCHAR(15) NOT NULL, 
	invoice_number VARCHAR(30), 
	issue_date DATE NOT NULL, 
	due_date DATE, 
	status VARCHAR(15) DEFAULT 'draft' NOT NULL, 
	total_ht NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	total_tva NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	total_ttc NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	journal_entry_id UUID, 
	converted_from UUID, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_invoices_company_type_number UNIQUE (company_id, type, invoice_number), 
	FOREIGN KEY(company_id) REFERENCES companies (id), 
	FOREIGN KEY(partner_id) REFERENCES partners (id), 
	FOREIGN KEY(journal_entry_id) REFERENCES journal_entries (id), 
	FOREIGN KEY(converted_from) REFERENCES invoices (id)
);

CREATE TABLE journal_entry_lines (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	entry_id UUID NOT NULL, 
	account_code VARCHAR(10) NOT NULL, 
	label VARCHAR(255), 
	debit NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	credit NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	partner_id UUID, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_entry_line_amounts CHECK (debit >= 0 AND credit >= 0), 
	FOREIGN KEY(entry_id) REFERENCES journal_entries (id) ON DELETE CASCADE
);

CREATE TABLE invoice_lines (
	id UUID DEFAULT gen_random_uuid() NOT NULL, 
	invoice_id UUID NOT NULL, 
	product_id UUID, 
	description VARCHAR(255), 
	quantity NUMERIC(15, 3) DEFAULT 1 NOT NULL, 
	unit_price_ht NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	tva_rate NUMERIC(5, 2) DEFAULT 19 NOT NULL, 
	line_total_ht NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	line_total_tva NUMERIC(15, 2) DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES invoices (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
