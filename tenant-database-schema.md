# Tenant Database Schema

Each hospital tenant has its own isolated database. This document covers the five core modules: **Base**, **Billing**, **Clinical**, **Pharmacy**, and **IPD**.

> **Note:** `patient_id` fields that reference patients are loose UUID references to `global_patient_db.patients.id` — there is no cross-database FK constraint. All other UUID foreign keys reference tables within the same tenant database.

---

## Table of Contents

- [Base Module](#base-module)
- [Billing Module](#billing-module)
- [Clinical Module](#clinical-module)
- [Pharmacy Module](#pharmacy-module)
- [IPD Module](#ipd-module)

---

## Base Module

The foundation of every tenant database. Defines users, roles, departments, permissions, and system-wide configuration. Every other module depends on `users` and `departments` from this module.

---

### `roles`

Defines named roles within the hospital (e.g. Doctor, Nurse, Pharmacist, Front Desk). System roles seeded at tenant creation cannot be deleted.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `name` | STRING(100) | NO | — | e.g. Hospital Admin, Doctor, Nurse |
| `description` | TEXT | YES | — | |
| `is_system` | BOOLEAN | NO | `false` | Seeded roles; cannot be deleted |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_by` | UUID | YES | — | `users.id` of admin who created this role |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |
| `deleted_at` | DATE | YES | — | Soft delete (paranoid) |

---

### `departments`

Hospital departments such as Cardiology, Orthopedics, Pharmacy, Pathology.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `name` | STRING(150) | NO | — | e.g. Cardiology, Ortho |
| `description` | TEXT | YES | — | |
| `head_id` | UUID | YES | — | `users.id` of department head |
| `short_code` | STRING(50) | YES | — | e.g. CARDIO, ORTHO (unique) |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_by` | UUID | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `users`

Core authentication record for every staff member in the tenant. Profile fields (specialization, registration number, etc.) are stored via the EAV pattern in `user_field_values`. Sensitive columns (`password_hash`, `refresh_token_hash`, etc.) are excluded from the default query scope.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `first_name` | STRING(120) | YES | — | |
| `last_name` | STRING(120) | YES | — | |
| `role_id` | UUID | YES | — | FK → `roles.id` |
| `department_id` | UUID | YES | — | FK → `departments.id` |
| `email` | STRING(200) | YES | — | Unique; validated email format |
| `phone` | STRING(20) | YES | — | Unique |
| `password_hash` | TEXT | NO | — | Excluded from default scope |
| `is_active` | BOOLEAN | NO | `true` | |
| `last_login` | DATE | YES | — | |
| `password_changed_at` | DATE | YES | — | |
| `refresh_token_hash` | TEXT | YES | — | Excluded from default scope |
| `failed_login_attempts` | INTEGER | NO | `0` | Excluded from default scope |
| `locked_until` | DATE | YES | — | Auto-unlock timestamp after brute-force lockout |
| `created_by` | UUID | YES | — | `users.id` of admin who created this account |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |
| `deleted_at` | DATE | YES | — | Soft delete (paranoid) |

---

### `role_field_definitions`

EAV schema layer. Defines what dynamic profile fields each role has. A hospital admin configures these per role (e.g. the "Doctor" role may have `specialization`, `medical_registration_no`, `years_of_experience`).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `role_id` | UUID | NO | — | FK → `roles.id` (CASCADE delete) |
| `field_key` | STRING(100) | NO | — | Internal snake_case key e.g. `specialization` |
| `field_label` | STRING(150) | NO | — | Human-readable UI label |
| `field_type` | ENUM | NO | `text` | `text`, `textarea`, `number`, `email`, `phone`, `date`, `select`, `multiselect`, `boolean`, `file`, `url` |
| `options` | JSONB | NO | `[]` | Choices for `select`/`multiselect` fields |
| `is_required` | BOOLEAN | NO | `false` | |
| `is_unique` | BOOLEAN | NO | `false` | e.g. `medical_registration_no` must be unique |
| `default_value` | TEXT | YES | — | Pre-populated value for new users of this role |
| `validation_regex` | STRING(500) | YES | — | Custom format validation |
| `sort_order` | INTEGER | NO | `0` | Controls display order in forms |
| `is_active` | BOOLEAN | NO | `true` | Soft disable — hides field but preserves data |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `user_field_values`

EAV data layer. Stores the actual profile values for each user based on their role's field definitions. All values are stored as TEXT and cast on read using the `field_type` from the definition.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `user_id` | UUID | NO | — | FK → `users.id` (CASCADE delete) |
| `field_def_id` | UUID | NO | — | FK → `role_field_definitions.id` |
| `field_value` | TEXT | YES | — | All values stored as text; cast on read |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `role_permissions`

Module-level RBAC. Maps a role to a module (e.g. `clinical`, `pharmacy`) and defines what actions that role can perform.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `role_id` | UUID | NO | — | FK → `roles.id` (CASCADE delete) |
| `module_name` | STRING(100) | NO | — | e.g. `hrms`, `clinical`, `ipd`, `pharmacy` |
| `can_view` | BOOLEAN | NO | `false` | |
| `can_create` | BOOLEAN | NO | `false` | |
| `can_update` | BOOLEAN | NO | `false` | |
| `can_delete` | BOOLEAN | NO | `false` | |
| `can_export` | BOOLEAN | NO | `false` | |
| `can_approve` | BOOLEAN | NO | `false` | For approval workflows (leave, PO, lab results) |
| `custom_actions` | JSONB | NO | `{}` | Module-specific actions e.g. `{ "can_dispense": true }` |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `role_field_access`

Column-level access control. Finer-grained than `role_permissions` — controls which individual fields/sections within a module each role can view or edit.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `role_id` | UUID | NO | — | FK → `roles.id` (CASCADE delete) |
| `module_name` | STRING(100) | NO | — | e.g. `clinical`, `billing` |
| `field_name` | STRING(100) | NO | — | Logical field e.g. `diagnosis`, `prescription`, `billing_total` |
| `can_view` | BOOLEAN | NO | `true` | |
| `can_edit` | BOOLEAN | NO | `false` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `audit_logs`

Immutable append-only log of all user actions within the tenant. Written by middleware/services; never updated or deleted. Denormalizes user email and role name to survive user deletion.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `user_id` | UUID | YES | — | Null for system-triggered actions |
| `user_email` | STRING(200) | YES | — | Denormalized — survives user deletion |
| `role_name` | STRING(100) | YES | — | Denormalized — captures role at time of action |
| `module` | STRING(100) | YES | — | e.g. `hrms`, `clinical`, `pharmacy` |
| `action` | STRING(50) | NO | — | `create`, `update`, `delete`, `login`, `dispense`, etc. |
| `resource_type` | STRING(100) | YES | — | Model name: `Appointment`, `Prescription`, etc. |
| `resource_id` | STRING(200) | YES | — | UUID of the affected record |
| `ip_address` | STRING(45) | YES | — | |
| `user_agent` | TEXT | YES | — | |
| `status` | ENUM | NO | `success` | `success`, `denied`, `error` |
| `metadata` | JSONB | NO | `{}` | Before/after snapshot, error details, request summary |
| `created_at` | DATE | NO | NOW | No `updated_at` — immutable |

---

### `hospital_settings`

Key-value configuration store for hospital-wide settings. Allows the hospital admin to tune behavior via the dashboard without code changes.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `key` | STRING(100) | NO | — | Unique setting key e.g. `uhid_prefix`, `appointment_slot_buffer_minutes` |
| `value` | TEXT | YES | — | |
| `value_type` | ENUM | NO | `string` | `string`, `number`, `boolean`, `json` |
| `category` | STRING(50) | YES | — | `general`, `clinical`, `pharmacy`, `billing`, `notification` |
| `description` | TEXT | YES | — | Human-readable explanation for settings UI |
| `is_editable` | BOOLEAN | NO | `true` | `false` for system-critical settings |
| `updated_by` | UUID | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `notifications`

In-app notification store for tenant users. Push/email/SMS delivery is handled by a separate service; this table is the persistence layer for the in-app notification inbox.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `user_id` | UUID | NO | — | FK → `users.id` (CASCADE delete) |
| `title` | STRING(250) | NO | — | |
| `body` | TEXT | YES | — | |
| `type` | ENUM | NO | `general` | `appointment_reminder`, `leave_request`, `leave_approved`, `leave_rejected`, `low_stock_alert`, `lab_result_ready`, `consent_request`, `maintenance_update`, `system`, `general` |
| `priority` | ENUM | NO | `normal` | `low`, `normal`, `high`, `urgent` |
| `module` | STRING(100) | YES | — | |
| `resource_type` | STRING(100) | YES | — | Deep link entity type |
| `resource_id` | UUID | YES | — | Deep link entity ID |
| `is_read` | BOOLEAN | NO | `false` | |
| `read_at` | DATE | YES | — | |
| `metadata` | JSONB | NO | `{}` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

## Billing Module

Handles all financial transactions in the hospital — bill creation, line items, payments, and invoices. Supports OPD, IPD, pharmacy, and diagnostic billing types.

---

### `price_items`

Master catalogue of all billable services and their prices. Referenced by `bill_items` as the source of truth for service pricing.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `service_code` | STRING(50) | NO | — | Unique service code |
| `service_name` | STRING(300) | NO | — | |
| `price` | DECIMAL(12,2) | NO | — | |
| `currency` | STRING(10) | NO | `INR` | |
| `status` | ENUM | NO | `active` | `active`, `inactive` |
| `description` | TEXT | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `bills`

Header record for a patient bill. One bill per visit/admission. Tracks the running totals of items, payments, and outstanding balance.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `patient_id` | UUID | NO | — | Loose ref to `global_patient_db` |
| `appointment_id` | UUID | YES | — | For OPD bills |
| `admission_id` | UUID | YES | — | For IPD bills |
| `bill_type` | ENUM | NO | `OPD` | `OPD`, `IPD`, `PHARMACY`, `DIAGNOSTIC` |
| `notes` | TEXT | YES | — | |
| `status` | ENUM | NO | `draft` | `draft`, `partial_paid`, `paid`, `finalized`, `cancelled`, `refund_pending` |
| `currency` | STRING(10) | NO | `INR` | |
| `item_count` | INTEGER | NO | `0` | Count of active `bill_items` |
| `total_price` | DECIMAL(12,2) | NO | `0` | Sum of all active bill items |
| `paid_amount` | DECIMAL(12,2) | NO | `0` | Sum of all completed payments |
| `balance_amount` | DECIMAL(12,2) | NO | `0` | `total_price - paid_amount`; negative = patient credit |
| `finalized_at` | DATE | YES | — | Set at discharge finalization |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `bill_items`

Individual line items within a bill. Each item represents a specific charge (bed charge, consultation, procedure, medicine, etc.). Snapshots the service name and code at billing time so the bill is immune to future price list changes.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `bill_id` | UUID | NO | — | FK → `bills.id` |
| `price_item_id` | UUID | YES | — | FK → `price_items.id`; nullable for ad-hoc items |
| `service_code_snapshot` | STRING(50) | YES | — | Snapshotted from `price_items` at billing time |
| `service_name_snapshot` | STRING(300) | YES | — | Snapshotted from `price_items` at billing time |
| `item_type` | ENUM | NO | `OTHER` | `BED_CHARGE`, `DOCTOR_VISIT`, `CONSULTATION`, `PROCEDURE`, `CONSUMABLE`, `PHARMACY`, `DIAGNOSTIC`, `DISCOUNT`, `OTHER` |
| `reference_type` | STRING(50) | YES | — | Polymorphic source e.g. `BED_ALLOCATION`, `DOCTOR_VISIT` |
| `reference_id` | UUID | YES | — | FK to source row (no DB constraint) |
| `service_date` | DATEONLY | YES | — | Date charge applies to (bed charges: per day) |
| `quantity` | INTEGER | NO | `1` | |
| `unit_price` | DECIMAL(12,2) | NO | — | |
| `auto_generated` | BOOLEAN | NO | `false` | `true` if created by daily cron |
| `notes` | TEXT | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `bill_payments`

Records each payment transaction against a bill. Supports split payments, advance payments, and refunds. Captures full gateway response for online payments.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `bill_id` | UUID | YES | — | Payment applied to the bill (split-payment friendly) |
| `bill_item_id` | UUID | YES | — | Optional: payment tied to a specific line item |
| `payment_type` | ENUM | NO | `PARTIAL` | `ADVANCE`, `PARTIAL`, `FINAL_SETTLEMENT`, `REFUND` |
| `payment_method` | ENUM | NO | — | `CASH`, `CREDIT_CARD`, `DEBIT_CARD`, `UPI`, `NET_BANKING`, `WALLET`, `CHEQUE`, `INSURANCE_TPA` |
| `amount` | DECIMAL(12,2) | NO | — | Negative for refunds |
| `transaction_id` | STRING(200) | YES | — | UTR / gateway txn ID / cheque number |
| `upi_app` | STRING(50) | YES | — | e.g. Google Pay, PhonePe, Paytm |
| `card_last_4` | STRING(4) | YES | — | |
| `gateway` | STRING(50) | YES | — | e.g. `razorpay`, `manual`, `pos` |
| `gateway_payment_id` | STRING(100) | YES | — | |
| `gateway_response` | JSONB | YES | — | Full gateway callback payload |
| `status` | ENUM | NO | `COMPLETED` | `PENDING`, `COMPLETED`, `FAILED`, `REFUNDED` |
| `collected_by` | UUID | YES | — | Cashier `users.id` |
| `paid_at` | DATE | NO | NOW | |
| `notes` | TEXT | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `invoices`

Formal issued invoice record tied to a patient appointment. Distinct from `bills` — an invoice is the official document issued after payment.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `invoice_number` | STRING(50) | NO | — | Unique |
| `appointment_id` | UUID | NO | — | |
| `patient_id` | UUID | NO | — | |
| `generated_at` | DATE | NO | — | |
| `status` | ENUM | NO | `issued` | `issued`, `cancelled` |
| `currency` | STRING(10) | NO | `INR` | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

## Clinical Module

Covers the full outpatient clinical workflow: doctor scheduling, appointment booking, patient encounters, vitals recording, diagnoses, prescriptions, lab orders, clinical notes, consent management, and referrals.

> All `patient_id` fields are loose UUID references to `global_patient_db`.

---

### `schedules`

Defines a doctor's recurring weekly availability — e.g. "every Monday 9am–1pm, 15-min slots". One row per day-of-week per doctor.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `day_of_week` | INTEGER | NO | — | `0`=Sun, `1`=Mon … `6`=Sat |
| `start_time` | TIME | NO | — | |
| `end_time` | TIME | NO | — | |
| `department_id` | UUID | YES | — | FK → `departments.id` |
| `slot_duration_minutes` | INTEGER | NO | `15` | |
| `max_patients_per_slot` | INTEGER | NO | `1` | |
| `consultation_type` | ENUM | NO | `in_person` | `in_person`, `online`, `both` |
| `consultation_fee` | DECIMAL(10,2) | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `schedule_overrides`

Single-day exceptions to a doctor's recurring schedule — holidays, custom hours, or special clinics. Takes precedence over the base schedule for that date.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `override_date` | DATEONLY | NO | — | Unique per doctor |
| `override_type` | ENUM | NO | — | `unavailable`, `custom_hours` |
| `start_time` | TIME | YES | — | Used when `override_type = custom_hours` |
| `end_time` | TIME | YES | — | Used when `override_type = custom_hours` |
| `slot_duration_minutes` | INTEGER | YES | — | |
| `reason` | TEXT | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `appointments`

Patient appointment bookings. Supports walk-ins, scheduled, online, follow-up, and emergency types. Tracks the full lifecycle from booking to completion.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `token_number` | STRING(50) | YES | — | Human-readable daily token e.g. `OPD-20260311-042` |
| `patient_id` | UUID | NO | — | Loose ref to `global_patient_db` |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `department_id` | UUID | YES | — | FK → `departments.id` |
| `appointment_date` | DATEONLY | NO | — | |
| `slot_start` | TIME | NO | — | |
| `slot_end` | TIME | NO | — | |
| `type` | ENUM | NO | `scheduled` | `walkin`, `scheduled`, `online`, `follow_up`, `emergency` |
| `status` | ENUM | NO | `pending` | `pending`, `waiting`, `booked`, `confirmed`, `checked_in`, `in_progress`, `completed`, `cancelled`, `no_show`, `rescheduled` |
| `appointment_completed_at` | DATE | YES | — | Server-set when marked completed |
| `priority` | ENUM | NO | `normal` | `normal`, `urgent`, `emergency` |
| `cancel_reason` | TEXT | YES | — | |
| `rescheduled_from` | UUID | YES | — | Original appointment ID if rescheduled |
| `chief_complaint` | TEXT | YES | — | Brief reason for visit captured at booking |
| `booked_by` | UUID | YES | — | `users.id` of front desk staff or patient |
| `source` | ENUM | NO | `front_desk` | `front_desk`, `patient_app`, `doctor_referral`, `phone`, `online` |
| `is_follow_up` | BOOLEAN | NO | `false` | Consultation fee waived when true |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `doctor_token_queue`

Tracks the appointment request order for each doctor/date and the final assigned token after payment. Manages the `REQ → GENERATED` token lifecycle.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `appointment_id` | UUID | NO | — | FK → `appointments.id` (unique) |
| `appointment_date` | DATEONLY | NO | — | |
| `queue_status` | STRING(20) | NO | `REQ` | `REQ`, `GENERATED`, `CANCELLED` |
| `token_number` | STRING(50) | YES | — | Populated once payment is confirmed |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `encounters`

The central EMR record for a patient visit. At most one encounter per appointment. All clinical sub-records (vitals, diagnoses, prescriptions, notes, lab orders) hang off this record.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `appointment_id` | UUID | YES | — | FK → `appointments.id` (unique); null for emergency |
| `patient_id` | UUID | NO | — | Denormalized from appointment |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `department_id` | UUID | YES | — | FK → `departments.id` |
| `encounter_type` | ENUM | NO | `opd` | `opd`, `ipd`, `emergency`, `teleconsult` |
| `encounter_date` | DATE | NO | NOW | |
| `status` | ENUM | NO | `open` | `pending`, `vitals_added`, `open`, `in_progress`, `completed`, `closed` |
| `summary` | TEXT | YES | — | Doctor's end-of-visit summary |
| `follow_up_date` | DATEONLY | YES | — | |
| `follow_up_notes` | TEXT | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `vitals`

Patient vital signs recorded during an encounter. Multiple readings per encounter are allowed (e.g. pre/post treatment).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `recorded_by` | UUID | YES | — | FK → `users.id` (nurse/staff) |
| `recorded_at` | DATE | NO | NOW | |
| `weight_kg` | DECIMAL(5,2) | YES | — | |
| `height_cm` | DECIMAL(5,1) | YES | — | |
| `bmi` | DECIMAL(4,1) | YES | — | Auto-computed if weight+height present |
| `bp_systolic` | INTEGER | YES | — | mmHg |
| `bp_diastolic` | INTEGER | YES | — | mmHg |
| `pulse_bpm` | INTEGER | YES | — | |
| `temperature_f` | DECIMAL(5,1) | YES | — | Fahrenheit |
| `spo2_percent` | DECIMAL(4,1) | YES | — | |
| `respiratory_rate` | INTEGER | YES | — | Breaths per minute |
| `blood_sugar_mg` | DECIMAL(6,1) | YES | — | mg/dL |
| `blood_sugar_type` | ENUM | YES | — | `fasting`, `pp`, `random` |
| `notes` | TEXT | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `diagnoses`

Clinical diagnoses made during an encounter. Supports ICD coding and classification by type and severity.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `icd_code` | STRING(20) | YES | — | ICD-10 / ICD-11 code |
| `description` | TEXT | NO | — | |
| `diagnosis_type` | ENUM | NO | `primary` | `primary`, `secondary`, `differential`, `provisional`, `final` |
| `severity` | ENUM | YES | — | `mild`, `moderate`, `severe`, `critical` |
| `notes` | TEXT | YES | — | |
| `diagnosed_by` | UUID | NO | — | FK → `users.id` |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `prescriptions`

Prescription header record — one per encounter. The actual medicines are stored as `prescription_items`. Tracks dispensing status once pharmacy fulfills the prescription.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `doctor_id` | UUID | NO | — | FK → `users.id` |
| `prescription_number` | STRING(50) | YES | — | Unique e.g. `RX-20260311-001` |
| `notes` | TEXT | YES | — | General prescription advice |
| `is_dispensed` | BOOLEAN | NO | `false` | Set to true once pharmacy fulfills |
| `dispensed_at` | DATE | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `prescription_items`

Individual medicine lines within a prescription. Deleted when the parent prescription is deleted (CASCADE).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `prescription_id` | UUID | NO | — | FK → `prescriptions.id` (CASCADE delete) |
| `medicine_name` | STRING(250) | NO | — | |
| `generic_name` | STRING(250) | YES | — | |
| `dosage` | STRING(100) | YES | — | e.g. `500mg`, `10ml` |
| `dosage_form` | STRING(50) | YES | — | `tablet`, `syrup`, `injection`, etc. |
| `frequency` | STRING(100) | YES | — | e.g. `1-0-1`, `twice daily`, `BD`, `TDS` |
| `route` | STRING(50) | YES | — | `oral`, `iv`, `im`, `topical`, `inhaled` |
| `duration_days` | INTEGER | YES | — | |
| `quantity` | INTEGER | YES | — | Total quantity to dispense |
| `instructions` | TEXT | YES | — | e.g. Before food, at bedtime |
| `is_sos` | BOOLEAN | NO | `false` | SOS / PRN — take only if needed |
| `sort_order` | INTEGER | NO | `0` | Display order on prescription |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `clinical_notes`

SOAP notes, progress notes, nursing notes, and procedure notes attached to an encounter. Supports addendum chaining where a later note references and amends an original.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `author_id` | UUID | NO | — | FK → `users.id` |
| `note_type` | ENUM | NO | `soap` | `soap`, `progress`, `procedure`, `discharge`, `nursing`, `general` |
| `subjective` | TEXT | YES | — | SOAP — patient-reported symptoms |
| `objective` | TEXT | YES | — | SOAP — measurable observations |
| `assessment` | TEXT | YES | — | SOAP — clinical assessment |
| `plan` | TEXT | YES | — | SOAP — treatment plan |
| `content_text` | TEXT | YES | — | Free-text for non-SOAP note types |
| `is_addendum` | BOOLEAN | NO | `false` | |
| `parent_note_id` | UUID | YES | — | References original note if addendum |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `lab_test_orders`

Header record for a lab/radiology test order placed during an encounter. Individual tests are on `lab_test_order_items`. Multiple order headers per encounter are allowed.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `ordered_by` | UUID | NO | — | FK → `users.id` |
| `notes` | TEXT | YES | — | Order-level instructions for lab/radiology |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `lab_test_order_items`

Individual tests within a lab test order. Deleted when the parent order is deleted (CASCADE).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `lab_test_order_id` | UUID | NO | — | FK → `lab_test_orders.id` (CASCADE delete) |
| `test_name` | STRING(250) | NO | — | e.g. `CBC (Complete Blood Count)` |
| `test_code` | STRING(50) | YES | — | Short code e.g. `CBC` |
| `notes` | TEXT | YES | — | Line-level notes |
| `sort_order` | INTEGER | NO | `0` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `patient_consents`

Tracks patient consent for data access, treatment, data sharing, research, and ABDM health record linking. Critical for ABDM compliance — no data access without an active consent record.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `patient_id` | UUID | NO | — | |
| `consent_type` | ENUM | NO | — | `data_access`, `treatment`, `data_sharing`, `research`, `abdm_health_records` |
| `granted_to_user_id` | UUID | YES | — | FK → `users.id` (doctor/staff granted access) |
| `granted_to_department_id` | UUID | YES | — | Department-wide consent |
| `scope` | JSONB | NO | `{}` | Granular scope: modules, date ranges |
| `granted_at` | DATE | NO | NOW | |
| `expires_at` | DATE | YES | — | Null = until revoked |
| `revoked_at` | DATE | YES | — | |
| `revoke_reason` | TEXT | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `consent_mode` | ENUM | YES | — | `otp`, `biometric`, `in_person_signature`, `app` |
| `consent_artifact_url` | TEXT | YES | — | Signed consent form PDF or ABDM artifact URL |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `referrals`

Patient referrals generated during an encounter — to internal doctors, internal diagnostics, or external hospitals.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `encounter_id` | UUID | NO | — | FK → `encounters.id` |
| `patient_id` | UUID | NO | — | |
| `referred_by` | UUID | NO | — | FK → `users.id` |
| `referral_type` | ENUM | NO | — | `internal_doctor`, `internal_diagnostic`, `external_hospital` |
| `referred_to_user_id` | UUID | YES | — | FK → `users.id` for internal doctor referrals |
| `referred_to_department_id` | UUID | YES | — | For internal department referrals |
| `external_hospital_name` | STRING(250) | YES | — | For external referrals |
| `external_doctor_name` | STRING(200) | YES | — | For external referrals |
| `reason` | TEXT | NO | — | |
| `urgency` | ENUM | NO | `routine` | `routine`, `urgent`, `stat` |
| `status` | ENUM | NO | `pending` | `pending`, `accepted`, `completed`, `declined` |
| `notes` | TEXT | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

## Pharmacy Module

Manages the full pharmacy workflow: medicine catalogue, supplier management, stock receiving, batch-level inventory tracking, dispense against prescriptions or OTC, and an append-only stock transaction ledger.

---

### `medicines`

Product catalogue — one row per unique medicine in the tenant's pharmacy. Stock levels live on `stock_batches`, not here.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `name` | STRING(255) | NO | — | Brand/trade name |
| `manufacturer` | STRING(255) | YES | — | |
| `dosage_form` | ENUM | NO | — | `TABLET`, `CAPSULE`, `SYRUP`, `INJECTION`, `VIAL`, `SACHET`, `CREAM`, `OINTMENT`, `GEL`, `DROPS`, `INHALER`, `POWDER`, `SPRAY`, `LOTION`, `SUPPOSITORY`, `PATCH`, `OTHER` |
| `description` | TEXT | YES | — | Free-text notes |
| `barcode` | STRING(50) | YES | — | Unique when not null |
| `reorder_level` | INTEGER | NO | `0` | Low-stock alert threshold (across all batches) |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `suppliers`

Pharmacy supplier / distributor master. Referenced by `stock_receipts` when receiving new stock.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `name` | STRING(255) | NO | — | |
| `gst_number` | STRING(15) | YES | — | 15-character GSTIN; unique when not null |
| `drug_license_number` | STRING(50) | YES | — | e.g. `20B/21B-XXXX` |
| `contact_person` | STRING(255) | NO | — | |
| `phone` | STRING(15) | NO | — | |
| `alternate_phone` | STRING(15) | YES | — | |
| `email` | STRING(255) | YES | — | |
| `street_address` | TEXT | YES | — | |
| `city` | STRING(100) | YES | — | |
| `state` | STRING(100) | YES | — | |
| `pincode` | STRING(6) | YES | — | |
| `country` | STRING(100) | YES | `India` | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `stock_batches`

Physical inventory — one row per batch of a medicine. `quantity` is mutable and tracks current available units. Every mutation must also append a row to `stock_transactions`. Batch status is managed by a daily cron based on expiry date and quantity.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `medicine_id` | UUID | NO | — | FK → `medicines.id` |
| `batch_number` | STRING(100) | NO | — | Unique per medicine |
| `expiry_date` | DATEONLY | NO | — | |
| `quantity` | INTEGER | NO | `0` | Current available units (mutable) |
| `purchase_price` | DECIMAL(10,2) | NO | — | Cost per unit from supplier |
| `mrp` | DECIMAL(10,2) | NO | — | Maximum retail / selling price per unit |
| `storage_location` | STRING(255) | YES | — | e.g. `Rack A – Shelf 2` |
| `status` | ENUM | NO | `ACTIVE` | `ACTIVE`, `NEAR_EXPIRY`, `EXPIRED`, `DEPLETED` — managed by daily cron |
| `received_at` | DATEONLY | NO | — | Date batch was physically received |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `stock_receipts`

Header record for a stock receiving event. One receipt has many `stock_receipt_items`. Confirmation creates/tops-up stock batches and appends stock transactions.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `supplier_id` | UUID | YES | — | FK → `suppliers.id`; nullable for ad-hoc stock additions |
| `invoice_number` | STRING(100) | YES | — | Supplier invoice number |
| `invoice_date` | DATEONLY | YES | — | |
| `total_items` | INTEGER | NO | `0` | Denormalized count of line items |
| `total_quantity` | INTEGER | NO | `0` | Denormalized total units received |
| `total_value` | DECIMAL(12,2) | NO | `0.00` | Sum of `purchase_price × quantity` across items |
| `status` | ENUM | NO | `DRAFT` | `DRAFT`, `CONFIRMED`, `CANCELLED` |
| `received_by` | UUID | NO | — | `users.id` of staff who received the stock |
| `received_at` | DATEONLY | NO | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `stock_receipt_items`

Individual line items within a stock receipt. On receipt confirmation, each item creates or tops up a `stock_batch` and appends a `STOCK_IN` transaction.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `stock_receipt_id` | UUID | NO | — | FK → `stock_receipts.id` |
| `medicine_id` | UUID | NO | — | FK → `medicines.id` |
| `batch_number` | STRING(100) | NO | — | |
| `expiry_date` | DATEONLY | NO | — | |
| `quantity` | INTEGER | NO | — | Units received |
| `purchase_price` | DECIMAL(10,2) | NO | — | Cost per unit |
| `mrp` | DECIMAL(10,2) | NO | — | Selling price per unit |
| `total_cost` | DECIMAL(12,2) | NO | — | `purchase_price × quantity` |
| `batch_id` | UUID | YES | — | FK → `stock_batches.id`; populated after confirmation |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `stock_transactions`

Append-only stock ledger. Every change to `stock_batches.quantity` produces exactly one row here. Rows are never updated or deleted. `balance_after` enables point-in-time stock reconstruction.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `medicine_id` | UUID | NO | — | FK → `medicines.id` |
| `batch_id` | UUID | NO | — | FK → `stock_batches.id` |
| `transaction_type` | ENUM | NO | — | `STOCK_IN`, `DISPENSED`, `ADJUSTMENT`, `RETURN`, `EXPIRED_WRITE_OFF` |
| `quantity` | INTEGER | NO | — | Positive = stock in, negative = stock out |
| `reference_id` | UUID | YES | — | FK to source record (stock receipt, prescription, etc.) |
| `reference_type` | ENUM | YES | — | `PURCHASE_ORDER`, `PRESCRIPTION`, `MANUAL` |
| `balance_after` | INTEGER | NO | — | Batch quantity snapshot after this transaction |
| `performed_by` | UUID | NO | — | `users.id` of staff who triggered the transaction |
| `notes` | TEXT | YES | — | |
| `created_at` | DATE | NO | NOW | No `updated_at` — append-only |

---

### `dispenses`

Dispense header record. Tracks the full dispensing event — against a prescription or as an OTC sale. Captures patient and doctor details as snapshots for invoice rendering.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `prescription_id` | UUID | YES | — | Loose ref to `prescriptions.id`; null for OTC |
| `patient_id` | UUID | YES | — | Loose ref to `global_patient_db`; null for anonymous OTC |
| `patient_name` | STRING(255) | YES | — | Snapshotted for invoice |
| `patient_uhid` | STRING(50) | YES | — | Snapshotted for invoice |
| `doctor_name` | STRING(255) | YES | — | Snapshotted for invoice |
| `invoice_number` | STRING(50) | YES | — | Unique; auto-generated on completion e.g. `RX-2025-0891` |
| `subtotal` | DECIMAL(12,2) | NO | `0.00` | |
| `tax_percent` | DECIMAL(5,2) | NO | `0.00` | GST percentage |
| `tax_amount` | DECIMAL(12,2) | NO | `0.00` | |
| `grand_total` | DECIMAL(12,2) | NO | `0.00` | |
| `payment_method` | ENUM | YES | — | `CASH`, `UPI`, `CARD`, `CREDIT`, `INSURANCE`, `OTHER` |
| `status` | ENUM | NO | `PENDING` | `PENDING`, `PROCESSING`, `COMPLETED`, `CANCELLED` |
| `dispensed_by` | UUID | NO | — | `users.id` of pharmacy staff |
| `dispensed_at` | DATE | YES | — | Set when status moves to `COMPLETED` |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `dispense_items`

Individual medicine lines within a dispense. All values (medicine name, batch number, unit price) are snapshotted at dispense time so the invoice is immune to future catalogue changes.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `dispense_id` | UUID | NO | — | FK → `dispenses.id` |
| `medicine_id` | UUID | NO | — | FK → `medicines.id` |
| `batch_id` | UUID | NO | — | FK → `stock_batches.id` |
| `medicine_name` | STRING(255) | NO | — | Snapshotted at dispense time |
| `batch_number` | STRING(100) | NO | — | Snapshotted from `stock_batches` |
| `dosage_form` | STRING(50) | YES | — | Snapshotted for invoice display |
| `prescribed_dosage` | STRING(100) | YES | — | e.g. `1-0-1 (5 Days)` — from `prescription_items` |
| `quantity_dispensed` | INTEGER | NO | — | |
| `unit_price` | DECIMAL(10,2) | NO | — | MRP per unit at dispense time (snapshotted) |
| `net_amount` | DECIMAL(12,2) | NO | — | `unit_price × quantity_dispensed` |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

## IPD Module

Manages inpatient (IPD) admissions, room and bed infrastructure, bed allocations, and configurable dropdown values (artifacts).

---

### `artifacts`

Configurable dropdown / picklist store for the IPD module. Hospital admins define the valid values for fields like ward types, admission types, and admission sources. Each row is one dropdown category with its options stored as a JSONB array.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `key` | STRING(100) | NO | — | Unique dropdown key e.g. `ipd.ward`, `ipd.admission_type` |
| `values` | JSONB | NO | `[]` | Array of `{ code, label }` objects |
| `description` | STRING(255) | YES | — | |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `rooms`

Physical rooms within the hospital. Grouped by ward, block, and floor. Rooms contain beds.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `room_no` | STRING(50) | NO | — | Display room number e.g. `203`; unique per block |
| `ward` | STRING(50) | NO | — | References `artifacts['ipd.ward'].values[].code` |
| `block` | STRING(50) | YES | — | |
| `floor` | STRING(20) | YES | — | |
| `tags` | JSONB | NO | `{}` | Room amenity flags e.g. `{ ac: true, attached_bathroom: true }` |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `beds`

Individual beds within a room. Tracks physical bed state and daily charge. Equipment capabilities are stored as flexible JSONB tags.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `room_id` | UUID | NO | — | FK → `rooms.id` |
| `bed_no` | STRING(50) | NO | — | e.g. `BED-203-A`; unique per room |
| `tags` | JSONB | NO | `{}` | Equipment flags e.g. `{ has_oxygen: true, has_ventilator: false }` |
| `daily_charge` | DECIMAL(12,2) | NO | — | Per-day bed charge in INR |
| `status` | ENUM | NO | `AVAILABLE` | `AVAILABLE`, `BOOKED`, `OCCUPIED`, `MAINTENANCE`, `BLOCKED` |
| `is_active` | BOOLEAN | NO | `true` | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `admissions`

IPD admission record — the central anchor for the inpatient stay. Tracks the full lifecycle from initiation through bed allocation, payment, admission, and discharge. Supports a clinical team with a primary consultant and multiple co-consultants.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `admission_no` | STRING(50) | NO | — | Unique human-readable ID e.g. `IPD-2026-00123` |
| `global_patient_id` | UUID | NO | — | Loose ref to `global_patient_db` |
| `admission_type` | STRING(50) | NO | — | References `artifacts['ipd.admission_type'].values[].code` |
| `admission_source` | STRING(50) | NO | — | References `artifacts['ipd.admission_source'].values[].code` |
| `urgency` | ENUM | NO | — | `ELECTIVE`, `EMERGENCY` |
| `estimated_los_days` | INTEGER | YES | — | Estimated length of stay in days |
| `chief_complaint` | TEXT | YES | — | |
| `consultant_id` | UUID | NO | — | Primary consultant `users.id` |
| `co_consultant_ids` | JSONB | NO | `[]` | Array of co-consultant `users.id` values |
| `emergency_contact` | JSONB | YES | — | `{ name, relation, phone, alternate_phone }` |
| `visit_fee_schedule` | JSONB | YES | — | `{ price_item_id, charge_type: PER_DAY\|PER_VISIT, amount }` |
| `status` | ENUM | NO | `INITIATED` | `INITIATED`, `BED_ALLOCATED`, `PAYMENT_DONE`, `ADMITTED`, `DISCHARGED`, `CANCELLED` |
| `initiated_at` | DATE | NO | NOW | |
| `bed_allocated_at` | DATE | YES | — | |
| `payment_completed_at` | DATE | YES | — | |
| `admitted_at` | DATE | YES | — | Actual admission timestamp |
| `discharged_at` | DATE | YES | — | |
| `cancelled_at` | DATE | YES | — | |
| `cancellation_reason` | STRING(255) | YES | — | |
| `created_by` | UUID | NO | — | |
| `updated_by` | UUID | YES | — | |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |

---

### `bed_allocations`

Records which bed a patient occupies during an admission. Supports bed transfers by chaining allocations via `transferred_to_allocation_id`. A null `released_at` means the patient is currently in that bed.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | UUIDV4 | Primary key |
| `admission_id` | UUID | NO | — | FK → `admissions.id` |
| `bed_id` | UUID | NO | — | FK → `beds.id` |
| `allocated_at` | DATE | NO | NOW | |
| `released_at` | DATE | YES | — | Null = currently occupying this bed |
| `transferred_to_allocation_id` | UUID | YES | — | Self-ref: points to new allocation after transfer |
| `transfer_reason` | STRING(255) | YES | — | |
| `daily_charge_snapshot` | DECIMAL(12,2) | NO | — | `beds.daily_charge` snapshotted at allocation time |
| `release_reason` | ENUM | YES | — | `TRANSFER`, `DISCHARGE`, `CANCELLED` |
| `allocated_by` | UUID | NO | — | `users.id` |
| `released_by` | UUID | YES | — | `users.id` |
| `created_at` | DATE | NO | NOW | |
| `updated_at` | DATE | NO | NOW | |
